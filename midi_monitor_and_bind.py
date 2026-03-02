import sys
import os
import time
import json
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any

import mido
from mido import Message, bpm2tempo

# --- Dépendance optionnelle pour les frappes clavier ---
try:
    from pynput.keyboard import Controller as KBController, Key
    _HAS_PYNPUT = True
except Exception:
    _HAS_PYNPUT = False
    KBController = None
    Key = None

# ------------------------------
# Paramètres personnalisables
# ------------------------------
TICKS_PER_BEAT = 480
DEFAULT_BPM = 120
PRINT_SYS_RT = False  # Afficher les messages système temps-réel (clock, start, stop, etc.)
CHANNEL_FILTER = None # None = tous, sinon 0..15
BINDINGS_FILE = "midi_bindings.json"

# ------------------------------
# Utils
# ------------------------------
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
def note_name(note_num: int) -> str:
    # Numérotation MIDI: 60 = C4 (middle C)
    octave = (note_num // 12) - 1
    name = NOTE_NAMES[note_num % 12]
    return f"{name}{octave}"

def list_input_ports():
    ports = mido.get_input_names()
    if not ports:
        print("Aucun port MIDI d'entrée détecté.")
        sys.exit(1)
    return ports

def choose_port():
    ports = list_input_ports()
    print("\n=== Ports MIDI d'entrée disponibles ===")
    for i, p in enumerate(ports):
        print(f"[{i}] {p}")
    while True:
        try:
            idx = int(input("Sélectionne l'index du port : ").strip())
            if 0 <= idx < len(ports):
                return ports[idx]
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
        print("Indice invalide. Réessaie.")

def is_interesting(msg: Message) -> bool:
    if msg.type in ("clock", "start", "stop", "continue", "active_sensing", "songpos", "song_select", "time_code"):
        return PRINT_SYS_RT
    if CHANNEL_FILTER is not None and hasattr(msg, "channel"):
        return msg.channel == CHANNEL_FILTER
    return True

def format_event(msg: Message) -> str:
    base = f"{time.strftime('%H:%M:%S')} | "
    if hasattr(msg, "channel"):
        base += f"ch{msg.channel+1:02d} | "
    else:
        base += "sys  | "

    if msg.type in ("note_on", "note_off"):
        name = note_name(msg.note)
        return base + f"{msg.type:<8} {name:<4} (#{msg.note:03d}) vel={msg.velocity:3d}"
    elif msg.type == "control_change":
        return base + f"cc        {msg.control:3d} val={msg.value:3d}"
    elif msg.type == "pitchwheel":
        return base + f"pitchbend {msg.pitch:+6d}"
    elif msg.type in ("polytouch", "aftertouch", "channel_pressure"):
        pressure = getattr(msg, "value", getattr(msg, "pressure", None))
        return base + f"{msg.type:<10} value={pressure}"
    elif msg.type == "program_change":
        return base + f"program   {msg.program:3d}"
    elif msg.type == "sysex":
        return base + f"sysex     len={len(msg.data)}"
    else:
        return base + f"{msg.type}"

# ------------------------------
# Binding (mappage)
# ------------------------------
@dataclass(frozen=True)
class EventKey:
    """Clé de mappage normalisée pour un event MIDI."""
    type: str                   # 'note_on','note_off','control_change','pitchwheel', etc.
    channel: Optional[int]      # 0..15 ou None
    note: Optional[int] = None  # pour note_on/off
    control: Optional[int] = None  # pour CC
    value_bucket: Optional[str] = None  # ex: 'any', '0', '1-63', '64-127'...

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "channel": self.channel,
            "note": self.note,
            "control": self.control,
            "value_bucket": self.value_bucket,
        }

def bucket_value(val: int) -> str:
    """Regroupe optionnellement les valeurs (utile pour CC/pitch)."""
    # Exemples simples; tu peux adapter.
    if val in (0, 127):
        return str(val)
    if val < 64:
        return "1-63"
    return "64-126"

def event_to_key(msg: Message, granular: bool = True) -> EventKey:
    ch = msg.channel if hasattr(msg, "channel") else None
    if msg.type in ("note_on", "note_off"):
        # on peut vouloir ignorer note_off si velocity=0 (équivalent note_on vel=0)
        return EventKey(type=msg.type, channel=ch, note=msg.note)
    if msg.type == "control_change":
        vb = str(msg.value) if granular else bucket_value(msg.value)
        return EventKey(type="control_change", channel=ch, control=msg.control, value_bucket=vb)
    if msg.type == "pitchwheel":
        # Le pitchwheel a une large plage (-8192..8191); on bucketise.
        vb = "down" if msg.pitch < 0 else ("up" if msg.pitch > 0 else "zero")
        return EventKey(type="pitchwheel", channel=ch, value_bucket=vb)
    # Autres types si besoin
    return EventKey(type=msg.type, channel=ch)

# Actions supportées: shell / keystroke
def run_shell(command: str):
    import subprocess
    try:
        subprocess.Popen(command, shell=True)
    except Exception as e:
        print(f"[BIND] Erreur lancement commande: {e}")

