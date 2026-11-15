"""Catálogo (início), Biblioteca (estantes), lista unificada de fichas e online por ficha."""
from collections import defaultdict
from fastapi import APIRouter, Body, HTTPException, Request
from core import completude, online
from core import entidades as E
from core.db import conn, lista
from core.texto import normalizar
from core.vocab import ENTIDADES
from .cadastros import _SQL_LISTA, _sub, montar_ficha
from .comum import perfil_ativo

router = APIRouter(prefix="/api")

@router.get("/fichas")
def fichas(request: Request, q: str = "", tipos: str = ""):
    """TODAS as fichas de uma vez (autores, obras, periódicos, eventos, mídias), com a completude de cada uma."""
    pid = perfil_ativo(request); quer = [t for t in ENTIDADES if not tipos or t in tipos.split(",")]; alvo = normalizar(q); out = []
    with conn() as c:
        comp = completude.calcular_todos(c)
        for t in quer:
            ids = E.ids_do_perfil(c, pid, t)
            for r in lista(c, _SQL_LISTA[t]):
                if (ids is not None and r["id"] not in ids) or (alvo and alvo not in normalizar(r["nome"] + " " + _sub(t, r))): continue
                cp = comp.get((t, r["id"]), {"pct": 0, "faltam": []})
                out.append({"tipo": t, "id": r["id"], "nome": r["nome"], "sub": _sub(t, r), "pct": cp["pct"], "faltam": cp["faltam"],
                            "pct_enriquecimento": cp.get("pct_enriquecimento", 100), "faltam_enriquecimento": cp.get("faltam_enriquecimento", []),
                            "documentacao": cp.get("documentacao", {"registros_associados": 0, "registros_com_fonte": 0, "pct_com_fonte": None})})
    ordem = list(ENTIDADES)
    return sorted(out, key=lambda x: (ordem.index(x["tipo"]), normalizar(x["nome"])))

@router.get("/catalogo")
def catalogo(request: Request):
    """Números do início: o quanto da dex está preenchido, o que entrou por último e o que falta pouco para completar."""
    pid = perfil_ativo(request)
    with conn() as c:
        comp = completude.calcular_todos(c); itens = []
        contagem, recentes = {}, []
        for t, e in ENTIDADES.items():
            ids = E.ids_do_perfil(c, pid, t); tabela = E.ENT[t]["tabela"]; nome = E.ENT[t]["nome"]
            rows = lista(c, f"SELECT id,{nome} AS nome,criado_em FROM {tabela}")
            rows = [r for r in rows if ids is None or r["id"] in ids]; contagem[t] = len(rows)
            for r in rows:
                cp = comp.get((t, r["id"]), {"pct": 0, "faltam": []})
                itens.append({"tipo": t, "id": r["id"], "nome": r["nome"], "pct": cp["pct"], "faltam": cp["faltam"],
                              "pct_enriquecimento": cp.get("pct_enriquecimento", 100), "documentacao": cp.get("documentacao")})
                recentes.append({"tipo": t, "id": r["id"], "nome": r["nome"], "pct": cp["pct"], "quando": r["criado_em"] or ""})
        arquivos = c.execute("SELECT COUNT(*) FROM manifestations WHERE caminho<>''").fetchone()[0]
        relacoes = c.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        lugares = c.execute("SELECT COUNT(DISTINCT place_id) FROM entity_places").fetchone()[0]
    media = round(sum(i["pct"] for i in itens) / len(itens)) if itens else 0
    falta_pouco = sorted((i for i in itens if i["pct"] < 100), key=lambda i: -i["pct"])[:6]
    docs = [i.get("documentacao") or {} for i in itens]
    docs_total = sum(int(d.get("registros_associados") or 0) for d in docs)
    docs_fontes = sum(int(d.get("registros_com_fonte") or 0) for d in docs)
    documentacao = {"registros_associados": docs_total, "registros_com_fonte": docs_fontes,
                    "pct_com_fonte": round(100 * docs_fontes / docs_total) if docs_total else None,
                    "estatuto": "rastreabilidade; não é avaliação de veracidade"}
    return {"contagem": contagem, "arquivos": arquivos, "relacoes": relacoes, "lugares": lugares, "media": media,
            "documentacao": documentacao,
            "completas": sum(1 for i in itens if i["pct"] >= 90), "total": len(itens),
            "recentes": sorted(recentes, key=lambda x: (x["quando"], x["id"]), reverse=True)[:8], "falta_pouco": falta_pouco}

