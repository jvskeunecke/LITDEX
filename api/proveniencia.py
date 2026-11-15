"""Fontes e evidências reutilizáveis para afirmações documentais."""
from fastapi import APIRouter, Body, HTTPException
from core.db import conn, lista

router = APIRouter(prefix="/api")
ENTITY_TABLES = {
    "author": ("authors", "nome"), "work": ("works", "titulo"),
    "periodical": ("periodicals", "titulo"), "event": ("events", "nome"),
    "media": ("media", "nome"), "institution": ("institutions", "nome"), "manifestation": ("manifestations", "tipo_aparicao"),
    "issue": ("periodical_issues", "titulo"),
}
SOURCE_FIELDS = ("titulo", "tipo", "autor", "data", "url", "identificador", "referencia", "notas")
EVIDENCE_FIELDS = ("source_id", "entidade_tipo", "entidade_id", "afirmacao", "alvo_tipo", "alvo_id", "trecho", "localizador", "data_consulta", "notas")

def _clean(dados, fields):
    return {k: (str(dados[k]).strip() if dados[k] is not None else None) for k in fields if k in dados}

def _clean_evidencia(dados):
    """Normaliza preservando o tipo dos identificadores.

    Comparar `"3"` com `3` marcava revisão sem que nada tivesse mudado; aqui
    source_id e entidade_id continuam inteiros, como no banco.
    """
    out = {}
    for k in EVIDENCE_FIELDS:
        if k not in dados:
            continue
        v = dados[k]
        if k in ("source_id", "entidade_id"):
            if v in (None, ""):
                out[k] = None
            else:
                try:
                    out[k] = int(v)
                except (TypeError, ValueError):
                    raise HTTPException(400, f"{k} precisa ser um número inteiro")
        else:
            out[k] = str(v).strip() if v is not None else None
    return out

@router.get("/fontes")
def listar_fontes(q: str = ""):
    with conn() as c:
        if q.strip():
            termo = f"%{q.strip()}%"
            return lista(c, "SELECT * FROM sources WHERE titulo LIKE ? OR autor LIKE ? OR identificador LIKE ? OR url LIKE ? ORDER BY titulo", (termo, termo, termo, termo))
        return lista(c, "SELECT * FROM sources ORDER BY titulo")

@router.post("/fontes")
def criar_fonte(dados: dict = Body(...)):
    campos = _clean(dados, SOURCE_FIELDS)
    if not campos.get("titulo"):
        raise HTTPException(400, "A fonte precisa de título ou descrição identificável.")
    cols = list(campos)
    with conn() as c:
        cur = c.execute(f"INSERT INTO sources({','.join(cols)}) VALUES({','.join('?' for _ in cols)})", [campos[k] for k in cols])
        return dict(c.execute("SELECT * FROM sources WHERE id=?", (cur.lastrowid,)).fetchone())

@router.patch("/fontes/{sid}")
def editar_fonte(sid: int, dados: dict = Body(...)):
    campos = _clean(dados, SOURCE_FIELDS)
    if not campos: return {"ok": True}
    if "titulo" in campos and not campos["titulo"]: raise HTTPException(400, "O título não pode ficar vazio.")
    with conn() as c:
        if not c.execute("SELECT 1 FROM sources WHERE id=?", (sid,)).fetchone(): raise HTTPException(404, "Fonte não encontrada.")
        c.execute(f"UPDATE sources SET {','.join(k+'=?' for k in campos)} WHERE id=?", [*campos.values(), sid])
        return dict(c.execute("SELECT * FROM sources WHERE id=?", (sid,)).fetchone())

@router.delete("/fontes/{sid}")
def apagar_fonte(sid: int):
    with conn() as c:
        if not c.execute("SELECT 1 FROM sources WHERE id=?", (sid,)).fetchone(): raise HTTPException(404, "Fonte não encontrada.")
        # A evidência permanece, mas perde a referência direta à fonte; não pode continuar silenciosamente vigente.
        c.execute("UPDATE evidences SET estado='revisao_necessaria', motivo_revisao='A fonte vinculada foi removida; identifique novamente a fonte ou revise esta evidência.' WHERE source_id=?", (sid,))
        c.execute("DELETE FROM sources WHERE id=?", (sid,))
    return {"ok": True}

