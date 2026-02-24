
# fix_quotes.py — normalise guillemets et espaces dans tous les .py du dossier courant
import pathlib

MAP = {
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'", "‛": "'", "′": "'", "″": '"',
    " ": " ", " ": " ", " ": " ", " ": " ", "​": ""
}

def sanitize(text: str) -> str:
    for k, v in MAP.items():
        text = text.replace(k, v)
    text = text.replace("
", "
").replace("", "
")
    return text

for p in pathlib.Path('.').glob('*.py'):
    t = p.read_text(encoding='utf-8', errors='replace')
    t2 = sanitize(t)
    if t2 != t:
        p.write_text(t2, encoding='utf-8')
        print(f"[fixed] {p}")
print('Terminé')
