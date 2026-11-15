"""Fichário: listar, criar, ler, editar e apagar as entidades; tags, lugares, imagens,
edições (manifestações), créditos e mídias das obras."""
import sqlite3
from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from core import config, files, geo, online
from core import entidades as E
from core.db import conn, lista, um
from core.evidencias import marcar_revisao
from core.relacoes import relacoes_de
from core.datas import ano_num
from core.texto import normalizar, slug
from .comum import perfil_ativo

router = APIRouter(prefix="/api")

# Autoria é derivada de work_agents; esta subconsulta é a única forma de ler
# "quem é o autor principal" e substitui a antiga coluna works.author_id.
AUTOR = ("(SELECT wa.author_id FROM work_agents wa WHERE wa.work_id=w.id "
         "AND wa.papel='autor_principal' ORDER BY wa.ordem, wa.id LIMIT 1)")

# ------------------------------------------------------------------ listar / criar
def _sub(tipo, r):
    if tipo == "author": return "–".join(x for x in (r.get("nascimento") or "", r.get("morte") or "")) if (r.get("nascimento") or r.get("morte")) else ""
    if tipo == "work": return " · ".join(x for x in (r.get("autor"), r.get("ano")) if x)
    if tipo == "periodical": return " · ".join(x for x in (r.get("tipo"), "–".join(y for y in (r.get("ano_inicio"), r.get("ano_fim")) if y)) if x)
    if tipo == "event": return " · ".join(x for x in (r.get("tipo"), r.get("ano")) if x)
    if tipo == "institution": return " · ".join(x for x in (r.get("tipo"), r.get("local")) if x)
    return ""

_SQL_LISTA = {
    "author": "SELECT id,nome,nascimento,morte FROM authors",
    "work": f"SELECT w.id,w.titulo AS nome,w.ano,a.nome AS autor FROM works w LEFT JOIN authors a ON a.id={AUTOR}",
    "periodical": "SELECT id,titulo AS nome,tipo,ano_inicio,ano_fim FROM periodicals",
    "event": "SELECT id,nome,tipo,ano FROM events",
    "media": "SELECT id,nome FROM media",
    "institution": "SELECT id,nome,tipo,local FROM institutions",
}

@router.get("/entidades/{tipo}")
def listar(tipo: str, request: Request, q: str = "", todos: int = 0):
    E.ent(tipo); pid = None if todos else perfil_ativo(request)
    with conn() as c:
        ids = E.ids_do_perfil(c, pid, tipo)
        rows = lista(c, _SQL_LISTA[tipo])
    alvo = normalizar(q)
    out = [{"id": r["id"], "nome": r["nome"], "sub": _sub(tipo, r)} for r in rows
           if (ids is None or r["id"] in ids) and (not alvo or alvo in normalizar(r["nome"]))]
    return sorted(out, key=lambda x: normalizar(x["nome"]))

@router.post("/entidades/{tipo}")
def criar(tipo: str, request: Request, dados: dict = Body(...)):
    e = E.ent(tipo)
    campos = E.preparar_campos(tipo, dados)
    pid = perfil_ativo(request)
    if e["nome"] not in campos:
        raise HTTPException(400, "informe o nome")
    # autoria chega como campo virtual (author_id) e vira participação canônica
    autor_id = dados.get("author_id") or dados.get("autor_principal")
    with conn() as c:
        if tipo == "media":
            ex = next((r for r in c.execute("SELECT id,nome FROM media")
                       if normalizar(r["nome"]) == normalizar(campos["nome"])), None)
            if ex:
                E.anexar_perfil(c, pid, "media", ex["id"])
                return {"id": ex["id"], "existente": True}
        if tipo == "work" and autor_id:
            E.exigir(c, "author", int(autor_id))
        cur = c.execute(f"INSERT INTO {e['tabela']}({', '.join(campos)}) "
                        f"VALUES({', '.join('?' * len(campos))})", tuple(campos.values()))
        novo_id = cur.lastrowid
        if tipo == "work" and autor_id:
            E.definir_autor_principal(c, novo_id, int(autor_id))
        E.anexar_perfil(c, pid, tipo, novo_id)
        return {"id": novo_id}

