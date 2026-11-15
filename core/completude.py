"""Cobertura de metadados e rastreabilidade documental são medidas separadas.

`pct`/`faltam` continuam compatíveis com a interface antiga, mas medem apenas a
cobertura de campos descritivos centrais. Imagem, tags, relações e anexos são
recursos de enriquecimento, não requisitos universais nem indicadores de confiança.
`documentacao` mede a presença de fonte identificável nos registros de evidência
associados à ficha; não avalia a qualidade ou a veracidade dessa fonte.
"""
from .db import lista


def _conjunto(c, sql):
    return {(r["t"], r["i"]) for r in c.execute(sql)}


def _evidencias(c, tipo, eid):
    """Retorna (registros com evidência textual, registros com fonte explícita)."""
    linhas = []
    if tipo in {"author", "work", "periodical", "event", "media", "institution"}:
        linhas.extend(c.execute("""SELECT fonte,notas FROM relations
            WHERE (origem_tipo=? AND origem_id=?) OR (destino_tipo=? AND destino_id=?)""",
            (tipo, eid, tipo, eid)).fetchall())
    if tipo == "author":
        linhas.extend(c.execute("SELECT fonte,notas FROM work_agents WHERE author_id=?", (eid,)).fetchall())
        linhas.extend(c.execute("SELECT fonte,notas FROM manifestation_agents WHERE author_id=?", (eid,)).fetchall())
        linhas.extend(c.execute("""SELECT m.fonte,m.notas FROM manifestations m
            JOIN work_agents wa ON wa.work_id=m.work_id AND wa.author_id=?""", (eid,)).fetchall())
    elif tipo == "work":
        linhas.extend(c.execute("SELECT fonte,notas FROM manifestations WHERE work_id=?", (eid,)).fetchall())
        linhas.extend(c.execute("SELECT fonte,notas FROM work_agents WHERE work_id=?", (eid,)).fetchall())
        linhas.extend(c.execute("""SELECT ma.fonte,ma.notas FROM manifestation_agents ma
            JOIN manifestations m ON m.id=ma.manifestation_id WHERE m.work_id=?""", (eid,)).fetchall())
    elif tipo == "periodical":
        linhas.extend(c.execute("SELECT referencia,notas FROM periodical_issues WHERE periodical_id=?", (eid,)).fetchall())
        linhas.extend(c.execute("SELECT fonte,notas FROM manifestations WHERE periodical_id=?", (eid,)).fetchall())
    # Evidências canônicas podem sustentar afirmações sem duplicar a fonte em
    # cada relação/ficha. source_id é a referência rastreável ao catálogo sources.
    linhas.extend(c.execute("SELECT source_id AS fonte, trecho AS notas FROM evidences WHERE entidade_tipo=? AND entidade_id=?", (tipo, eid)).fetchall())
    total = len(linhas)
    com_fonte = sum(1 for r in linhas if "fonte" in r.keys() and str(r["fonte"] or "").strip())
    # Algumas tabelas usam `referencia` em vez de `fonte` (fascículos).
    com_fonte += sum(1 for r in linhas if "referencia" in r.keys() and str(r["referencia"] or "").strip())
    return total, min(total, com_fonte)