@router.get("/evidencias")
def listar_evidencias(entidade_tipo: str | None = None, entidade_id: int | None = None, source_id: int | None = None, alvo_tipo: str | None = None, alvo_id: str | None = None):
    sql = "SELECT e.*,s.titulo AS fonte_titulo,s.url AS fonte_url FROM evidences e LEFT JOIN sources s ON s.id=e.source_id WHERE 1=1"
    args = []
    if entidade_tipo is not None: sql += " AND e.entidade_tipo=?"; args.append(entidade_tipo)
    if entidade_id is not None: sql += " AND e.entidade_id=?"; args.append(entidade_id)
    if source_id is not None: sql += " AND e.source_id=?"; args.append(source_id)
    if alvo_tipo is not None: sql += " AND e.alvo_tipo=?"; args.append(alvo_tipo)
    if alvo_id is not None: sql += " AND e.alvo_id=?"; args.append(alvo_id)
    sql += " ORDER BY e.id"
    with conn() as c: return lista(c, sql, args)

@router.post("/evidencias")
def criar_evidencia(dados: dict = Body(...)):
    campos = _clean_evidencia(dados)
    tipo, eid = campos.get("entidade_tipo"), campos.get("entidade_id")
    if tipo not in ENTITY_TABLES: raise HTTPException(400, "Tipo de entidade inválido para evidência.")
    if not eid or not str(eid).isdigit(): raise HTTPException(400, "entidade_id precisa ser um inteiro positivo.")
    campos["entidade_id"] = int(eid)
    if campos.get("alvo_tipo"):
        alvo = str(campos.get("alvo_id") or "").strip()
        tipo_alvo = campos["alvo_tipo"]
        if not alvo: raise HTTPException(400, "alvo_id é obrigatório para evidência de uma afirmação")
        with conn() as c:
            if tipo_alvo == "relation":
                rid = alvo.split(":")[-1]
                ok = rid.isdigit() and c.execute("SELECT 1 FROM relations WHERE id=?", (int(rid),)).fetchone()
            elif tipo_alvo == "work_agent":
                rid = alvo.split(":")[-1]; ok = rid.isdigit() and c.execute("SELECT 1 FROM work_agents WHERE id=?", (int(rid),)).fetchone()
            elif tipo_alvo == "manifestation_agent":
                rid = alvo.split(":")[-1]; ok = rid.isdigit() and c.execute("SELECT 1 FROM manifestation_agents WHERE id=?", (int(rid),)).fetchone()
            else: raise HTTPException(400, "alvo_tipo deve ser relation, work_agent ou manifestation_agent")
            if not ok: raise HTTPException(404, "afirmação/alvo não encontrado")
        campos["alvo_id"] = alvo
    if not campos.get("afirmacao"): raise HTTPException(400, "Descreva a afirmação sustentada pela evidência.")
    with conn() as c:
        tabela, _ = ENTITY_TABLES[tipo]
        if not c.execute(f"SELECT 1 FROM {tabela} WHERE id=?", (campos["entidade_id"],)).fetchone():
            raise HTTPException(404, "Entidade da evidência não encontrada.")
        if campos.get("source_id") is not None and not c.execute("SELECT 1 FROM sources WHERE id=?", (campos["source_id"],)).fetchone():
            raise HTTPException(404, "Fonte vinculada não encontrada.")
        cols = list(campos)
        cur = c.execute(f"INSERT INTO evidences({','.join(cols)}) VALUES({','.join('?' for _ in cols)})", [campos[k] for k in cols])
        return dict(c.execute("SELECT * FROM evidences WHERE id=?", (cur.lastrowid,)).fetchone())

@router.patch("/evidencias/{eid}")
def editar_evidencia(eid: int, dados: dict = Body(...)):
    permitidos = ("source_id", "afirmacao", "trecho", "localizador", "data_consulta",
                  "notas", "estado", "motivo_revisao")
    campos = {k: v for k, v in _clean_evidencia(dados).items() if k in permitidos}
    if "afirmacao" in campos and not campos["afirmacao"]: raise HTTPException(400, "A afirmação não pode ficar vazia.")
    if "estado" in campos and campos["estado"] not in {"vigente", "revisao_necessaria", "nao_sustenta"}:
        raise HTTPException(400, "estado de evidência inválido")
    if campos.get("estado") == "vigente": campos["motivo_revisao"] = None
    with conn() as c:
        antigo = c.execute("SELECT * FROM evidences WHERE id=?", (eid,)).fetchone()
        if not antigo: raise HTTPException(404, "Evidência não encontrada.")
        if campos.get("source_id") is not None and not c.execute("SELECT 1 FROM sources WHERE id=?", (campos["source_id"],)).fetchone(): raise HTTPException(404, "Fonte vinculada não encontrada.")
        # Alterar a fonte, a afirmação literal, o trecho ou o localizador pode
        # mudar aquilo que a evidência sustenta. Exige reavaliação explícita;
        # só a decisão deliberada estado='vigente' confirma a nova vinculação.
        campos_de_validade = {"source_id", "afirmacao", "trecho", "localizador"}
        mudou_base = any(k in campos and campos[k] != antigo[k] for k in campos_de_validade)
        if mudou_base and "estado" not in campos:
            campos["estado"] = "revisao_necessaria"
            campos["motivo_revisao"] = "A fonte, a formulação ou o localizador desta evidência mudou; confirme se ela ainda sustenta a afirmação vinculada."
        if campos.get("estado") == "vigente": campos["motivo_revisao"] = None
        if campos: c.execute(f"UPDATE evidences SET {','.join(k+'=?' for k in campos)} WHERE id=?", [*campos.values(), eid])
        return dict(c.execute("SELECT * FROM evidences WHERE id=?", (eid,)).fetchone())

