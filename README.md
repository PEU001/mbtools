
# mbtools — FULL PACKAGE (ULTRA-SAFE + Fallback RG + Scripts + Tests)

## Contenu
```
src/mbtools/            # package
  __main__.py           # permet: python -m mbtools
  mb_rating_tag.py      # CLI principale
  utils_mb.py           # HTTP ultra-safe (session+retry+throttle) + helpers
  cache.py              # cache SQLite
  exotic_cleanup.py     # nettoyage tags exotiques
  backup_restore.py     # backup / restore de tags
  report_html.py        # rapport HTML
scripts/
  run_mbtools.sh/.bat   # lance la CLI avec UA d'exemple
  check_compile.sh      # compile à blanc tous les modules
  sanitize_quotes.sh    # convertit les guillemets typographiques → ASCII
tests/
  test_mbtools.py       # tests unitaires (mock HTTP, offline)
tools/
  fix_quotes.py         # utilitaire de normalisation guillemets/espaces
requirements.txt
.env.example            # exemple de config UA + mode test
```

## Installation rapide
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scriptsctivate
pip install -r requirements.txt
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
```

## Lancer (exemple recommandé)
```bash
python -m mbtools   "/chemin/musique"   --ua "PierreTools/1.0 (pierre@example.com)"   --search-fallback   --cache
```

## Tests unitaires (offline)
Les tests **ne sollicitent pas l’API MusicBrainz** : ils *mockent* `_session.get` et forcent un throttle rapide.
```bash
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
export MBTOOLS_TEST_FAST=1
python -m unittest -v tests/test_mbtools.py
```

## Anti-erreurs de guillemets
Si vous avez copié/collé du code depuis un éditeur qui "typographie" les guillemets :
```bash
python tools/fix_quotes.py
```

## Notes
- MusicBrainz impose ~1 requête/seconde. L’outil applique 1.5 s + retries.
- Le fallback vers le **release-group** écrit `RATING_RG` et `MUSICBRAINZ_RG_*` pour ne pas confondre avec le rating piste.
- Le cache mémoire **évite** les appels redondants au sein d’un run; le cache SQLite évite de re‑questionner entre runs.
```