# ------------------------------------------------------------------ ficha
def montar_ficha(c, tipo, eid):
    e = E.ent(tipo)
    r = um(c, f"SELECT * FROM {e['tabela']} WHERE id=?", (eid,))
    if not r: raise HTTPException(404, "ficha não encontrada")
    r["_tipo"], r["_nome"] = tipo, r[e["nome"]]
    r["tags"] = lista(c, """SELECT t.id,t.nome FROM tags t JOIN entity_tags et ON et.tag_id=t.id
                            WHERE et.entity_tipo=? AND et.entity_id=? ORDER BY t.nome""", (tipo, eid))
    r["lugares"] = lista(c, """SELECT p.id,p.nome,p.lat,p.lon,p.tipo,p.contexto,p.parent_id,p.notas,ep.papel
                               FROM places p JOIN entity_places ep ON ep.place_id=p.id
                               WHERE ep.entity_tipo=? AND ep.entity_id=? ORDER BY ep.ordem,p.id""", (tipo, eid))
    for lugar in r["lugares"]:
        lugar["caminho"] = _caminho_lugar(c, lugar["id"])
    r["assets"] = lista(c, "SELECT * FROM assets WHERE entity_tipo=? AND entity_id=? ORDER BY ordem,id", (tipo, eid))
    r["perfis"] = [x["profile_id"] for x in c.execute(
        "SELECT profile_id FROM profile_items WHERE entity_tipo=? AND entity_id=?", (tipo, eid))]
    r["relacoes"] = relacoes_de(c, tipo, eid)
    r["evidencias"] = lista(c, """SELECT e.*,s.titulo AS fonte_titulo,s.url AS fonte_url
                                  FROM evidences e LEFT JOIN sources s ON s.id=e.source_id
                                  WHERE e.entidade_tipo=? AND e.entidade_id=? ORDER BY e.id""", (tipo, eid))
    if tipo == "work":
        r["evidencias_manifestacoes"] = lista(c, """SELECT e.*,s.titulo AS fonte_titulo,s.url AS fonte_url,
                                                    m.id AS manifestacao_id
                                                    FROM evidences e
                                                    LEFT JOIN sources s ON s.id=e.source_id
                                                    JOIN manifestations m ON m.id=e.entidade_id
                                                    WHERE e.entidade_tipo='manifestation' AND m.work_id=?
                                                    ORDER BY e.id""", (eid,))
    arq = "(SELECT caminho FROM manifestations m WHERE m.work_id=w.id AND m.caminho<>'' ORDER BY m.id LIMIT 1)"
    if tipo == "author":
        r["obras"] = lista(c, f"""SELECT DISTINCT w.id,w.titulo,w.ano,w.tipo,w.genero,{arq} AS arquivo,
                                  wa.papel FROM works w JOIN work_agents wa ON wa.work_id=w.id
                                  WHERE wa.author_id=? AND wa.papel IN ('autor_principal','coautor')
                                  ORDER BY (w.ano_num IS NULL), w.ano_num, w.titulo""", (eid,))
        r["participacoes"] = lista(c, """SELECT wa.id,wa.work_id,w.titulo,wa.papel,wa.ano,wa.fonte,wa.notas
                                          FROM work_agents wa JOIN works w ON w.id=wa.work_id
                                          WHERE wa.author_id=? ORDER BY w.titulo,wa.papel""", (eid,))
        r["participacoes_manifestacoes"] = lista(c, """SELECT ma.id,ma.manifestation_id,m.work_id,w.titulo,m.tipo_aparicao,m.ano_edicao,
                                                                 m.referencia,m.periodical_id,p.titulo AS periodico,ma.papel,ma.fonte,ma.notas
                                                          FROM manifestation_agents ma JOIN manifestations m ON m.id=ma.manifestation_id
                                                          JOIN works w ON w.id=m.work_id LEFT JOIN periodicals p ON p.id=m.periodical_id
                                                          WHERE ma.author_id=? ORDER BY w.titulo,(m.ed_num IS NULL),m.ed_num,m.id,ma.ordem""", (eid,))
    elif tipo == "work":
        autor = E.autor_principal(c, eid)
        r["author_id"] = autor
        r["author_nome"] = (um(c, "SELECT nome FROM authors WHERE id=?", (autor,)) or {}).get("nome") if autor else None
        r["agentes"] = lista(c, """SELECT wa.id,wa.author_id,a.nome,wa.papel,wa.ordem,wa.ano,wa.fonte,wa.notas
                                    FROM work_agents wa JOIN authors a ON a.id=wa.author_id
                                    WHERE wa.work_id=? ORDER BY wa.ordem,wa.id""", (eid,))
        r["edicoes"] = lista(c, """SELECT m.*,p.titulo AS periodico_titulo, cw.titulo AS obra_continente_titulo,
                                  i.volume AS fasciculo_volume,i.numero AS fasciculo_numero,i.data AS fasciculo_data,
                                  i.titulo AS fasciculo_titulo,cm.work_id AS obra_continente_id, cwork.titulo AS obra_contida_na_edicao
                                  FROM manifestations m
                                  LEFT JOIN periodicals p ON p.id=m.periodical_id
                                  LEFT JOIN works cw ON cw.id=m.container_work_id
                                  LEFT JOIN periodical_issues i ON i.id=m.issue_id
                                  LEFT JOIN manifestations cm ON cm.id=m.container_manifestation_id
                                  LEFT JOIN works cwork ON cwork.id=cm.work_id
                                  WHERE m.work_id=? ORDER BY (m.ed_num IS NULL), m.ed_num, m.id""", (eid,))
        r["agentes_manifestacao"] = lista(c, """SELECT ma.manifestation_id,ma.author_id,a.nome,ma.papel,ma.ordem,ma.fonte,ma.notas
                                             FROM manifestation_agents ma JOIN authors a ON a.id=ma.author_id
                                             JOIN manifestations m ON m.id=ma.manifestation_id WHERE m.work_id=?
                                             ORDER BY ma.manifestation_id,ma.ordem""", (eid,))
        r["generos_especificos"] = _generos_da_obra(c, eid)
        r["midias"] = lista(c, """SELECT m.id,m.nome FROM media m JOIN work_media wm ON wm.media_id=m.id
                                  WHERE wm.work_id=? ORDER BY wm.ordem,m.id""", (eid,))
    elif tipo == "periodical":
        r["obras"] = lista(c, f"""SELECT w.id,w.titulo,w.ano,a.nome AS autor,
            m.referencia, m.ano_edicao AS ano_pub, m.id AS manifestacao_id, m.tipo_aparicao,
            m.issue_id,i.volume AS fasciculo_volume,i.numero AS fasciculo_numero,i.data AS fasciculo_data,
            ma.agentes_manifestacao
            FROM manifestations m JOIN works w ON m.work_id=w.id
            LEFT JOIN authors a ON a.id={AUTOR} LEFT JOIN periodical_issues i ON i.id=m.issue_id
            LEFT JOIN (SELECT ma.manifestation_id,GROUP_CONCAT(a.nome || ' (' || ma.papel || ')', '; ') AS agentes_manifestacao
                       FROM manifestation_agents ma JOIN authors a ON a.id=ma.author_id GROUP BY ma.manifestation_id) ma ON ma.manifestation_id=m.id
            WHERE m.periodical_id=? ORDER BY (COALESCE(i.data_num,m.ed_num) IS NULL), COALESCE(i.data_num,m.ed_num), w.titulo, m.id""", (eid,))
        r["fasciculos"] = lista(c, """SELECT i.*, COUNT(m.id) AS manifestacoes FROM periodical_issues i
                                        LEFT JOIN manifestations m ON m.issue_id=i.id
                                        WHERE i.periodical_id=? GROUP BY i.id
                                        ORDER BY (i.data_num IS NULL),i.data_num,i.volume,i.numero,i.id""", (eid,))
        r["colaboradores"] = lista(c, """SELECT a.id,a.nome,r.tipo AS papel FROM relations r JOIN authors a ON r.origem_tipo='author' AND r.origem_id=a.id
            WHERE r.tipo IN ('colaborou_em','editou','fundou') AND r.destino_tipo='periodical' AND r.destino_id=? ORDER BY a.nome""", (eid,))
    elif tipo == "event":
        r["participantes"] = lista(c, """SELECT a.id,a.nome FROM relations r JOIN authors a ON r.origem_tipo='author' AND r.origem_id=a.id
            WHERE r.tipo='participou' AND r.destino_tipo='event' AND r.destino_id=? ORDER BY a.nome""", (eid,))
        r["obras"] = lista(c, """SELECT w.id,w.titulo FROM relations r JOIN works w ON r.origem_tipo='work' AND r.origem_id=w.id
            WHERE r.tipo='apresentada_em' AND r.destino_tipo='event' AND r.destino_id=?""", (eid,))
    elif tipo == "media":
        r["obras"] = lista(c, f"""SELECT w.id,w.titulo,a.nome AS autor FROM works w JOIN work_media wm ON wm.work_id=w.id
                                 LEFT JOIN authors a ON a.id={AUTOR} WHERE wm.media_id=? ORDER BY w.titulo""", (eid,))
        r["referenciada_em"] = lista(c, """SELECT w.id,w.titulo,r.tipo FROM relations r JOIN works w ON r.origem_tipo='work' AND r.origem_id=w.id
                                           WHERE r.destino_tipo='media' AND r.destino_id=?""", (eid,))
    return r

@router.get("/entidades/{tipo}/{eid}")
def ficha(tipo: str, eid: int):
    with conn() as c: return montar_ficha(c, tipo, eid)


@router.get("/manifestacoes")
def listar_manifestacoes(request: Request, todos: int = 0, excluir_obra: int | None = None):
    """Índice de aparições documentais para vincular uma manifestação a uma edição concreta.

    Não cria cópias de obras. Cada item é uma manifestação já cadastrada, com seu
    identificador próprio, e pode ser filtrada do seletor por obra ou perfil.
    """
    with conn() as c:
        rows = lista(c, """SELECT m.id,m.work_id,w.titulo AS obra,m.tipo_aparicao,m.ano_edicao,
                                  m.periodical_id,p.titulo AS periodico,m.referencia,m.issue_id,
                                  i.volume AS fasciculo_volume,i.numero AS fasciculo_numero,
                                  i.data AS fasciculo_data,i.titulo AS fasciculo_titulo
                           FROM manifestations m JOIN works w ON w.id=m.work_id
                           LEFT JOIN periodicals p ON p.id=m.periodical_id
                           LEFT JOIN periodical_issues i ON i.id=m.issue_id
                           ORDER BY (COALESCE(i.data_num,m.ed_num) IS NULL),COALESCE(i.data_num,m.ed_num),w.titulo,m.id""")
        ids = E.ids_do_perfil(c, perfil_ativo(request), "work")
        out = []
        for r in rows:
            if excluir_obra is not None and r["work_id"] == excluir_obra: continue
            if not todos and ids is not None and r["work_id"] not in ids: continue
            out.append(r)
        return out

@router.patch("/entidades/{tipo}/{eid}")
def editar(tipo: str, eid: int, dados: dict = Body(...)):
    e = E.ent(tipo)
    campos = E.preparar_campos(tipo, dados)
    muda_autor = tipo == "work" and ("author_id" in dados or "autor_principal" in dados)
    if not campos and not muda_autor:
        return {"ok": True}
    with conn() as c:
        E.exigir(c, tipo, eid)
        try:
            if campos:
                c.execute(f"UPDATE {e['tabela']} SET {', '.join(f'{k}=?' for k in campos)} WHERE id=?",
                          (*campos.values(), eid))
            if muda_autor:
                bruto = dados.get("author_id", dados.get("autor_principal"))
                try:
                    novo = int(bruto) if bruto not in (None, "") else None
                except (TypeError, ValueError):
                    raise HTTPException(400, "autor inválido")
                antigo = E.autor_principal(c, eid)
                if novo != antigo:
                    linha_antiga = c.execute(
                        "SELECT id FROM work_agents WHERE work_id=? AND papel='autor_principal'",
                        (eid,)).fetchone()
                    ja_existia = c.execute(
                        "SELECT id FROM work_agents WHERE work_id=? AND author_id=?",
                        (eid, novo)).fetchone() if novo is not None else None
                    E.definir_autor_principal(c, eid, novo)
                    if linha_antiga:
                        # a afirmação de autoria mudou: a evidência antiga precisa ser reconfirmada
                        marcar_revisao(c, "work_agent", [linha_antiga["id"]],
                                       "O autor principal da obra foi alterado; confirme se a evidência "
                                       "ainda sustenta a nova autoria.")
                    if ja_existia:
                        marcar_revisao(c, "work_agent", [ja_existia["id"]],
                                       "O papel desta pessoa na obra mudou para autor principal; "
                                       "reveja a evidência vinculada.")
        except sqlite3.IntegrityError:
            raise HTTPException(409, "já existe uma ficha com esse nome")
    return {"ok": True}