def calcular_todos(c):
    """Retorna cobertura descritiva, enriquecimento opcional e rastreabilidade por ficha."""
    tags = _conjunto(c, "SELECT entity_tipo t, entity_id i FROM entity_tags")
    lugares = _conjunto(c, "SELECT entity_tipo t, entity_id i FROM entity_places")
    rels = _conjunto(c, "SELECT origem_tipo t, origem_id i FROM relations UNION SELECT destino_tipo, destino_id FROM relations")
    obras_de = {r["a"] for r in c.execute(
        "SELECT DISTINCT author_id a FROM work_agents WHERE papel IN ('autor_principal','coautor')")}
    arquivo = {r["w"] for r in c.execute("SELECT DISTINCT work_id w FROM manifestations WHERE caminho<>''")}
    editora = {r["w"] for r in c.execute("SELECT DISTINCT work_id w FROM manifestations WHERE editora IS NOT NULL AND editora<>''")}
    midias = {r["w"] for r in c.execute("SELECT DISTINCT work_id w FROM work_media")}
    generos = {r["w"] for r in c.execute("SELECT DISTINCT work_id w FROM work_genres")}
    autores_da_obra = {r["w"] for r in c.execute("SELECT DISTINCT work_id w FROM work_agents WHERE papel IN ('autor_principal','coautor')")}
    em_midia = {r["m"] for r in c.execute("SELECT DISTINCT media_id m FROM work_media")}
    pref = lambda v: bool(str(v or "").strip())
    out = {}

    def fechar(tipo, i, centrais, enriquecimento):
        feitos = [n for n, ok in centrais if ok]
        extras_feitos = [n for n, ok in enriquecimento if ok]
        total_ev, com_fonte = _evidencias(c, tipo, i)
        ev_alvo = c.execute("SELECT COUNT(*) FROM evidences WHERE entidade_tipo=? AND entidade_id=? AND alvo_tipo IS NOT NULL AND alvo_id IS NOT NULL", (tipo, i)).fetchone()[0]
        out[(tipo, i)] = {
            "pct": round(100 * len(feitos) / len(centrais)) if centrais else 100,
            "faltam": [n for n, ok in centrais if not ok],
            "total": len(centrais),
            "pct_enriquecimento": round(100 * len(extras_feitos) / len(enriquecimento)) if enriquecimento else 100,
            "faltam_enriquecimento": [n for n, ok in enriquecimento if not ok],
            "documentacao": {"registros_associados": total_ev, "registros_com_fonte": com_fonte,
                             "pct_com_fonte": round(100 * com_fonte / total_ev) if total_ev else None,
                             "evidencias_vinculadas_a_afirmacao": ev_alvo,
                             "evidencias_apenas_associadas_a_entidade": max(0, total_ev - ev_alvo),
                             "estatuto": "rastreabilidade; não é avaliação de veracidade"}
        }

    for r in lista(c, "SELECT * FROM authors"):
        k = ("author", r["id"])
        fechar(*k, [("nascimento", pref(r["nascimento"])), ("morte", pref(r["morte"])), ("biografia", pref(r["bio"]))],
               [("tags", k in tags), ("imagem", pref(r["imagem"])), ("obras vinculadas", r["id"] in obras_de), ("lugares", k in lugares), ("relações explícitas", k in rels)])
    for r in lista(c, "SELECT * FROM works"):
        k = ("work", r["id"])
        fechar(*k, [("autor ou autoria não identificada", r["id"] in autores_da_obra),
                    ("ano", pref(r["ano"])), ("gênero", pref(r["genero"]) or r["id"] in generos), ("tipo / forma", pref(r["tipo"]))],
               [("mídia", r["id"] in midias), ("arquivo digital", r["id"] in arquivo), ("editora", r["id"] in editora),
                ("notas", pref(r["notas"])), ("tags", k in tags), ("capa", pref(r["imagem"])), ("relações entre obras", k in rels)])
    for r in lista(c, "SELECT * FROM periodicals"):
        k = ("periodical", r["id"])
        fechar(*k, [("tipo", pref(r["tipo"])), ("início de circulação", pref(r["ano_inicio"])), ("ISSN", pref(r["issn"]))],
               [("lugar", k in lugares), ("notas", pref(r["notas"])), ("imagem", pref(r["imagem"])), ("relações explícitas", k in rels)])
    for r in lista(c, "SELECT * FROM events"):
        k = ("event", r["id"])
        fechar(*k, [("tipo", pref(r["tipo"])), ("data", pref(r["ano"]))],
               [("lugar", k in lugares), ("notas", pref(r["notas"])), ("relações explícitas", k in rels)])
    for r in lista(c, "SELECT * FROM media"):
        k = ("media", r["id"])
        fechar(*k, [("obras vinculadas", r["id"] in em_midia or k in rels)], [("notas", pref(r["notas"]))])
    for r in lista(c, "SELECT * FROM institutions"):
        k = ("institution", r["id"])
        fechar(*k, [("tipo", pref(r["tipo"]))], [("fundação", pref(r["fundacao"])), ("local", pref(r["local"])), ("notas", pref(r["notas"])), ("relações explícitas", k in rels)])
    return out
