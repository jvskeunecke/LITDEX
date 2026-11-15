"""Vocabulário, relações e perfis (recortes de pesquisa).

Regra central: papéis de pessoa em obra ou em edição vivem nas tabelas canônicas
(`work_agents`, `manifestation_agents`). Uma hipótese de autoria pode existir como
relação; ao ser confirmada, é promovida ao registro canônico e deixa de ser aresta.
"""
import sqlite3

from fastapi import APIRouter, Body, HTTPException, Request

from core import entidades as E
from core.datas import ano_num
from core.db import conn, lista
from core.erros import ErroDominio
from core.evidencias import marcar_revisao
from core.relacoes import adicionar, relacoes_de, RELACAO_PARA_PAPEL
from core.texto import normalizar
from core.vocab import ENTIDADES, RELACOES, validar, vocab_publico
from .comum import perfil_ativo

router = APIRouter(prefix="/api")

STATUS = {"documentada", "hipotese"}


@router.get("/vocab")
def vocab():
    return vocab_publico()


def _id(rid, prefixos=("r",)):
    """Aceita '12', 'r12', 'r:12' (e os prefixos wa:/ma: quando pedido)."""
    texto = str(rid).strip()
    for p in prefixos:
        if texto.startswith(p):
            texto = texto[len(p):].lstrip(":")
            break
    try:
        return int(texto)
    except (TypeError, ValueError):
        raise HTTPException(400, "identificador inválido")


# ------------------------------------------------------------------ relações
@router.post("/relacoes/lote")
def criar_relacoes_lote(request: Request, dados: dict = Body(...)):
    """Cria um lote de relações em uma única transação SQLite.

    O formato é {"relacoes": [{...}, ...]}. Toda a lista é validada antes da
    primeira escrita; a transação usa BEGIN IMMEDIATE e qualquer erro reverte o lote.
    """
    itens = dados.get("relacoes") if isinstance(dados, dict) else None
    if not isinstance(itens, list) or not itens:
        raise HTTPException(400, "Envie uma lista não vazia no campo 'relacoes'.")
    if len(itens) > 500:
        raise HTTPException(400, "O lote excede o limite de 500 relações.")
    pid = perfil_ativo(request)
    try:
        with conn() as c:
            c.execute("BEGIN IMMEDIATE")
            # pré-validação sem escrita: estrutura, participantes, predicado e mediação
            for idx, item in enumerate(itens, 1):
                if not isinstance(item, dict):
                    raise HTTPException(400, f"Item {idx}: relação inválida.")
                ot, dt, tipo = item.get("origem_tipo"), item.get("destino_tipo"), item.get("tipo")
                try:
                    oi, di = int(item.get("origem_id")), int(item.get("destino_id"))
                except (TypeError, ValueError):
                    raise HTTPException(400, f"Item {idx}: IDs de origem/destino inválidos.")
                if ot not in ENTIDADES or dt not in ENTIDADES:
                    raise HTTPException(400, f"Item {idx}: tipo de entidade inválido.")
                msg = validar(tipo, ot, dt)
                if msg:
                    raise HTTPException(400, f"Item {idx}: {msg}")
                if (ot, oi) == (dt, di):
                    raise HTTPException(400, f"Item {idx}: uma ficha não pode relacionar-se consigo mesma.")
                E.exigir(c, ot, oi)
                E.exigir(c, dt, di)
                if item.get("via_tipo"):
                    if item["via_tipo"] not in ENTIDADES:
                        raise HTTPException(400, f"Item {idx}: tipo de mediação inválido.")
                    try:
                        E.exigir(c, item["via_tipo"], int(item.get("via_id")))
                    except (TypeError, ValueError):
                        raise HTTPException(400, f"Item {idx}: ID de mediação inválido.")
            criadas = []
            for idx, item in enumerate(itens, 1):
                try:
                    rid, duplicada = adicionar(c, item, pid)
                    criadas.append({"id": rid, "duplicado": bool(duplicada)})
                except ErroDominio as exc:
                    raise HTTPException(exc.status, f"Item {idx}: {exc.mensagem}") from exc
            return {"ok": True, "total": len(criadas), "relacoes": criadas, "atomico": True}
    except HTTPException:
        raise
    except ErroDominio:
        raise
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, f"Conflito de integridade; nenhuma relação do lote foi gravada: {exc}") from exc
    except Exception as exc:
        raise HTTPException(500, f"Falha no lote; a transação foi revertida: {exc}") from exc