@router.delete("/entidades/{tipo}/{eid}")
def apagar(tipo: str, eid: int):
    with conn() as c:
        E.exigir(c, tipo, eid)
        extra = {}
        if tipo == "author":
            extra["obras_sem_autor"] = c.execute(
                "SELECT COUNT(*) FROM work_agents WHERE author_id=? AND papel='autor_principal'", (eid,)).fetchone()[0]
        E.limpar(c, tipo, eid)
    return {"ok": True, **extra}

# ------------------------------------------------------------------ tags
@router.get("/tags")
def todas_tags():
    with conn() as c:
        return lista(c, """SELECT t.id,t.nome,COUNT(et.entity_id) AS n FROM tags t
                           LEFT JOIN entity_tags et ON et.tag_id=t.id GROUP BY t.id ORDER BY t.nome""")

@router.post("/entidades/{tipo}/{eid}/tags")
def add_tag(tipo: str, eid: int, dados: dict = Body(...)):
    nome = (dados.get("nome") or "").strip().lower()
    if not nome: raise HTTPException(400, "tag vazia")
    with conn() as c:
        E.exigir(c, tipo, eid)
        c.execute("INSERT OR IGNORE INTO tags(nome) VALUES(?)", (nome,))
        tid = c.execute("SELECT id FROM tags WHERE nome=?", (nome,)).fetchone()["id"]
        c.execute("INSERT OR IGNORE INTO entity_tags(entity_tipo,entity_id,tag_id) VALUES(?,?,?)", (tipo, eid, tid))
    return {"ok": True}

@router.delete("/entidades/{tipo}/{eid}/tags/{tid}")
def del_tag(tipo: str, eid: int, tid: int):
    with conn() as c: c.execute("DELETE FROM entity_tags WHERE entity_tipo=? AND entity_id=? AND tag_id=?", (tipo, eid, tid))
    return {"ok": True}

# ------------------------------------------------------------------ lugares
# Lugar é OPCIONAL em qualquer ficha (autores não precisam de local de nascimento). Quando existe, o primeiro (★) fixa
# a ficha no mapa; periódicos e eventos são os que mais precisam dele. Países, estados e cidades vêm do catálogo embutido.
def _caminho_lugar(c, pid):
    """Caminho do lugar até a raiz, com proteção contra ciclos em bancos antigos."""
    partes, vistos, atual = [], set(), pid
    while atual and atual not in vistos and len(partes) < 32:
        vistos.add(atual)
        r = c.execute("SELECT id,nome,parent_id FROM places WHERE id=?", (atual,)).fetchone()
        if not r: break
        partes.append(r["nome"]); atual = r["parent_id"]
    return " → ".join(partes)

@router.get("/lugares")
def todos_lugares():
    with conn() as c:
        out = lista(c, """SELECT p.id,p.nome,p.lat,p.lon,p.tipo,p.contexto,p.parent_id,p.notas,
                          pai.nome AS pai,COUNT(ep.entity_id) AS n FROM places p
                          LEFT JOIN places pai ON pai.id=p.parent_id
                          LEFT JOIN entity_places ep ON ep.place_id=p.id GROUP BY p.id ORDER BY p.nome""")
        for r in out: r["caminho"] = _caminho_lugar(c, r["id"])
        return out

@router.post("/lugares")
def criar_lugar_canonico(dados: dict = Body(...)):
    """Cria ou reutiliza um lugar canônico sem exigir associação imediata a uma ficha."""
    nome = (dados.get("nome") or "").strip()
    if not nome: raise HTTPException(400, "Informe o nome do lugar.")
    contexto = (dados.get("contexto") or "").strip() or None
    tipo = (dados.get("tipo") or "").strip() or None
    lat, lon = dados.get("lat"), dados.get("lon")
    if (lat in (None, "")) != (lon in (None, "")): raise HTTPException(400, "Latitude e longitude devem ser informadas juntas.")
    if lat not in (None, ""):
        try: lat, lon = float(lat), float(lon)
        except (TypeError, ValueError): raise HTTPException(400, "Coordenadas inválidas.")
        if not -90 <= lat <= 90 or not -180 <= lon <= 180: raise HTTPException(400, "Coordenadas fora dos limites geográficos.")
    else: lat = lon = None
    with conn() as c:
        pid = _achar_lugar(c, nome, contexto)
        if pid is not None:
            campos = {"lat": lat, "lon": lon, "tipo": tipo, "contexto": contexto}
            # Reutiliza o registro canônico e só completa os campos ainda vazios.
            c.execute("UPDATE places SET lat=COALESCE(lat,?),lon=COALESCE(lon,?),tipo=COALESCE(tipo,?),contexto=COALESCE(contexto,?) WHERE id=?", (lat,lon,tipo,contexto,pid))
            return {"id": pid, "existente": True}
        similares = [dict(r) for r in c.execute("SELECT id,nome,contexto,tipo FROM places WHERE lower(trim(nome))=lower(trim(?))", (nome,))]
        if similares and not contexto:
            raise HTTPException(409, {"mensagem":"Há lugares homônimos; informe o contexto para evitar duplicação ou associação incorreta.","opcoes":similares})
        try:
            cur = c.execute("INSERT INTO places(nome,lat,lon,tipo,contexto) VALUES(?,?,?,?,?)", (nome,lat,lon,tipo,contexto))
        except sqlite3.IntegrityError:
            ex = c.execute("SELECT id FROM places WHERE lower(trim(nome))=lower(trim(?)) ORDER BY id LIMIT 1", (nome,)).fetchone()
            if not ex: raise HTTPException(409, "Não foi possível consolidar o lugar canônico.")
            return {"id": ex["id"], "existente": True}
        pid = cur.lastrowid
        _inferir_hierarquia_lugar(c, pid)
        return {"id": pid, "existente": False}

@router.get("/lugares/buscar")
def buscar_lugares(q: str, internet: int = 0):
    """Catálogo embutido (sempre) + Nominatim/OpenStreetMap (se o módulo online estiver ligado e for pedido)."""
    achados, aviso = geo.buscar(q, 8), None
    if internet:
        if not online.ativo(): aviso = "módulo online desligado"
        else:
            try:
                vistos = {(normalizar(x["nome"]), normalizar(x["contexto"])) for x in achados}
                achados += [x for x in online.lugar(q) if (normalizar(x["nome"]), normalizar(x["contexto"])) not in vistos]
            except online.OnlineErro as e: aviso = str(e)
    return {"lugares": achados, "aviso": aviso}

def _achar_lugar(c, nome, contexto):
    n, ctx = normalizar(nome), normalizar(contexto or "")
    encontrados = [dict(r) for r in c.execute("SELECT id,nome,contexto,tipo FROM places") if normalizar(r["nome"]) == n]
    if not encontrados: return None
    if ctx:
        exatos = [r for r in encontrados if normalizar(r.get("contexto") or "") == ctx]
        if exatos: return exatos[0]["id"]
    # Uma única ficha com esse nome é canônica; não cria cópia apenas porque a grafia do contexto varia.
    if len(encontrados) == 1: return encontrados[0]["id"]
    # Em homônimos, preferir contexto compatível ou lugar sem contexto ainda preenchível.
    sem_ctx = [r for r in encontrados if not r.get("contexto")]
    if len(sem_ctx) == 1: return sem_ctx[0]["id"]
    return None