def send_keystroke(key_str: str):
    if not _HAS_PYNPUT:
        print("[BIND] pynput n'est pas installé. `pip install pynput` pour les frappes clavier.")
        return
    kb = KBController()
    # Gestion de touches spéciales simples
    special = {
        "enter": Key.enter, "esc": Key.esc, "space": Key.space,
        "tab": Key.tab, "up": Key.up, "down": Key.down,
        "left": Key.left, "right": Key.right,
        "vol_up": Key.media_volume_up, "vol_down": Key.media_volume_down, "mute": Key.media_volume_mute,
        "play_pause": Key.media_play_pause, "next": Key.media_next, "prev": Key.media_previous,
    }
    k = special.get(key_str.lower(), key_str)
    try:
        kb.press(k)
        kb.release(k)
    except Exception as e:
        print(f"[BIND] Erreur envoi touche '{key_str}': {e}")

def load_bindings(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"rules": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_bindings(path: str, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def match_binding(key: EventKey, bindings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for rule in bindings.get("rules", []):
        rkey = rule.get("event", {})
        # Correspondance stricte sur type et channel (si défini)
        if rkey.get("type") != key.type:
            continue
        if rkey.get("channel", None) is not None and rkey.get("channel") != key.channel:
            continue
        # Spécificités par type
        if key.type in ("note_on", "note_off"):
            if rkey.get("note") is not None and rkey.get("note") != key.note:
                continue
        if key.type == "control_change":
            if rkey.get("control") is not None and rkey.get("control") != key.control:
                continue
            rv = rkey.get("value_bucket", "any")
            kv = key.value_bucket or "any"
            if rv != "any" and rv != kv:
                continue
        if key.type == "pitchwheel":
            rv = rkey.get("value_bucket", "any")
            kv = key.value_bucket or "any"
            if rv != "any" and rv != kv:
                continue
        return rule
    return None

def perform_action(rule: Dict[str, Any]):
    action = rule.get("action", {})
    atype = action.get("type")
    if atype == "shell":
        cmd = action.get("command")
        if cmd:
            print(f"[BIND] shell: {cmd}")
            run_shell(cmd)
    elif atype == "keystroke":
        key = action.get("key")
        if key:
            print(f"[BIND] keystroke: {key}")
            send_keystroke(key)
    else:
        print(f"[BIND] Type d'action non supporté: {atype}")

# ------------------------------
# Thread de capture
# ------------------------------
class MidiMonitor:
    def __init__(self, port_name: str, bindings_path: str):
        self.port_name = port_name
        self.stop_flag = threading.Event()
        self.bindings_path = bindings_path
        self.bindings = load_bindings(bindings_path)

    def reload_bindings(self):
        self.bindings = load_bindings(self.bindings_path)
        print("[INFO] Bindings rechargés.")

    def run(self):
        print(f"\n[INFO] Ouverture du port: {self.port_name}")
        with mido.open_input(self.port_name) as inport:
            print("[INFO] Affichage des événements (Ctrl+C pour quitter)")
            while not self.stop_flag.is_set():
                for msg in inport.iter_pending():
                    if not is_interesting(msg):
                        continue
                    # Affichage
                    print(format_event(msg))
                    # Matching de binding et action
                    key = event_to_key(msg, granular=True)
                    rule = match_binding(key, self.bindings)
                    if rule:
                        perform_action(rule)
                time.sleep(0.001)

    def stop(self):
        self.stop_flag.set()

# ------------------------------
# Mode Learn (apprentissage)
# ------------------------------
def learn_binding(port_name: str, bindings_path: str):
    print("\n=== MODE LEARN ===")
    print("Appuie sur UNE touche (note/CC/etc.) de ton clavier MIDI pour capturer l'événement.")
    print("Appuie sur Ctrl+C pour annuler.\n")
    with mido.open_input(port_name) as inport:
        while True:
            for msg in inport.iter_pending():
                if not is_interesting(msg):
                    continue
                print("Événement capturé:", format_event(msg))
                key = event_to_key(msg, granular=True)
                ek = key.to_dict()
                print("\nDéfinis l'action à associer à cet événement.")
                print("1) shell  (ex: lancer une appli ou un script)")
                print("2) keystroke (ex: 'space', 'enter', 'play_pause', 'vol_up')")
                try:
                    choice = input("Choix [1/2] : ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("Annulé.")
                    return
                if choice == "1":
                    cmd = input("Commande shell à exécuter : ").strip()
                    rule = {"event": ek, "action": {"type": "shell", "command": cmd}}
                elif choice == "2":
                    keyname = input("Nom de la touche : ").strip()
                    rule = {"event": ek, "action": {"type": "keystroke", "key": keyname}}
                else:
                    print("Choix invalide.")
                    return
                data = load_bindings(bindings_path)
                data.setdefault("rules", []).append(rule)
                save_bindings(bindings_path, data)
                print(f"[OK] Règle ajoutée à {bindings_path}")
                return
            time.sleep(0.01)

# ------------------------------
# Main
# ------------------------------
def main():
    ports = mido.get_input_names()
    if not ports:
        print("Aucun port MIDI détecté.")
        sys.exit(1)
    port_name = choose_port()

    print("\nCommandes disponibles pendant l'exécution :")
    print("  r + Entrée : recharger les bindings")
    print("  l + Entrée : passer en mode learn (apprentissage)")
    print("  q + Entrée : quitter\n")

    monitor = MidiMonitor(port_name, BINDINGS_FILE)
    t = threading.Thread(target=monitor.run, daemon=True)
    t.start()

    try:
        while True:
            cmd = input().strip().lower()
            if cmd == "q":
                break
            elif cmd == "r":
                monitor.reload_bindings()
            elif cmd == "l":
                learn_binding(port_name, BINDINGS_FILE)
            else:
                print("(Commande inconnue) r=reload, l=learn, q=quit")
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()
        t.join()
        print("Bye.")

if __name__ == "__main__":
    main()