@router.post("/relacoes")
def criar_relacao(request: Request, dados: dict = Body(...)):
    with conn() as c:
        rid, dup = adicionar(c, dados, perfil_ativo(request))
    return {"id": rid, "duplicado": dup}


@router.get("/entidades/{tipo}/{eid}/relacoes")
def relacoes(tipo: str, eid: int):
    E.ent(tipo)
    with conn() as c:
        return relacoes_de(c, tipo, eid)


@router.patch("/relacoes/{rid}")
def editar_relacao(rid: str, dados: dict = Body(...)):
    """Edita metadados e estrutura da afirmação relacional.

    Uma mudança de participantes, predicado, rótulo ou mediação altera a afirmação
    sustentada; as evidências ligadas ao alvo ficam marcadas para revisão explícita.
    """
    # --- papel canônico de obra
    if rid.startswith("wa:"):
        pk = _id(rid, ("wa:",))
        with conn() as c:
            old = c.execute("SELECT * FROM work_agents WHERE id=?", (pk,)).fetchone()
            if not old:
                raise HTTPException(404, "participação não encontrada")
            old = dict(old)
            try:
                author_id = int(dados.get("author_id", old["author_id"]))
                work_id = int(dados.get("work_id", old["work_id"]))
            except (TypeError, ValueError):
                raise HTTPException(400, "pessoa ou obra inválida")
            papel = (dados.get("papel", old["papel"]) or "").strip()
            if papel not in E.PAPEIS_OBRA:
                raise HTTPException(400, "papel de agente da obra inválido")
            E.exigir(c, "author", author_id)
            E.exigir(c, "work", work_id)
            ano = str(dados.get("ano", old.get("ano") or "")).strip() or None
            fonte = str(dados.get("fonte", old.get("fonte") or "")).strip() or None
            notas = str(dados.get("notas", old.get("notas") or "")).strip() or None
            mudou = (author_id, work_id, papel) != (old["author_id"], old["work_id"], old["papel"])
            try:
                c.execute("""UPDATE work_agents SET author_id=?,work_id=?,papel=?,ano=?,ano_num=?,
                             fonte=?,notas=? WHERE id=?""",
                          (author_id, work_id, papel, ano, ano_num(ano), fonte, notas, pk))
                if papel == "autor_principal":
                    # um só principal por obra: rebaixa os demais sem apagar histórico
                    for r in c.execute("""SELECT id FROM work_agents WHERE work_id=?
                                          AND papel='autor_principal' AND id<>?""", (work_id, pk)):
                        c.execute("UPDATE work_agents SET papel='coautor' WHERE id=?", (r["id"],))
            except sqlite3.IntegrityError:
                raise HTTPException(409, "já existe esse mesmo papel para esta pessoa e obra")
            if mudou:
                marcar_revisao(c, "work_agent", [pk],
                               "O agente, a obra ou o papel desta participação foi alterado; "
                               "confirme se a evidência ainda sustenta a nova afirmação.")
        return {"ok": True, "id": f"wa:{pk}", "revisao_evidencias": bool(mudou)}

    # --- crédito canônico de edição
    if rid.startswith("ma:"):
        pk = _id(rid, ("ma:",))
        with conn() as c:
            old = c.execute("SELECT * FROM manifestation_agents WHERE id=?", (pk,)).fetchone()
            if not old:
                raise HTTPException(404, "crédito de manifestação não encontrado")
            old = dict(old)
            try:
                author_id = int(dados.get("author_id", old["author_id"]))
                manifestation_id = int(dados.get("manifestation_id", old["manifestation_id"]))
            except (TypeError, ValueError):
                raise HTTPException(400, "pessoa ou manifestação inválida")
            papel = (dados.get("papel", old["papel"]) or "").strip()
            if papel not in E.PAPEIS_MANIFESTACAO:
                raise HTTPException(400, "papel de agente da manifestação inválido")
            E.exigir(c, "author", author_id)
            if not c.execute("SELECT 1 FROM manifestations WHERE id=?", (manifestation_id,)).fetchone():
                raise HTTPException(404, "manifestação não encontrada")
            fonte = str(dados.get("fonte", old.get("fonte") or "")).strip() or None
            notas = str(dados.get("notas", old.get("notas") or "")).strip() or None
            mudou = (author_id, manifestation_id, papel) != (old["author_id"], old["manifestation_id"], old["papel"])
            try:
                c.execute("""UPDATE manifestation_agents SET author_id=?,manifestation_id=?,papel=?,
                             fonte=?,notas=? WHERE id=?""",
                          (author_id, manifestation_id, papel, fonte, notas, pk))
            except sqlite3.IntegrityError:
                raise HTTPException(409, "já existe esse mesmo papel para esta pessoa e manifestação")
            if mudou:
                marcar_revisao(c, "manifestation_agent", [pk],
                               "O agente, a manifestação ou o papel deste crédito foi alterado; "
                               "confirme se a evidência ainda sustenta a nova afirmação.")
        return {"ok": True, "id": f"ma:{pk}", "revisao_evidencias": bool(mudou)}

    # --- relação genérica
    pk = _id(rid)
    escalares = {k for k in ("rotulo", "ano", "notas", "fonte", "estatuto") if k in dados}
    estruturais = {k for k in ("origem_tipo", "origem_id", "destino_tipo", "destino_id",
                               "tipo", "via_tipo", "via_id") if k in dados}
    for k in ("ano", "rotulo", "notas", "fonte"):
        if k in dados:
            dados[k] = str(dados.get(k) or "").strip() or None
    if "estatuto" in dados and dados["estatuto"] not in STATUS:
        raise HTTPException(400, "estatuto inválido")
    if not escalares and not estruturais:
        return {"ok": True}
    with conn() as c:
        row = c.execute("SELECT * FROM relations WHERE id=?", (pk,)).fetchone()
        if not row:
            raise HTTPException(404, "relação não encontrada")
        old = dict(row)
        novo = dict(old)
        for k in escalares:
            novo[k] = dados[k]
        if "ano" in escalares:
            novo["ano_num"] = ano_num(novo["ano"])
        for k in ("origem_tipo", "destino_tipo", "tipo"):
            if k in dados:
                novo[k] = str(dados[k] or "").strip() or None
        for k in ("origem_id", "destino_id"):
            if k in dados:
                try:
                    novo[k] = int(dados[k])
                except (TypeError, ValueError):
                    raise HTTPException(400, f"{k} precisa ser um ID numérico")
        if "via_tipo" in dados or "via_id" in dados:
            vt = dados.get("via_tipo", old.get("via_tipo"))
            vi = dados.get("via_id", old.get("via_id"))
            if not vt:
                novo["via_tipo"], novo["via_id"] = None, None
            else:
                if vt not in ENTIDADES:
                    raise HTTPException(400, "tipo de mediação inválido")
                try:
                    vi = int(vi)
                except (TypeError, ValueError):
                    raise HTTPException(400, "selecione uma ficha mediadora")
                E.exigir(c, vt, vi)
                novo["via_tipo"], novo["via_id"] = vt, vi
        if estruturais:
            if novo["tipo"] not in RELACOES:
                raise HTTPException(400, "tipo de relação inválido")
            if novo["tipo"] == "publicado_em":
                raise HTTPException(400, "publicação em periódico deve ser representada por uma manifestação")
            erro = validar(novo["tipo"], novo["origem_tipo"], novo["destino_tipo"])
            if erro:
                raise HTTPException(400, erro)
            if (novo["origem_tipo"], novo["origem_id"]) == (novo["destino_tipo"], novo["destino_id"]):
                raise HTTPException(400, "não pode relacionar uma ficha com ela mesma")
            E.exigir(c, novo["origem_tipo"], novo["origem_id"])
            E.exigir(c, novo["destino_tipo"], novo["destino_id"])
            if novo.get("via_tipo"):
                E.exigir(c, novo["via_tipo"], novo["via_id"])
            if novo["tipo"] == "liga" and not (novo.get("rotulo") or "").strip():
                raise HTTPException(400, "em ligação livre, informe um rótulo")

        # Hipótese de autoria confirmada deixa de ser aresta e vira participação canônica.
        virou_agente = None
        if (novo.get("estatuto") == "documentada" and old.get("estatuto") == "hipotese"
                and novo.get("origem_tipo") == "author" and novo.get("destino_tipo") == "work"
                and novo.get("tipo") in RELACAO_PARA_PAPEL):
            papel = RELACAO_PARA_PAPEL[novo["tipo"]]
            if novo["tipo"] == "autor_de":
                principal = E.autor_principal(c, novo["destino_id"])
                papel = "autor_principal" if principal in (None, novo["origem_id"]) else "coautor"
            ex = c.execute("SELECT id FROM work_agents WHERE work_id=? AND author_id=? AND papel=?",
                           (novo["destino_id"], novo["origem_id"], papel)).fetchone()
            if ex:
                virou_agente = ex["id"]
            else:
                virou_agente = c.execute("""INSERT INTO work_agents(work_id,author_id,papel,ordem,ano,ano_num,
                                            fonte,notas) VALUES(?,?,?,?,?,?,?,?)""",
                                         (novo["destino_id"], novo["origem_id"], papel,
                                          c.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM work_agents "
                                                    "WHERE work_id=?", (novo["destino_id"],)).fetchone()[0],
                                          novo.get("ano"), ano_num(novo.get("ano")),
                                          novo.get("fonte"), novo.get("notas"))).lastrowid
            marcar_revisao(c, "relation", [pk],
                           "A hipótese foi confirmada e convertida em participação canônica; "
                           "revise a evidência vinculada.")
            c.execute("DELETE FROM relations WHERE id=?", (pk,))
            return {"ok": True, "convertida": f"wa:{virou_agente}"}

        mudou = any(novo.get(k) != old.get(k) for k in
                    ("origem_tipo", "origem_id", "destino_tipo", "destino_id", "tipo",
                     "rotulo", "via_tipo", "via_id"))
        cols = [k for k in ("origem_tipo", "origem_id", "destino_tipo", "destino_id", "tipo",
                            "rotulo", "via_tipo", "via_id", "ano", "ano_num", "notas", "fonte",
                            "estatuto") if k in dados or ("ano" in dados and k == "ano_num")]
        if cols:
            c.execute(f"UPDATE relations SET {', '.join(k + '=?' for k in cols)} WHERE id=?",
                      (*[novo.get(k) for k in cols], pk))
        if mudou:
            marcar_revisao(c, "relation", [pk],
                           "Os participantes, o tipo, o rótulo ou a mediação da relação foi alterado; "
                           "confirme se a evidência ainda sustenta a nova afirmação.")
    return {"ok": True, "id": f"r:{pk}", "revisao_evidencias": bool(mudou)}