def _obter_lugar_catalogado(c, nome, tipo_preferido=None):
    nome = (nome or "").strip()
    if not nome: return None
    opcoes = [x for x in geo.buscar(nome, 40) if normalizar(x["nome"]) == normalizar(nome)]
    if tipo_preferido:
        opcoes.sort(key=lambda x: x.get("tipo") != tipo_preferido)
    item = opcoes[0] if opcoes else None
    contexto = item.get("contexto") if item else None
    pid = _achar_lugar(c, nome, contexto)
    if pid is not None: return pid
    try:
        return c.execute("INSERT INTO places(nome,lat,lon,tipo,contexto) VALUES(?,?,?,?,?)",
                         (item["nome"] if item else nome, item.get("lat") if item else None,
                          item.get("lon") if item else None, item.get("tipo") if item else tipo_preferido, contexto)).lastrowid
    except sqlite3.IntegrityError:
        # Bancos antigos podem ter UNIQUE(nome). Reutiliza o nome existente sem perder a ficha original.
        row = c.execute("SELECT id FROM places WHERE lower(nome)=lower(?) ORDER BY id LIMIT 1", (nome,)).fetchone()
        if row: return row["id"]
        raise

def _inferir_hierarquia_lugar(c, pid, vistos=None):
    vistos = vistos or set()
    if pid in vistos: return
    vistos.add(pid)
    r = c.execute("SELECT id,nome,tipo,contexto,parent_id FROM places WHERE id=?", (pid,)).fetchone()
    if not r or r["parent_id"] or (r["tipo"] or "").lower() in {"pais", "histórico", "historico"}: return
    contexto = r["contexto"] or ""
    import re
    tokens = [x.strip() for x in re.split(r"[,;·|]", contexto) if x.strip()]
    # O primeiro trecho costuma repetir a própria cidade; os trechos seguintes descrevem os níveis superiores.
    candidatos = tokens[1:] if tokens and normalizar(tokens[0]) == normalizar(r["nome"]) else tokens
    tipo_lugar = (r["tipo"] or "").lower()
    pai_nome, pai_tipo = None, None
    if tipo_lugar == "estado":
        pai_nome = next((t for t in candidatos if any(normalizar(x["nome"]) == normalizar(t) and x["tipo"] == "pais" for x in geo.buscar(t, 40))), None)
        if not pai_nome and "brasil" in normalizar(contexto): pai_nome = "Brasil"
        pai_tipo = "pais"
    elif tipo_lugar == "cidade":
        for t in candidatos:
            achados = [x for x in geo.buscar(t, 40) if normalizar(x["nome"]) == normalizar(t) and x["tipo"] in ("estado", "pais")]
            est = next((x for x in achados if x["tipo"] == "estado"), None)
            pais = next((x for x in achados if x["tipo"] == "pais"), None)
            if est:
                pai_nome, pai_tipo = est["nome"], "estado"; break
            if pais and not pai_nome:
                pai_nome, pai_tipo = pais["nome"], "pais"
    if pai_nome:
        parent = _obter_lugar_catalogado(c, pai_nome, pai_tipo)
        if parent and parent != pid:
            c.execute("UPDATE places SET parent_id=? WHERE id=? AND parent_id IS NULL", (parent, pid))
            _inferir_hierarquia_lugar(c, parent, vistos)

@router.post("/entidades/{tipo}/{eid}/lugares")
def add_lugar(tipo: str, eid: int, dados: dict = Body(...)):
    nome = (dados.get("nome") or "").strip()
    if not nome: raise HTTPException(400, "lugar vazio")
    contexto, tp, lat, lon = (dados.get("contexto") or "").strip() or None, dados.get("tipo") or None, dados.get("lat"), dados.get("lon")
    with conn() as c:
        E.exigir(c, tipo, eid); pid = _achar_lugar(c, nome, contexto)
        if lat in (None, ""):
            m = next((x for x in geo.buscar(nome, 40) if normalizar(x["nome"]) == normalizar(nome) and
                      (not contexto or normalizar(x["contexto"]) == normalizar(contexto))), None)
            if m: lat, lon, tp, contexto = m["lat"], m["lon"], tp or m["tipo"], contexto or m["contexto"]
        else:
            try: lat, lon = float(lat), float(lon)
            except (TypeError, ValueError): raise HTTPException(400, "coordenadas inválidas")
            if not -90 <= lat <= 90 or not -180 <= lon <= 180: raise HTTPException(400, "coordenadas fora dos limites geográficos")
        if pid is None:
            try: pid = c.execute("INSERT INTO places(nome,lat,lon,tipo,contexto) VALUES(?,?,?,?,?)",
                                 (nome, lat if lat != "" else None, lon if lon != "" else None, tp, contexto)).lastrowid
            except sqlite3.IntegrityError:
                pid = c.execute("SELECT id FROM places WHERE lower(nome)=lower(?) ORDER BY id LIMIT 1", (nome,)).fetchone()["id"]
        else:
            c.execute("UPDATE places SET lat=COALESCE(lat,?), lon=COALESCE(lon,?), tipo=COALESCE(tipo,?), contexto=COALESCE(contexto,?) WHERE id=?",
                      (lat if lat != "" else None, lon if lon != "" else None, tp, contexto, pid))
        if dados.get("parent_id") not in (None, ""):
            parent = int(dados["parent_id"])
            if parent == pid or not c.execute("SELECT 1 FROM places WHERE id=?", (parent,)).fetchone(): raise HTTPException(400, "lugar superior inválido")
            atual, vistos = parent, {pid}
            while atual:
                if atual in vistos: raise HTTPException(400, "a hierarquia criaria um ciclo")
                vistos.add(atual)
                rr = c.execute("SELECT parent_id FROM places WHERE id=?", (atual,)).fetchone(); atual = rr["parent_id"] if rr else None
            c.execute("UPDATE places SET parent_id=? WHERE id=?", (parent, pid))
        else:
            _inferir_hierarquia_lugar(c, pid)
        ordem = c.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM entity_places WHERE entity_tipo=? AND entity_id=?", (tipo, eid)).fetchone()[0]
        c.execute("INSERT OR IGNORE INTO entity_places(entity_tipo,entity_id,place_id,papel,ordem) VALUES(?,?,?,?,?)", (tipo, eid, pid, (dados.get("papel") or "").strip(), ordem))
    return {"ok": True, "place_id": pid}

@router.delete("/entidades/{tipo}/{eid}/lugares/{pid}")
def del_lugar(tipo: str, eid: int, pid: int, papel: str | None = None):
    with conn() as c:
        if papel is None: c.execute("DELETE FROM entity_places WHERE entity_tipo=? AND entity_id=? AND place_id=?", (tipo, eid, pid))
        else: c.execute("DELETE FROM entity_places WHERE entity_tipo=? AND entity_id=? AND place_id=? AND papel=?", (tipo, eid, pid, papel))
    return {"ok": True}

@router.post("/entidades/{tipo}/{eid}/lugares/{pid}/principal")
def lugar_principal(tipo: str, eid: int, pid: int, papel: str | None = None):
    with conn() as c:
        linhas = c.execute("SELECT place_id,papel FROM entity_places WHERE entity_tipo=? AND entity_id=? ORDER BY ordem,place_id,papel", (tipo, eid)).fetchall()
        ids = [(r["place_id"], r["papel"]) for r in linhas]
        chave = (pid, papel or "") if papel is not None else next((x for x in ids if x[0] == pid), None)
        if chave is None or chave not in ids: raise HTTPException(404, "atribuição geográfica não está nesta ficha")
        # A estrela escolhe a atribuição principal da ficha inteira, não apenas
        # a primeira dentro do seu papel. Assim o mapa e a ficha concordam.
        ordenados = [chave] + [x for x in ids if x != chave]
        for ordem, (place_id, role) in enumerate(ordenados):
            c.execute("UPDATE entity_places SET ordem=? WHERE entity_tipo=? AND entity_id=? AND place_id=? AND papel=?", (ordem, tipo, eid, place_id, role))
    return {"ok": True}