@router.delete("/evidencias/{eid}")
def apagar_evidencia(eid: int):
    with conn() as c:
        cur = c.execute("DELETE FROM evidences WHERE id=?", (eid,))
        if not cur.rowcount: raise HTTPException(404, "Evidência não encontrada.")
    return {"ok": True}

# ------------------------------------------------------------------ reconciliação assistida de campos legados
_LEGADO_FONTES = {
    "author": ("authors", ("notas",)),
    "work": ("works", ("notas",)),
    "periodical": ("periodicals", ("notas",)),
    "event": ("events", ("notas",)),
    "media": ("media", ("notas",)),
    "institution": ("institutions", ("notas",)),
    "manifestation": ("manifestations", ("fonte", "referencia", "notas")),
    "issue": ("periodical_issues", ("referencia", "notas")),
    "relation": ("relations", ("fonte", "notas")),
    "work_agent": ("work_agents", ("fonte", "notas")),
    "manifestation_agent": ("manifestation_agents", ("fonte", "notas")),
}

@router.get("/migracao/fontes-legadas")
def auditar_fontes_legadas(limite: int = 200):
    """Dry-run de texto legado sem evidência vinculada; nunca altera dados."""
    limite = max(1, min(int(limite), 1000))
    achados = []
    with conn() as c:
        for tipo, (tabela, campos) in _LEGADO_FONTES.items():
            cols = {r[1] for r in c.execute(f"PRAGMA table_info({tabela})")}
            campos = tuple(f for f in campos if f in cols)
            if not campos or "id" not in cols: continue
            nome_col = next((x for x in ("titulo", "nome", "tipo_aparicao", "tipo", "papel") if x in cols), "id")
            cond = " OR ".join(f"({f} IS NOT NULL AND trim(CAST({f} AS TEXT)) <> '')" for f in campos)
            for row in lista(c, f"SELECT id,{nome_col} AS nome,{','.join(campos)} FROM {tabela} WHERE {cond} ORDER BY id LIMIT ?", (limite,)):
                # Para relações/créditos, evidências de alvo são mais precisas que as ligadas à entidade.
                alvo_tipo = {"relation":"relation", "work_agent":"work_agent", "manifestation_agent":"manifestation_agent"}.get(tipo)
                if alvo_tipo:
                    tem = c.execute("SELECT 1 FROM evidences WHERE alvo_tipo=? AND alvo_id IN (?,?) AND COALESCE(notas,'') LIKE 'Reconciliação assistida%' LIMIT 1", (alvo_tipo, str(row["id"]), f"{ {'relation':'r','work_agent':'wa','manifestation_agent':'ma'}[tipo] }:{row['id']}")).fetchone()
                else:
                    tem = c.execute("SELECT 1 FROM evidences WHERE entidade_tipo=? AND entidade_id=? AND COALESCE(notas,'') LIKE 'Reconciliação assistida%' LIMIT 1", (tipo, row["id"])).fetchone()
                if tem: continue
                valores = {k: row.get(k) for k in campos if str(row.get(k) or "").strip()}
                if valores:
                    achados.append({"entidade_tipo": tipo, "entidade_id": row["id"], "nome": row.get("nome") or f"{tipo} #{row['id']}", "campos_legados": valores})
                    if len(achados) >= limite: break
            if len(achados) >= limite: break
    return {"total": len(achados), "limite": limite, "modo": "somente_leitura", "registros": achados,
            "aviso": "A auditoria não presume que cada texto seja uma fonte distinta. Revise antes de reconciliar; os campos originais serão preservados."}