@router.delete("/relacoes/{rid}")
def apagar_relacao(rid: str):
    with conn() as c:
        if rid.startswith("wa:"):
            pk = _id(rid, ("wa:",))
            if not c.execute("SELECT 1 FROM work_agents WHERE id=?", (pk,)).fetchone():
                raise HTTPException(404, "participação não encontrada")
            marcar_revisao(c, "work_agent", [pk],
                           "A participação vinculada à evidência foi removida; reveja o registro documental.")
            c.execute("DELETE FROM work_agents WHERE id=?", (pk,))
        elif rid.startswith("ma:"):
            pk = _id(rid, ("ma:",))
            if not c.execute("SELECT 1 FROM manifestation_agents WHERE id=?", (pk,)).fetchone():
                raise HTTPException(404, "crédito não encontrado")
            marcar_revisao(c, "manifestation_agent", [pk],
                           "O crédito de manifestação vinculado à evidência foi removido; reveja o registro.")
            c.execute("DELETE FROM manifestation_agents WHERE id=?", (pk,))
        else:
            pk = _id(rid)
            marcar_revisao(c, "relation", [pk],
                           "A relação vinculada à evidência foi removida; reveja se a fonte ainda "
                           "sustenta alguma afirmação.")
            c.execute("DELETE FROM relations WHERE id=?", (pk,))
    return {"ok": True}