@router.patch("/lugares/{pid}")
def editar_lugar(pid: int, dados: dict = Body(...)):
    campos = {}
    for k in ("lat", "lon"):
        if k in dados:
            try: campos[k] = None if dados[k] in (None, "") else float(dados[k])
            except (TypeError, ValueError): raise HTTPException(400, f"{k} inválido")
    if "lat" in campos and campos["lat"] is not None and not -90 <= campos["lat"] <= 90: raise HTTPException(400, "latitude fora de -90..90")
    if "lon" in campos and campos["lon"] is not None and not -180 <= campos["lon"] <= 180: raise HTTPException(400, "longitude fora de -180..180")
    if (dados.get("nome") or "").strip(): campos["nome"] = dados["nome"].strip()
    for k in ("tipo", "contexto", "notas"):
        if k in dados: campos[k] = (dados[k] or "").strip() or None
    if not campos and "parent_id" not in dados: return {"ok": True}
    with conn() as c:
        atual = c.execute("SELECT id FROM places WHERE id=?", (pid,)).fetchone()
        if not atual: raise HTTPException(404, "lugar não existe")
        if "parent_id" in dados:
            pai = None if dados["parent_id"] in (None, "") else int(dados["parent_id"])
            if pai == pid: raise HTTPException(400, "um lugar não pode ser pai de si mesmo")
            if pai is not None and not c.execute("SELECT 1 FROM places WHERE id=?", (pai,)).fetchone(): raise HTTPException(404, "lugar superior não existe")
            cursor, vistos = pai, {pid}
            while cursor:
                if cursor in vistos: raise HTTPException(400, "a hierarquia criaria um ciclo")
                vistos.add(cursor)
                rr = c.execute("SELECT parent_id FROM places WHERE id=?", (cursor,)).fetchone(); cursor = rr["parent_id"] if rr else None
            campos["parent_id"] = pai
        try: c.execute(f"UPDATE places SET {', '.join(f'{k}=?' for k in campos)} WHERE id=?", (*campos.values(), pid))
        except sqlite3.IntegrityError: raise HTTPException(409, "já existe um lugar com esse nome")
    return {"ok": True}

# ------------------------------------------------------------------ imagens
def _pasta(tipo, nome, eid, sub):
    d = config.LIB / "_fichas" / tipo / f"{slug(nome)}-{eid}" / sub
    d.mkdir(parents=True, exist_ok=True); return d

def _salvar_imagem(upload, destino_dir, base):
    alvo = destino_dir / f"{base}{files.ext_imagem(upload.filename)}"
    if alvo.exists(): alvo = destino_dir / f"{base}-{files.novo_lote()[-9:]}{alvo.suffix}"
    with alvo.open("wb") as f:
        import shutil; shutil.copyfileobj(upload.file, f)
    return alvo

@router.post("/entidades/{tipo}/{eid}/imagem")
async def imagem(tipo: str, eid: int, imagem: UploadFile = File(...)):
    e = E.ent(tipo)
    if not e["imagem"]: raise HTTPException(400, "este tipo de ficha não tem imagem principal")
    with conn() as c:
        E.exigir(c, tipo, eid); nome = E.nome_de(c, tipo, eid)
        antiga = c.execute(f"SELECT imagem FROM {e['tabela']} WHERE id=?", (eid,)).fetchone()["imagem"]
        rel = files.relativo(_salvar_imagem(imagem, _pasta(tipo, nome, eid, "_principal"), "imagem"))
        c.execute(f"UPDATE {e['tabela']} SET imagem=? WHERE id=?", (rel, eid))
        if antiga and antiga != rel: files.mover_para_lixo(antiga)
    return {"ok": True, "caminho": rel}

@router.post("/entidades/{tipo}/{eid}/assets")
async def add_asset(tipo: str, eid: int, arquivo: UploadFile = File(...), tipo_asset: str = Form("outro"), legenda: str = Form("")):
    with conn() as c:
        E.exigir(c, tipo, eid); nome = E.nome_de(c, tipo, eid)
        base = slug(__import__("pathlib").Path(arquivo.filename or "imagem").stem)
        rel = files.relativo(_salvar_imagem(arquivo, _pasta(tipo, nome, eid, "_galeria"), base))
        cur = c.execute("INSERT INTO assets(entity_tipo,entity_id,caminho,legenda,tipo_asset) VALUES(?,?,?,?,?)", (tipo, eid, rel, legenda, tipo_asset))
    return {"id": cur.lastrowid, "caminho": rel}

@router.delete("/assets/{aid}")
def del_asset(aid: int):
    with conn() as c:
        r = c.execute("SELECT caminho FROM assets WHERE id=?", (aid,)).fetchone()
        if r: files.mover_para_lixo(r["caminho"]); c.execute("DELETE FROM assets WHERE id=?", (aid,))
    return {"ok": True}

# ------------------------------------------------------------------ obra: edições (manifestações) e mídias
def _generos_da_obra(c, wid):
    linhas = lista(c, """SELECT g.id,g.nome,g.parent_id,p.nome AS pai FROM work_genres wg
                         JOIN genre_terms g ON g.id=wg.genre_id LEFT JOIN genre_terms p ON p.id=g.parent_id
                         WHERE wg.work_id=? ORDER BY wg.ordem,g.nome""", (wid,))
    for g in linhas:
        g["caminho"] = (g["pai"] + " → " + g["nome"]) if g["pai"] else g["nome"]
    return linhas

@router.get("/generos")
def listar_generos():
    with conn() as c:
        rows = lista(c, "SELECT id,nome,parent_id,notas FROM genre_terms ORDER BY nome")
        por_id = {r["id"]: r for r in rows}
        for r in rows:
            vistos, caminho, atual = set(), [], r
            while atual and atual["id"] not in vistos and len(caminho) < 32:
                vistos.add(atual["id"]); caminho.append(atual["nome"])
                atual = por_id.get(atual["parent_id"])
            r["caminho"] = " → ".join(reversed(caminho))
        return rows

@router.post("/generos")
def criar_genero(dados: dict = Body(...)):
    nome = (dados.get("nome") or "").strip()
    if not nome: raise HTTPException(400, "informe o nome do gênero")
    parent = dados.get("parent_id")
    with conn() as c:
        if parent not in (None, ""):
            try: parent = int(parent)
            except (TypeError, ValueError): raise HTTPException(400, "gênero superior inválido")
            if not c.execute("SELECT 1 FROM genre_terms WHERE id=?", (parent,)).fetchone(): raise HTTPException(404, "gênero superior não existe")
        else: parent = None
        existente = next((dict(r) for r in c.execute("SELECT id,nome,parent_id FROM genre_terms") if normalizar(r["nome"]) == normalizar(nome)), None)
        if existente: return {"id": existente["id"], "existente": True}
        cur = c.execute("INSERT INTO genre_terms(nome,parent_id,notas) VALUES(?,?,?)", (nome, parent, (dados.get("notas") or "").strip() or None))
        return {"id": cur.lastrowid, "existente": False}

@router.post("/works/{wid}/generos")
def atribuir_genero(wid: int, dados: dict = Body(...)):
    with conn() as c:
        E.exigir(c, "work", wid)
        gid = dados.get("genre_id") or dados.get("id")
        if gid not in (None, ""):
            try: gid = int(gid)
            except (TypeError, ValueError): raise HTTPException(400, "gênero inválido")
            if not c.execute("SELECT 1 FROM genre_terms WHERE id=?", (gid,)).fetchone(): raise HTTPException(404, "gênero não existe")
        else:
            nome = (dados.get("nome") or "").strip()
            if not nome: raise HTTPException(400, "escolha ou informe um gênero")
            existente = next((dict(r) for r in c.execute("SELECT id,nome,parent_id FROM genre_terms") if normalizar(r["nome"]) == normalizar(nome)), None)
            if existente: gid = existente["id"]
            else:
                parent = dados.get("parent_id")
                if parent in (None, ""): parent = None
                else:
                    try: parent = int(parent)
                    except (TypeError, ValueError): raise HTTPException(400, "gênero superior inválido")
                    if not c.execute("SELECT 1 FROM genre_terms WHERE id=?", (parent,)).fetchone(): raise HTTPException(404, "gênero superior não existe")
                gid = c.execute("INSERT INTO genre_terms(nome,parent_id) VALUES(?,?)", (nome, parent)).lastrowid
        ordem = c.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM work_genres WHERE work_id=?", (wid,)).fetchone()[0]
        cur = c.execute("INSERT OR IGNORE INTO work_genres(work_id,genre_id,ordem) VALUES(?,?,?)", (wid, gid, ordem))
        return {"ok": True, "genre_id": gid, "duplicado": cur.rowcount == 0}