@router.get("/biblioteca")
def biblioteca(request: Request, q: str = ""):
    """Estantes por autor; cada livro com capa, mídias, tags e as edições/arquivos que podem ser abertos."""
    pid = perfil_ativo(request); alvo = normalizar(q)
    with conn() as c:
        comp = completude.calcular_todos(c)
        ids_o, ids_a = E.ids_do_perfil(c, pid, "work"), E.ids_do_perfil(c, pid, "author")
        obras = [w for w in lista(c, """SELECT w.*, a.nome AS autor_nome,
                                  (SELECT wa.author_id FROM work_agents wa WHERE wa.work_id=w.id
                                   AND wa.papel='autor_principal' ORDER BY wa.ordem, wa.id LIMIT 1) AS autor_principal_id
                                  FROM works w LEFT JOIN authors a ON a.id=(SELECT wa.author_id FROM work_agents wa
                                   WHERE wa.work_id=w.id AND wa.papel='autor_principal' ORDER BY wa.ordem, wa.id LIMIT 1)
                                  ORDER BY (w.ano_num IS NULL), w.ano_num, w.titulo""")
                 if (ids_o is None or w["id"] in ids_o) and (not alvo or alvo in normalizar(f"{w['titulo']} {w['autor_nome'] or ''}"))]
        edicoes, midias, tags, generos, agentes = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
        for r in lista(c, """SELECT m.*,i.volume AS fasciculo_volume,i.numero AS fasciculo_numero,
                                  i.data AS fasciculo_data,i.titulo AS fasciculo_titulo,p.titulo AS periodico,
                                  (SELECT GROUP_CONCAT(a.nome || ' (' || ma.papel || ')','; ')
                                     FROM manifestation_agents ma JOIN authors a ON a.id=ma.author_id
                                     WHERE ma.manifestation_id=m.id) AS creditos_manifestacao
                           FROM manifestations m LEFT JOIN periodical_issues i ON i.id=m.issue_id
                           LEFT JOIN periodicals p ON p.id=m.periodical_id
                           ORDER BY (m.ed_num IS NULL),m.ed_num,m.id"""):
            edicoes[r["work_id"]].append(r)
        for r in lista(c, "SELECT wa.work_id,a.id AS author_id,a.nome,wa.papel FROM work_agents wa JOIN authors a ON a.id=wa.author_id ORDER BY wa.ordem,wa.id"):
            agentes[r["work_id"]].append({"id": r["author_id"], "nome": r["nome"], "papel": r["papel"]})
        for r in lista(c, "SELECT wm.work_id w, m.nome FROM work_media wm JOIN media m ON m.id=wm.media_id ORDER BY wm.ordem"): midias[r["w"]].append(r["nome"])
        for r in lista(c, "SELECT et.entity_id w, t.nome FROM entity_tags et JOIN tags t ON t.id=et.tag_id WHERE et.entity_tipo='work'"): tags[r["w"]].append(r["nome"])
        termos = {g["id"]: g for g in lista(c, "SELECT id,nome,parent_id FROM genre_terms")}
        for r in lista(c, "SELECT wg.work_id w,g.id,g.nome,g.parent_id FROM work_genres wg JOIN genre_terms g ON g.id=wg.genre_id ORDER BY wg.ordem,g.nome"):
            atual = r; vistos = set()
            while atual and atual["id"] not in vistos:
                vistos.add(atual["id"])
                generos[r["w"]].append(atual["nome"])
                atual = termos.get(atual["parent_id"])
        autores = {a["id"]: a for a in lista(c, "SELECT id,nome,nascimento,morte,imagem FROM authors")}
    estantes, por_autor = [], {}
    for w in obras:
        todos_generos = sorted(set(([w["genero"]] if w["genero"] else []) + generos[w["id"]]), key=normalizar)
        item = {"id": w["id"], "titulo": w["titulo"], "ano": w["ano"], "genero": w["genero"], "generos": todos_generos, "tipo": w["tipo"], "imagem": w["imagem"],
                "midias": midias[w["id"]], "tags": tags[w["id"]], "agentes": agentes[w["id"]], "pct": comp.get(("work", w["id"]), {}).get("pct", 0),
                "edicoes": [{k: e.get(k) for k in ("id", "caminho", "formato", "editora", "ano_edicao", "local", "fonte", "paginas", "issue_id", "tipo_aparicao", "referencia", "periodico", "fasciculo_volume", "fasciculo_numero", "fasciculo_data", "fasciculo_titulo", "creditos_manifestacao")} for e in edicoes[w["id"]]]}
        k = w["autor_principal_id"]
        if k not in por_autor:
            a = autores.get(k); por_autor[k] = {"autor": ({**a, "pct": comp.get(("author", k), {}).get("pct", 0)} if a else None), "obras": []}
            estantes.append(por_autor[k])
        por_autor[k]["obras"].append(item)
    estantes.sort(key=lambda e: (e["autor"] is None, normalizar((e["autor"] or {}).get("nome", ""))))
    todas = [o for e in estantes for o in e["obras"]]
    return {"estantes": estantes, "total": len(todas),
            "filtros": {"generos": sorted({g for o in todas for g in o["generos"]}), "tipos": sorted({o["tipo"] for o in todas if o["tipo"]}),
                        "midias": sorted({m for o in todas for m in o["midias"]}), "tags": sorted({t for o in todas for t in o["tags"]})}}

@router.post("/online/ficha")
def online_ficha(dados: dict = Body(...)):
    """Reconhecimento e preenchimento online para QUALQUER ficha: devolve cartões de sugestão (com a fonte)."""
    if not online.ativo(): raise HTTPException(403, "o módulo online está desligado (ative em Diagnóstico ou no botão da ficha)")
    tipo, eid = dados.get("tipo"), int(dados.get("id", 0))
    with conn() as c:
        E.exigir(c, tipo, eid); f = montar_ficha(c, tipo, eid)
    try: return online.sugerir(tipo, f)
    except online.OnlineErro as e: raise HTTPException(502, str(e))