@router.post("/migracao/fontes-legadas/reconciliar")
def reconciliar_fonte_legada(dados: dict = Body(...)):
    """Promove campos textuais para sources/evidences sem apagar nem reescrever o legado."""
    tipo = str(dados.get("entidade_tipo") or "").strip()
    try: eid = int(dados.get("entidade_id"))
    except (TypeError, ValueError): raise HTTPException(400, "entidade_id precisa ser inteiro.")
    if tipo not in _LEGADO_FONTES: raise HTTPException(400, "Tipo de entidade não suportado para reconciliação.")
    tabela, campos_def = _LEGADO_FONTES[tipo]
    with conn() as c:
        c.execute("BEGIN IMMEDIATE")
        cols = {r[1] for r in c.execute(f"PRAGMA table_info({tabela})")}
        campos = tuple(f for f in campos_def if f in cols)
        row = c.execute(f"SELECT * FROM {tabela} WHERE id=?", (eid,)).fetchone()
        if not row: raise HTTPException(404, "Registro não encontrado.")
        row = dict(row)
        valores = {k: str(row.get(k) or "").strip() for k in campos if str(row.get(k) or "").strip()}
        if not valores: raise HTTPException(400, "Este registro não contém texto legado para reconciliar.")
        alvo_tipo = {"relation":"relation", "work_agent":"work_agent", "manifestation_agent":"manifestation_agent"}.get(tipo)
        alvo_id = None
        if alvo_tipo:
            prefixo = {"relation":"r", "work_agent":"wa", "manifestation_agent":"ma"}[tipo]
            alvo_id = f"{prefixo}:{eid}"
            ja = c.execute("SELECT id FROM evidences WHERE alvo_tipo=? AND alvo_id IN (?,?) AND COALESCE(notas,'') LIKE 'Reconciliação assistida%' LIMIT 1", (alvo_tipo, str(eid), alvo_id)).fetchone()
        else:
            ja = c.execute("SELECT id FROM evidences WHERE entidade_tipo=? AND entidade_id=? AND COALESCE(notas,'') LIKE 'Reconciliação assistida%' LIMIT 1", (tipo, eid)).fetchone()
        if ja: raise HTTPException(409, "Este registro já possui evidência vinculada; revise-a em vez de criar outra automaticamente.")
        nome_col = next((x for x in ("titulo", "nome", "tipo_aparicao", "tipo", "papel") if x in cols), None)
        nome = row.get(nome_col) if nome_col else f"{tipo} #{eid}"
        principal = valores.get("fonte") or valores.get("referencia") or valores.get("notas") or str(nome)
        titulo = f"Registro legado — {nome}: {principal[:180]}"
        ref = "\n".join(f"{k}: {v}" for k, v in valores.items())
        cur = c.execute("INSERT INTO sources(titulo,tipo,referencia,notas) VALUES(?,?,?,?)", (titulo, "registro legado", ref, "Criado por reconciliação assistida. Texto original preservado na ficha de origem."))
        sid = cur.lastrowid
        afirmacao = f"Registro legado preservado como referência documental de {nome}. Campos originais: {', '.join(valores)}."
        ecampos = {"source_id": sid, "entidade_tipo": tipo if tipo not in {"relation", "work_agent", "manifestation_agent"} else ("work" if tipo != "relation" else "work"),
                   "entidade_id": eid if tipo not in {"relation", "work_agent", "manifestation_agent"} else (row.get("origem_id") or row.get("work_id") or row.get("manifestation_id")),
                   "afirmacao": afirmacao, "notas": "Reconciliação assistida; revisar pertinência e alvo da afirmação."}
        if alvo_tipo:
            ecampos["alvo_tipo"] = alvo_tipo; ecampos["alvo_id"] = alvo_id
            if ecampos["entidade_id"] is None: raise HTTPException(400, "Não foi possível determinar a entidade contextual do registro.")
            # relation may have origin entity types other than work; normalize from the row.
            if tipo == "relation": ecampos["entidade_tipo"] = row.get("origem_tipo") or "work"; ecampos["entidade_id"] = row.get("origem_id")
            elif tipo == "work_agent": ecampos["entidade_tipo"] = "work"; ecampos["entidade_id"] = row.get("work_id")
            elif tipo == "manifestation_agent":
                m = c.execute("SELECT work_id FROM manifestations WHERE id=?", (row.get("manifestation_id"),)).fetchone()
                ecampos["entidade_tipo"] = "work"; ecampos["entidade_id"] = m["work_id"] if m else None
            if ecampos["entidade_id"] is None: raise HTTPException(400, "Não foi possível determinar a entidade contextual do registro.")
        c.execute("INSERT INTO evidences(source_id,entidade_tipo,entidade_id,afirmacao,alvo_tipo,alvo_id,notas,estado) VALUES(?,?,?,?,?,?,?,'revisao_necessaria')",
                  (ecampos["source_id"], ecampos["entidade_tipo"], ecampos["entidade_id"], ecampos["afirmacao"], ecampos.get("alvo_tipo"), ecampos.get("alvo_id"), ecampos["notas"]))
        return {"ok": True, "source_id": sid, "entidade_tipo": tipo, "entidade_id": eid, "campos_preservados": list(valores), "estado_evidencia": "revisao_necessaria"}