@router.delete("/works/{wid}/generos/{gid}")
def retirar_genero(wid: int, gid: int):
    with conn() as c:
        E.exigir(c, "work", wid)
        c.execute("DELETE FROM work_genres WHERE work_id=? AND genre_id=?", (wid, gid))
    return {"ok": True}

def _buscar_fasciculo(c, periodical_id, volume=None, numero=None, data=None, titulo=None):
    """Resolve a identidade do fascículo sem inferir a partir de dados insuficientes."""
    volume = str(volume).strip() if volume not in (None, "") else None
    numero = str(numero).strip() if numero not in (None, "") else None
    data = str(data).strip() if data not in (None, "") else None
    titulo = str(titulo).strip() if titulo not in (None, "") else None
    if volume or numero:
        return c.execute("""SELECT id FROM periodical_issues WHERE periodical_id=?
                            AND COALESCE(volume,'')=COALESCE(?,'') AND COALESCE(numero,'')=COALESCE(?,'')
                            AND COALESCE(data,'')=COALESCE(?,'') ORDER BY id LIMIT 1""",
                         (periodical_id, volume, numero, data)).fetchone()
    if titulo:
        from core.texto import normalizar
        candidatos = c.execute("""SELECT id,titulo FROM periodical_issues WHERE periodical_id=?
                                  AND length(trim(COALESCE(volume,'')))=0 AND length(trim(COALESCE(numero,'')))=0
                                  AND COALESCE(data,'')=COALESCE(?,'') AND titulo IS NOT NULL ORDER BY id""",
                               (periodical_id, data)).fetchall()
        return next((r for r in candidatos if normalizar(r["titulo"]) == normalizar(titulo)), None)
    return None


def _obter_fasciculo(c, periodical_id, volume=None, numero=None, data=None, titulo=None, referencia=None, notas=None):
    """Cria/reutiliza um fascículo apenas com identificadores explicitamente informados."""
    volume = str(volume).strip() if volume not in (None, "") else None
    numero = str(numero).strip() if numero not in (None, "") else None
    data = str(data).strip() if data not in (None, "") else None
    titulo = str(titulo).strip() if titulo not in (None, "") else None
    referencia = str(referencia).strip() if referencia not in (None, "") else None
    notas = str(notas).strip() if notas not in (None, "") else None
    if not any((volume, numero, titulo)):
        return None
    ex = _buscar_fasciculo(c, periodical_id, volume, numero, data, titulo)
    if ex:
        # Não sobrescreve campos já catalogados com vazios; completa apenas lacunas.
        c.execute("""UPDATE periodical_issues SET titulo=COALESCE(titulo,?),referencia=COALESCE(referencia,?),
                     notas=COALESCE(notas,?) WHERE id=?""", (titulo, referencia, notas, ex["id"]))
        return ex["id"]
    return c.execute("""INSERT INTO periodical_issues(periodical_id,volume,numero,data,data_num,titulo,referencia,notas)
                        VALUES(?,?,?,?,?,?,?,?)""", (periodical_id, volume, numero, data, ano_num(data), titulo, referencia, notas)).lastrowid


@router.get("/periodicals/{pid}/fasciculos")
def listar_fasciculos(pid: int):
    with conn() as c:
        if not c.execute("SELECT 1 FROM periodicals WHERE id=?", (pid,)).fetchone(): raise HTTPException(404, "periódico não existe")
        return lista(c, """SELECT i.*,COUNT(m.id) AS manifestacoes FROM periodical_issues i
                           LEFT JOIN manifestations m ON m.issue_id=i.id WHERE i.periodical_id=?
                           GROUP BY i.id ORDER BY (i.data_num IS NULL),i.data_num,i.volume,i.numero,i.id""", (pid,))


@router.post("/periodicals/{pid}/fasciculos")
def criar_fasciculo(pid: int, dados: dict = Body(...)):
    with conn() as c:
        if not c.execute("SELECT 1 FROM periodicals WHERE id=?", (pid,)).fetchone(): raise HTTPException(404, "periódico não existe")
        if not any(str(dados.get(k) or "").strip() for k in ("volume", "numero", "titulo")):
            raise HTTPException(400, "informe volume, número ou título do fascículo")
        vol = str(dados.get("volume") or "").strip() or None
        num = str(dados.get("numero") or "").strip() or None
        data = str(dados.get("data") or "").strip() or None
        ex = _buscar_fasciculo(c, pid, vol, num, data, dados.get("titulo"))
        iid = _obter_fasciculo(c, pid, vol, num, data, dados.get("titulo"), dados.get("referencia"), dados.get("notas"))
        return {"id": iid, "existente": ex is not None}


@router.patch("/fasciculos/{iid}")
def editar_fasciculo(iid: int, dados: dict = Body(...)):
    permitidos = {"volume", "numero", "data", "titulo", "referencia", "notas"}
    campos = {k: (str(dados[k]).strip() or None) if dados[k] not in (None, "") else None for k in permitidos if k in dados}
    if "data" in campos: campos["data_num"] = ano_num(campos["data"])
    if not campos: return {"ok": True}
    with conn() as c:
        if not c.execute("SELECT 1 FROM periodical_issues WHERE id=?", (iid,)).fetchone(): raise HTTPException(404, "fascículo não existe")
        try: c.execute(f"UPDATE periodical_issues SET {', '.join(f'{k}=?' for k in campos)} WHERE id=?", (*campos.values(), iid))
        except sqlite3.IntegrityError: raise HTTPException(409, "já existe um fascículo com esse volume, número e data")
    return {"ok": True}


@router.delete("/fasciculos/{iid}")
def apagar_fasciculo(iid: int):
    with conn() as c:
        if not c.execute("SELECT 1 FROM periodical_issues WHERE id=?", (iid,)).fetchone(): raise HTTPException(404, "fascículo não existe")
        n = c.execute("SELECT COUNT(*) FROM manifestations WHERE issue_id=?", (iid,)).fetchone()[0]
        if n: raise HTTPException(409, f"fascículo ainda está vinculado a {n} manifestação(ões); desvincule-as primeiro")
        c.execute("DELETE FROM periodical_issues WHERE id=?", (iid,))
    return {"ok": True}