# ------------------------------------------------------------------ perfis
# "Geral" = tudo (não é uma linha da tabela). Um perfil é um recorte de pesquisa sobre o MESMO
# banco: o que se cria dentro dele já está no Geral; fichas antigas podem ser anexadas sem copiar.
@router.get("/perfis")
def perfis():
    with conn() as c:
        return lista(c, """SELECT p.id,p.nome,p.notas,COUNT(i.entity_id) AS n FROM profiles p
                           LEFT JOIN profile_items i ON i.profile_id=p.id GROUP BY p.id ORDER BY p.nome""")


@router.post("/perfis")
def criar_perfil(dados: dict = Body(...)):
    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise HTTPException(400, "dê um nome ao perfil")
    with conn() as c:
        try:
            cur = c.execute("INSERT INTO profiles(nome,notas) VALUES(?,?)", (nome, dados.get("notas")))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "já existe um perfil com esse nome")
    return {"id": cur.lastrowid}


@router.patch("/perfis/{pid}")
def editar_perfil(pid: int, dados: dict = Body(...)):
    campos = {k: dados[k] for k in ("nome", "notas") if k in dados}
    if "nome" in campos and not (campos["nome"] or "").strip():
        raise HTTPException(400, "nome vazio")
    if not campos:
        return {"ok": True}
    with conn() as c:
        try:
            c.execute(f"UPDATE profiles SET {', '.join(f'{k}=?' for k in campos)} WHERE id=?",
                      (*campos.values(), pid))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "já existe um perfil com esse nome")
    return {"ok": True}


