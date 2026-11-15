"""Arquivos: pasta temporária do scanner, biblioteca, área de entrada e lixeira.

O ciclo de uma edição tem duas fases, para que o banco e o disco não se contradigam:

  1. `estacionar()` move o upload de `_tmp` para `library/_incoming/` antes do INSERT;
  2. `promover()` move para `library/<autor>/<obra>/` depois do commit.

Se a promoção falhar, a linha do banco continua apontando para o arquivo estacionado —
o pesquisador não perde o documento e pode tentar de novo.
"""
import re
import shutil
import time
import uuid
from pathlib import Path

from . import config
from .erros import ErroDominio
from .texto import slug

ENTRADA = "library/_incoming"


def ext_imagem(nome):
    e = Path(nome or "").suffix.lower()
    return e if e in config.IMAGENS else ".jpg"     # nunca grava .html/.svg etc. na biblioteca


def nome_original(p):
    return re.sub(r"^[0-9a-f]{8}-", "", Path(p).name)


def tmp_valido(caminho):
    """Só mexe em arquivos da pasta _tmp — nunca em caminhos arbitrários vindos do navegador."""
    p = Path(caminho).resolve()
    if config.TMP.resolve() not in p.parents or not p.is_file():
        raise ErroDominio("arquivo temporário não encontrado (envie de novo)", 404)
    return p


def guardar_upload(arquivo):
    """Salva um upload em _tmp e devolve o caminho."""
    nome = Path(arquivo.filename or "arquivo").name
    tmp = config.TMP / f"{uuid.uuid4().hex[:8]}-{nome}"
    with tmp.open("wb") as f:
        shutil.copyfileobj(arquivo.file, f)
    return tmp


def estacionar(origem):
    """Move para a área de entrada da biblioteca (já visível em /arq) e devolve o caminho relativo."""
    destino = config.DATA / ENTRADA
    destino.mkdir(parents=True, exist_ok=True)
    alvo = destino / f"{uuid.uuid4().hex[:12]}-{nome_original(origem)}"
    shutil.move(str(origem), alvo)
    return relativo(alvo)


def promover(caminho_rel, autor_nome, titulo):
    """Move da área de entrada para a estante definitiva; devolve o caminho relativo final."""
    if not caminho_rel:
        return caminho_rel
    origem = config.DATA / caminho_rel
    if not origem.is_file():
        return caminho_rel
    d = config.LIB / slug(autor_nome or "anonimo") / slug(titulo or "sem-titulo")
    d.mkdir(parents=True, exist_ok=True)
    alvo = d / nome_original(origem)
    if alvo.exists():
        alvo = d / f"{alvo.stem}-{uuid.uuid4().hex[:6]}{alvo.suffix}"
    try:
        shutil.move(str(origem), alvo)
    except OSError:
        return caminho_rel
    return relativo(alvo)


def guardar(origem, autor_nome, titulo):
    """Move um arquivo para library/<autor>/<obra>/ (atalho de estacionar + promover)."""
    return config.DATA / promover(estacionar(origem), autor_nome, titulo)


def relativo(alvo):
    return Path(alvo).relative_to(config.DATA).as_posix()      # sempre '/', também no Windows


def novo_lote():
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"


def mover_para_lixo(caminho_rel, lote=None):
    """Nada é apagado: restaurar = mover data/_trash/<lote>/<caminho> de volta para data/<caminho>."""
    if not caminho_rel:
        return
    src = config.DATA / caminho_rel
    if not src.is_file():
        return
    dst = config.TRASH / (lote or novo_lote()) / caminho_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(src), dst)
    except OSError:
        pass


def limpar_tmp(horas=24):
    limite = time.time() - horas * 3600
    for f in config.TMP.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < limite:
                f.unlink()
        except OSError:
            pass


def seguro_em(base, caminho):
    """Resolve `caminho` dentro de `base` ou devolve None (impede ../)."""
    p = (Path(base) / str(caminho).replace("\\", "/")).resolve()
    return p if Path(base).resolve() in p.parents and p.is_file() else None


def paginas(caminho):
    """Número de páginas de um PDF (None para os outros formatos ou se falhar)."""
    if Path(caminho).suffix.lower() != ".pdf":
        return None
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(caminho)).pages)
    except Exception:
        return None