def _texto(valor):
    """Normaliza valor de campo textual vindo de JSON (aceita número, null, string)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


_CAMPOS_ED = ("editora", "ano_edicao", "idioma", "notas", "local", "fonte",
              "tipo_aparicao", "periodical_id", "container_work_id", "container_manifestation_id",
              "issue_id", "referencia")


# ------------------------------------------------------------------ agentes (obra e edição)
@router.post("/obras/{wid}/agentes")
def add_agente_obra(wid: int, dados: dict = Body(...)):
    """Adiciona ou atualiza um papel de agente na obra (fonte canônica: work_agents)."""
    papel = (dados.get("papel") or "").strip()
    if papel not in E.PAPEIS_OBRA:
        raise HTTPException(400, f"papel inválido para obra: use um de {', '.join(E.PAPEIS_OBRA)}")
    try:
        aid = int(dados.get("author_id"))
    except (TypeError, ValueError):
        raise HTTPException(400, "informe a pessoa (author_id)")
    ano, fonte, notas = _texto(dados.get("ano")), _texto(dados.get("fonte")), _texto(dados.get("notas"))
    with conn() as c:
        E.exigir(c, "work", wid)
        E.exigir(c, "author", aid)
        if papel == "autor_principal":
            linha = E.definir_autor_principal(c, wid, aid, ano=ano, fonte=fonte, notas=notas)
            return {"id": f"wa:{linha}", "papel": papel}
        ex = c.execute("SELECT id FROM work_agents WHERE work_id=? AND author_id=? AND papel=?",
                       (wid, aid, papel)).fetchone()
        if ex:
            c.execute("""UPDATE work_agents SET ano=COALESCE(?,ano),ano_num=COALESCE(?,ano_num),
                         fonte=COALESCE(?,fonte),notas=COALESCE(?,notas) WHERE id=?""",
                      (ano, ano_num(ano), fonte, notas, ex["id"]))
            marcar_revisao(c, "work_agent", [ex["id"]],
                           "Os metadados deste papel foram alterados; confirme a fonte.")
            return {"id": f"wa:{ex['id']}", "papel": papel, "atualizado": True}
        ordem = c.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM work_agents WHERE work_id=?",
                          (wid,)).fetchone()[0]
        novo = c.execute("""INSERT INTO work_agents(work_id,author_id,papel,ordem,ano,ano_num,fonte,notas)
                            VALUES(?,?,?,?,?,?,?,?)""",
                         (wid, aid, papel, ordem, ano, ano_num(ano), fonte, notas)).lastrowid
    return {"id": f"wa:{novo}", "papel": papel}


@router.delete("/obras/{wid}/agentes/{aid}")
def del_agente_obra(wid: int, aid: int):
    with conn() as c:
        linha = c.execute("SELECT id,papel FROM work_agents WHERE id=? AND work_id=?", (aid, wid)).fetchone()
        if not linha:
            raise HTTPException(404, "participação não encontrada")
        marcar_revisao(c, "work_agent", [aid],
                       "Esta participação foi removida; a evidência não sustenta mais a afirmação.")
        c.execute("DELETE FROM work_agents WHERE id=?", (aid,))
    return {"ok": True}


@router.post("/manifestacoes/{mid}/agentes")
def add_agente_manifestacao(mid: int, dados: dict = Body(...)):
    """Crédito de uma edição concreta (tradutor, organizador, ilustrador...)."""
    papel = (dados.get("papel") or "").strip()
    if papel not in E.PAPEIS_MANIFESTACAO:
        raise HTTPException(400, f"papel inválido para edição: use um de {', '.join(E.PAPEIS_MANIFESTACAO)}")
    try:
        aid = int(dados.get("author_id"))
    except (TypeError, ValueError):
        raise HTTPException(400, "informe a pessoa (author_id)")
    fonte, notas = _texto(dados.get("fonte")), _texto(dados.get("notas"))
    with conn() as c:
        if not c.execute("SELECT 1 FROM manifestations WHERE id=?", (mid,)).fetchone():
            raise HTTPException(404, "manifestação não existe")
        E.exigir(c, "author", aid)
        ex = c.execute("SELECT id FROM manifestation_agents WHERE manifestation_id=? AND author_id=? AND papel=?",
                       (mid, aid, papel)).fetchone()
        if ex:
            c.execute("UPDATE manifestation_agents SET fonte=COALESCE(?,fonte),notas=COALESCE(?,notas) WHERE id=?",
                      (fonte, notas, ex["id"]))
            marcar_revisao(c, "manifestation_agent", [ex["id"]],
                           "Os metadados deste crédito foram alterados; confirme a fonte.")
            return {"id": f"ma:{ex['id']}", "papel": papel, "atualizado": True}
        ordem = c.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM manifestation_agents WHERE manifestation_id=?",
                          (mid,)).fetchone()[0]
        novo = c.execute("""INSERT INTO manifestation_agents(manifestation_id,author_id,papel,ordem,fonte,notas)
                            VALUES(?,?,?,?,?,?)""", (mid, aid, papel, ordem, fonte, notas)).lastrowid
    return {"id": f"ma:{novo}", "papel": papel}


@router.delete("/manifestacoes/{mid}/agentes/{aid}")
def del_agente_manifestacao(mid: int, aid: int):
    with conn() as c:
        linha = c.execute("SELECT id FROM manifestation_agents WHERE id=? AND manifestation_id=?",
                          (aid, mid)).fetchone()
        if not linha:
            raise HTTPException(404, "crédito não encontrado")
        marcar_revisao(c, "manifestation_agent", [aid],
                       "Este crédito de edição foi removido; a evidência não sustenta mais a afirmação.")
        c.execute("DELETE FROM manifestation_agents WHERE id=?", (aid,))
    return {"ok": True}


@router.post("/works/{wid}/edicoes")
async def nova_edicao(wid: int, arquivo: UploadFile | None = File(None), editora: str = Form(""), ano_edicao: str = Form(""),
                      idioma: str = Form(""), notas: str = Form(""),
                      local: str = Form(""), fonte: str = Form(""), tipo_aparicao: str = Form("edição"),
                      periodical_id: str = Form(""), container_work_id: str = Form(""), referencia: str = Form(""),
                      issue_id: str = Form(""), container_manifestation_id: str = Form(""), volume: str = Form(""),
                      numero: str = Form(""), data_fasciculo: str = Form(""), titulo_fasciculo: str = Form("")):
    caminho, formato, issue, mid = "", None, None, None
    with conn() as c:
        w = um(c, f"SELECT w.id,w.titulo,a.nome AS autor FROM works w LEFT JOIN authors a ON a.id={AUTOR} "
                  f"WHERE w.id=?", (wid,))
        if not w:
            raise HTTPException(404, "obra não encontrada")
        if arquivo is not None and arquivo.filename:
            if __import__("pathlib").Path(arquivo.filename).suffix.lower() not in config.FORMATOS:
                raise HTTPException(400, "formato não suportado (use PDF, DOCX, TXT ou MD)")
            # o arquivo entra na biblioteca antes do INSERT, mas numa área de entrada;
            # a promoção para a estante acontece só depois do commit
            caminho = files.estacionar(files.guardar_upload(arquivo))
            formato = __import__("pathlib").Path(caminho).suffix.lstrip(".")
        v = {k: _texto(x) for k, x in zip(
            ("editora", "ano_edicao", "idioma", "notas", "local", "fonte", "tipo_aparicao",
             "periodical_id", "container_work_id", "referencia"),
            (editora, ano_edicao, idioma, notas, local, fonte, tipo_aparicao,
             periodical_id, container_work_id, referencia))}
        if v["periodical_id"]:
            try: v["periodical_id"] = int(v["periodical_id"])
            except ValueError: raise HTTPException(400, "periódico inválido")
            if not c.execute("SELECT 1 FROM periodicals WHERE id=?", (v["periodical_id"],)).fetchone(): raise HTTPException(404, "periódico não existe")
        else: v["periodical_id"] = None
        if v["container_work_id"]:
            try: v["container_work_id"] = int(v["container_work_id"])
            except ValueError: raise HTTPException(400, "obra continente inválida")
            if v["container_work_id"] == wid: raise HTTPException(400, "uma obra não pode ser continente da própria manifestação")
            if not c.execute("SELECT 1 FROM works WHERE id=?", (v["container_work_id"],)).fetchone(): raise HTTPException(404, "obra continente não existe")
        else: v["container_work_id"] = None
        cmid = None
        if container_manifestation_id:
            try: cmid = int(container_manifestation_id)
            except ValueError: raise HTTPException(400, "edição continente inválida")
            cm = c.execute("SELECT id,work_id FROM manifestations WHERE id=?", (cmid,)).fetchone()
            if not cm: raise HTTPException(404, "edição continente não existe")
            if cm["work_id"] == wid: raise HTTPException(400, "uma manifestação não pode conter outra manifestação da mesma obra")
            if v["container_work_id"] and int(v["container_work_id"]) != cm["work_id"]: raise HTTPException(400, "obra continente não corresponde à edição escolhida")
            v["container_work_id"] = cm["work_id"]
        if issue_id:
            try: issue = int(issue_id)
            except ValueError: raise HTTPException(400, "fascículo inválido")
            ir = c.execute("SELECT id,periodical_id FROM periodical_issues WHERE id=?", (issue,)).fetchone()
            if not ir: raise HTTPException(404, "fascículo não existe")
            if v["periodical_id"] and int(v["periodical_id"]) != ir["periodical_id"]: raise HTTPException(400, "o fascículo pertence a outro periódico")
            v["periodical_id"] = ir["periodical_id"]
        elif v["periodical_id"] and any(x.strip() for x in (volume, numero, titulo_fasciculo)):
            issue = _obter_fasciculo(c, int(v["periodical_id"]), volume, numero, data_fasciculo,
                                     titulo_fasciculo, referencia, notas)
        cur = c.execute("""INSERT INTO manifestations(work_id,caminho,formato,editora,ano_edicao,ed_num,
                            idioma,notas,local,fonte,paginas,tipo_aparicao,periodical_id,container_work_id,
                            referencia,issue_id,container_manifestation_id)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (wid, caminho, formato, v["editora"], v["ano_edicao"], ano_num(v["ano_edicao"]),
                         v["idioma"], v["notas"], v["local"], v["fonte"],
                         files.paginas(config.DATA / caminho) if caminho else None,
                         v["tipo_aparicao"] or "edição", v["periodical_id"], v["container_work_id"],
                         v["referencia"], issue, cmid))
        mid = cur.lastrowid
    if caminho:
        final = files.promover(caminho, w["autor"], w["titulo"])
        if final != caminho:
            with conn() as c:
                c.execute("UPDATE manifestations SET caminho=? WHERE id=?", (final, mid))
            caminho = final
    return {"id": mid, "caminho": caminho, "issue_id": issue}

