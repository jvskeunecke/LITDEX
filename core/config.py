"""Caminhos e constantes. Tudo que o LitDex grava fica em data/ (ou em $LITDEX_DATA)."""
import os, sys
from pathlib import Path

if getattr(sys, "frozen", False):
    RAIZ = Path(sys.executable).resolve().parent
else:
    RAIZ = Path(__file__).resolve().parent.parent

DATA   = Path(os.environ.get("LITDEX_DATA") or (RAIZ / "data")).resolve()
LIB    = DATA / "library"      # arquivos das obras, por autor/obra
TMP    = DATA / "_tmp"         # leituras do scanner ainda não confirmadas
TRASH  = DATA / "_trash"       # nada é apagado de verdade
WEB    = RAIZ / "web"
VENDOR = WEB / "vendor"        # d3, MapLibre, marked… embutidos: nada a baixar, funciona offline
DB     = DATA / "litdex.db"
CONFIG = DATA / "config.json"

for _p in (DATA, LIB, TMP, TRASH):
    _p.mkdir(parents=True, exist_ok=True)

VENDOR_ESPERADOS = ("d3.min.js", "marked.umd.js", "purify.min.js", "topojson-client.min.js", "maplibre-gl.js", "maplibre-gl.css", "paises.geojson")
FORMATOS = {".pdf", ".docx", ".txt", ".md"}
IMAGENS  = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
GENEROS  = ("prosa", "verso")