@router.delete("/perfis/{pid}")
def apagar_perfil(pid: int):
    """Apaga só o recorte; nenhuma ficha é removida."""
    with conn() as c:
        c.execute("DELETE FROM profiles WHERE id=?", (pid,))
    return {"ok": True}


@router.get("/perfis/{pid}/itens")
def itens(pid: int):
    out = {}
    with conn() as c:
        for t in ENTIDADES:
            ids = E.ids_do_perfil(c, pid, t) or set()
            out[t] = sorted(({"id": i, "nome": E.nome_de(c, t, i)} for i in ids if E.existe(c, t, i)),
                            key=lambda x: (x["nome"] or "").lower())
    return out


@router.post("/perfis/{pid}/itens")
def anexar(pid: int, dados: dict = Body(...)):
    with conn() as c:
        if not c.execute("SELECT 1 FROM profiles WHERE id=?", (pid,)).fetchone():
            raise HTTPException(404, "perfil não existe")
        try:
            eid = int(dados.get("id", 0))
        except (TypeError, ValueError):
            raise HTTPException(400, "id inválido")
        E.exigir(c, dados.get("tipo"), eid)
        E.anexar_perfil(c, pid, dados["tipo"], eid)
    return {"ok": True}


@router.delete("/perfis/{pid}/itens/{tipo}/{eid}")
def desanexar(pid: int, tipo: str, eid: int):
    with conn() as c:
        c.execute("DELETE FROM profile_items WHERE profile_id=? AND entity_tipo=? AND entity_id=?",
                  (pid, tipo, eid))
    return {"ok": True}