@router.patch("/edicoes/{mid}")
def editar_edicao(mid: int, dados: dict = Body(...)):
    campos = {k: _texto(v) for k, v in dados.items()
              if k in _CAMPOS_ED and k not in ("periodical_id", "container_work_id",
                                               "container_manifestation_id", "issue_id")}
    if "ano_edicao" in campos:
        campos["ed_num"] = ano_num(campos["ano_edicao"])
    with conn() as c:
        manifesto = c.execute("""SELECT id,work_id,periodical_id,issue_id,container_work_id,
                                 container_manifestation_id FROM manifestations WHERE id=?""", (mid,)).fetchone()
        if not manifesto: raise HTTPException(404, "manifestação não existe")
        periodical = manifesto["periodical_id"]
        if "periodical_id" in dados:
            v = dados["periodical_id"]
            if v in (None, "", 0, "0"): periodical = None
            else:
                try: periodical = int(v)
                except (TypeError, ValueError): raise HTTPException(400, "periódico inválido")
                if not c.execute("SELECT 1 FROM periodicals WHERE id=?", (periodical,)).fetchone(): raise HTTPException(404, "periódico não existe")
            issue_atual = c.execute("SELECT periodical_id FROM periodical_issues WHERE id=?", (manifesto["issue_id"],)).fetchone() if manifesto["issue_id"] else None
            if issue_atual and issue_atual["periodical_id"] != periodical and "issue_id" not in dados:
                raise HTTPException(409, "esta manifestação está vinculada a um fascículo do periódico atual; escolha outro fascículo ou envie issue_id=null para desvincular")
            campos["periodical_id"] = periodical
        cmid = manifesto["container_manifestation_id"]
        if "container_work_id" in dados:
            v = dados["container_work_id"]
            if v in (None, "", 0, "0"):
                campos["container_work_id"] = None
                # Não pode restar um vínculo com edição concreta quando o vínculo
                # geral com a obra continente foi explicitamente removido.
                campos["container_manifestation_id"] = None; cmid = None
            else:
                try: v = int(v)
                except (TypeError, ValueError): raise HTTPException(400, "obra continente inválida")
                if v == manifesto["work_id"]: raise HTTPException(400, "uma obra não pode ser continente da própria manifestação")
                if not c.execute("SELECT 1 FROM works WHERE id=?", (v,)).fetchone(): raise HTTPException(404, "obra continente não existe")
                campos["container_work_id"] = v
                if cmid:
                    concr = c.execute("SELECT work_id FROM manifestations WHERE id=?", (cmid,)).fetchone()
                    if not concr or concr["work_id"] != v:
                        # Selecionar outra obra continente abandona a precisão da
                        # edição anterior; nunca deixa um par de campos contraditório.
                        campos["container_manifestation_id"] = None; cmid = None
        if "container_manifestation_id" in dados:
            v = dados["container_manifestation_id"]
            if v in (None, "", 0, "0"): cmid = None; campos["container_manifestation_id"] = None
            else:
                try: cmid = int(v)
                except (TypeError, ValueError): raise HTTPException(400, "edição continente inválida")
                cm = c.execute("SELECT id,work_id,container_manifestation_id FROM manifestations WHERE id=?", (cmid,)).fetchone()
                if not cm: raise HTTPException(404, "edição continente não existe")
                if cmid == mid or cm["work_id"] == manifesto["work_id"]: raise HTTPException(400, "manifestação continente inválida")
                container_solicitado = dados.get("container_work_id")
                if container_solicitado not in (None, "", 0, "0") and int(container_solicitado) != cm["work_id"]:
                    raise HTTPException(400, "a obra continente não corresponde à edição concreta escolhida")
                cursor, vistos = cmid, {mid}
                while cursor:
                    if cursor in vistos: raise HTTPException(400, "a contenção criaria um ciclo")
                    vistos.add(cursor)
                    rr = c.execute("SELECT container_manifestation_id FROM manifestations WHERE id=?", (cursor,)).fetchone()
                    cursor = rr["container_manifestation_id"] if rr else None
                campos["container_manifestation_id"] = cmid
                campos["container_work_id"] = cm["work_id"]
        issue_id = manifesto["issue_id"]
        if "issue_id" in dados:
            v = dados["issue_id"]
            if v in (None, "", 0, "0"): issue_id = None; campos["issue_id"] = None
            else:
                try: issue_id = int(v)
                except (TypeError, ValueError): raise HTTPException(400, "fascículo inválido")
                issue = c.execute("SELECT id,periodical_id FROM periodical_issues WHERE id=?", (issue_id,)).fetchone()
                if not issue: raise HTTPException(404, "fascículo não existe")
                if periodical and periodical != issue["periodical_id"]: raise HTTPException(400, "fascículo pertence a outro periódico")
                periodical = issue["periodical_id"]; campos["periodical_id"] = periodical; campos["issue_id"] = issue_id
        virtual = {k: dados.get(k) for k in ("volume", "numero", "data_fasciculo", "titulo_fasciculo") if k in dados}
        if virtual and periodical:
            iid = _obter_fasciculo(c, periodical, virtual.get("volume"), virtual.get("numero"), virtual.get("data_fasciculo"), virtual.get("titulo_fasciculo"), dados.get("referencia"), dados.get("notas"))
            if iid:
                issue_id = iid; campos["issue_id"] = iid; campos["periodical_id"] = periodical
        try:
            if campos: c.execute(f"UPDATE manifestations SET {', '.join(f'{k}=?' for k in campos)} WHERE id=?", (*campos.values(), mid))
        except sqlite3.IntegrityError: raise HTTPException(409, "não foi possível aplicar a alteração sem violar a integridade documental")
    return {"ok": True}

@router.delete("/edicoes/{mid}")
def apagar_edicao(mid: int):
    with conn() as c:
        r = c.execute("SELECT caminho FROM manifestations WHERE id=?", (mid,)).fetchone()
        if not r: raise HTTPException(404, "manifestação não existe")
        dependentes = c.execute("SELECT COUNT(*) FROM manifestations WHERE container_manifestation_id=?", (mid,)).fetchone()[0]
        if dependentes:
            raise HTTPException(409, f"esta manifestação contém {dependentes} outra(s) manifestação(ões); desvincule-as antes de excluir")
        files.mover_para_lixo(r["caminho"]); c.execute("DELETE FROM manifestations WHERE id=?", (mid,))
    return {"ok": True}

def vincular_midia(c, wid, nome, pid=None):
    nome = (nome or "").strip().lower()
    if not nome: raise HTTPException(400, "mídia vazia")
    m = next((r for r in c.execute("SELECT id,nome FROM media") if normalizar(r["nome"]) == normalizar(nome)), None)
    mid = m["id"] if m else c.execute("INSERT INTO media(nome) VALUES(?)", (nome,)).lastrowid
    ordem = c.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM work_media WHERE work_id=?", (wid,)).fetchone()[0]
    c.execute("INSERT OR IGNORE INTO work_media(work_id,media_id,ordem) VALUES(?,?,?)", (wid, mid, ordem))
    E.anexar_perfil(c, pid, "media", mid)
    return mid

@router.post("/works/{wid}/midias")
def add_midia(wid: int, request: Request, dados: dict = Body(...)):
    with conn() as c:
        E.exigir(c, "work", wid)
        return {"ok": True, "media_id": vincular_midia(c, wid, dados.get("nome"), perfil_ativo(request))}

@router.delete("/works/{wid}/midias/{mid}")
def del_midia(wid: int, mid: int):
    with conn() as c: c.execute("DELETE FROM work_media WHERE work_id=? AND media_id=?", (wid, mid))
    return {"ok": True}
