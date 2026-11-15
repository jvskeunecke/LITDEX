"""Relações: leitura e criação. Uma relação liga duas entidades QUAISQUER e pode registrar
através de quê ela se deu (obra, periódico, evento, carta), quando e em que fonte."""
from .datas import ano_num
from .db import lista
from .erros import ErroDominio
from .vocab import RELACOES, ENTIDADES, validar
from . import entidades as E

# Papéis pessoa–obra ficam no registro canônico work_agents, não duplicados
# como relações genéricas. Os endpoints mantêm IDs namespaced (wa:<id>) para
# compatibilidade com a interface de edição de relações.
PAPEL_PARA_RELACAO = {
    "autor_principal": "autor_de", "coautor": "autor_de", "tradutor": "traduziu",
    "organizador": "organizou", "ilustrador": "ilustrou", "prefaciador": "prefaciou",
    "entrevistador": "entrevistou", "entrevistado": "entrevistado_em",
}
RELACAO_PARA_PAPEL = {v: k for k, v in PAPEL_PARA_RELACAO.items()}
RELACAO_PARA_PAPEL["autor_de"] = "coautor"


def rotulo_de(r, saindo):
    v = RELACOES.get(r["tipo"])
    if r["tipo"] == "liga" and r.get("rotulo"):
        return r["rotulo"]
    if not v:
        return r.get("rotulo") or r["tipo"]
    return v["direta"] if (saindo or v["simetrica"]) else v["inversa"]


def _rotulo_papel(papel, saindo):
    t = PAPEL_PARA_RELACAO.get(papel, "autor_de")
    if t == "autor_de" and papel == "autor_principal":
        return "é autor(a) principal de" if saindo else "tem como autor(a) principal"
    v = RELACOES.get(t, {})
    return v.get("direta" if saindo else "inversa", papel)


def _entrada(out, r, tipo_rel, papel, sentido, outro, **extra):
    base = {"id": r["id"], "tipo": tipo_rel, "familia": "autoria", "simetrica": False,
            "sentido": sentido, "rotulo": _rotulo_papel(papel, sentido == "saindo"),
            "outro": outro, "via": None, "ano": r.get("ano"), "nota": r.get("notas"),
            "fonte": r.get("fonte"), "estatuto": r.get("estatuto") or "documentada", "papel": papel}
    base.update(extra)
    out.append(base)


def relacoes_de(c, tipo, eid):
    rows = lista(c, """SELECT * FROM relations WHERE (origem_tipo=? AND origem_id=?)
                       OR (destino_tipo=? AND destino_id=?) ORDER BY id""", (tipo, eid, tipo, eid))
    out = []
    for r in rows:
        saindo = (r["origem_tipo"] == tipo and r["origem_id"] == eid)
        outro = E.resumo(c, r["destino_tipo"], r["destino_id"]) if saindo \
            else E.resumo(c, r["origem_tipo"], r["origem_id"])
        if not outro:
            continue
        v = RELACOES.get(r["tipo"], {})
        via = E.resumo(c, r["via_tipo"], r["via_id"]) if r.get("via_tipo") else None
        out.append({"id": f"r{r['id']}", "tipo": r["tipo"], "familia": v.get("familia", "livre"),
                    "simetrica": bool(v.get("simetrica")),
                    "sentido": "saindo" if saindo else "entrando",
                    "rotulo": rotulo_de(r, saindo), "outro": outro, "via": via,
                    "ano": r.get("ano"), "nota": r.get("notas"), "fonte": r.get("fonte"),
                    "estatuto": r.get("estatuto") or "documentada"})

    # Atribuições de papel são relações reais, mas armazenadas uma única vez na
    # tabela de participações. A ficha de obra e a ficha de pessoa consultam a
    # mesma linha; não há cópia paralela em relations.
    if tipo == "author":
        partes = lista(c, """SELECT wa.*,w.titulo AS outro_nome,w.id AS outro_id FROM work_agents wa
                            JOIN works w ON w.id=wa.work_id WHERE wa.author_id=?
                            ORDER BY w.titulo,wa.ordem,wa.id""", (eid,))
        for r in partes:
            if r["papel"] not in PAPEL_PARA_RELACAO:
                continue
            _entrada(out, r, PAPEL_PARA_RELACAO[r["papel"]], r["papel"], "saindo",
                     {"tipo": "work", "id": r["outro_id"], "nome": r["outro_nome"]},
                     id=f"wa:{r['id']}")
        # Papéis na edição concreta são distintos dos papéis gerais na obra: um
        # tradutor de uma edição não se torna automaticamente tradutor da obra.
        partes = lista(c, """SELECT ma.*,w.id AS work_id,w.titulo AS work_title,m.id AS manifestation_id,
                                    m.tipo_aparicao,m.ano_edicao,m.referencia,m.periodical_id,
                                    p.titulo AS periodical_title
                             FROM manifestation_agents ma
                             JOIN manifestations m ON m.id=ma.manifestation_id
                             JOIN works w ON w.id=m.work_id
                             LEFT JOIN periodicals p ON p.id=m.periodical_id
                             WHERE ma.author_id=? ORDER BY w.titulo,m.ed_num,m.id,ma.ordem""", (eid,))
        for r in partes:
            rel = PAPEL_PARA_RELACAO.get(r["papel"])
            if not rel:
                continue
            data = " · ".join(x for x in (r.get("tipo_aparicao"), r.get("ano_edicao"),
                                          r.get("periodical_title"), r.get("referencia")) if x)
            _entrada(out, r, rel, r["papel"], "saindo",
                     {"tipo": "work", "id": r["work_id"], "nome": r["work_title"]},
                     id=f"ma:{r['id']}", ano=None,
                     manifestacao={"id": r["manifestation_id"],
                                   "descricao": data or "manifestação sem data"})
    elif tipo == "work":
        partes = lista(c, """SELECT wa.*,a.nome AS outro_nome,a.id AS outro_id FROM work_agents wa
                            JOIN authors a ON a.id=wa.author_id WHERE wa.work_id=?
                            ORDER BY wa.ordem,wa.id""", (eid,))
        for r in partes:
            if r["papel"] not in PAPEL_PARA_RELACAO:
                continue
            _entrada(out, r, PAPEL_PARA_RELACAO[r["papel"]], r["papel"], "entrando",
                     {"tipo": "author", "id": r["outro_id"], "nome": r["outro_nome"]},
                     id=f"wa:{r['id']}")
    return sorted(out, key=lambda x: (x.get("outro", {}).get("nome", "").casefold(), str(x["id"])))


def _texto(d, chave, limite=None):
    v = (d.get(chave) or "").strip() or None
    return v[:limite] if (v and limite) else v


def adicionar(c, d, pid=None):
    """Adiciona uma relação documentada ou uma participação tipada de pessoa numa obra."""
    ot, oi, dt, di, tipo = (d.get("origem_tipo"), d.get("origem_id"),
                            d.get("destino_tipo"), d.get("destino_id"), d.get("tipo"))
    if ot not in ENTIDADES or dt not in ENTIDADES:
        raise ErroDominio("tipo de entidade inválido")
    try:
        oi, di = int(oi), int(di)
    except (TypeError, ValueError):
        raise ErroDominio("ids inválidos")
    msg = validar(tipo, ot, dt)
    if msg:
        raise ErroDominio(msg)
    if (ot, oi) == (dt, di):
        raise ErroDominio("não pode relacionar uma ficha com ela mesma")
    E.exigir(c, ot, oi)
    E.exigir(c, dt, di)
    if tipo == "publicado_em":
        raise ErroDominio("publicação em periódico não é uma relação manual: registre uma manifestação "
                          "na ficha da obra e vincule o periódico e, quando identificado, o fascículo")

    ano = _texto(d, "ano")
    fonte = _texto(d, "fonte")
    notas = _texto(d, "notas")
    rotulo = _texto(d, "rotulo")
    estatuto = (d.get("estatuto") or "documentada").strip()
    if estatuto not in {"documentada", "hipotese"}:
        raise ErroDominio("estatuto deve ser documentada ou hipotese")

    # Autoria e papéis autor–obra são gravados no registro canônico work_agents,
    # mesmo quando o pesquisador informa fonte/data/notas. Não se cria uma aresta
    # paralela que deixe o Fichário desatualizado.
    papel = RELACAO_PARA_PAPEL.get(tipo)
    if papel and ot == "author" and dt == "work" and estatuto == "documentada":
        if tipo == "autor_de":
            atual = E.autor_principal(c, di)
            papel = "autor_principal" if atual in (None, oi) else "coautor"
        ja_coautor = c.execute("SELECT id FROM work_agents WHERE work_id=? AND author_id=? AND papel='coautor'",
                               (di, oi)).fetchone()
        if papel == "autor_principal" and ja_coautor:
            # promove a linha existente em vez de criar uma segunda participação
            c.execute("""UPDATE work_agents SET papel='autor_principal', ano=COALESCE(?,ano),
                         ano_num=COALESCE(?,ano_num), fonte=COALESCE(?,fonte), notas=COALESCE(?,notas)
                         WHERE id=?""", (ano, ano_num(ano), fonte, notas, ja_coautor["id"]))
            rid, duplicada = ja_coautor["id"], False
        else:
            ex = c.execute("SELECT id FROM work_agents WHERE work_id=? AND author_id=? AND papel=?",
                           (di, oi, papel)).fetchone()
            if ex:
                c.execute("""UPDATE work_agents SET ano=COALESCE(?,ano),ano_num=COALESCE(?,ano_num),
                             fonte=COALESCE(?,fonte),notas=COALESCE(?,notas) WHERE id=?""",
                          (ano, ano_num(ano), fonte, notas, ex["id"]))
                rid, duplicada = ex["id"], True
            else:
                ordem = c.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM work_agents WHERE work_id=?",
                                  (di,)).fetchone()[0]
                rid = c.execute("""INSERT INTO work_agents(work_id,author_id,papel,ordem,ano,ano_num,fonte,notas)
                                   VALUES(?,?,?,?,?,?,?,?)""",
                                (di, oi, papel, ordem, ano, ano_num(ano), fonte, notas)).lastrowid
                duplicada = False
        if papel == "autor_principal":
            outro = c.execute("""SELECT id FROM work_agents WHERE work_id=? AND papel='autor_principal'
                                 AND id<>?""", (di, rid)).fetchall()
            for r in outro:
                c.execute("UPDATE work_agents SET papel='coautor' WHERE id=?", (r["id"],))
        for t, i in ((ot, oi), (dt, di)):
            E.anexar_perfil(c, pid, t, i)
        return f"wa:{rid}", duplicada

    vt, vi = d.get("via_tipo") or None, d.get("via_id") or None
    if vt and not vi:
        raise ErroDominio("a mediação precisa de tipo e de ficha")
    if vi and not vt:
        raise ErroDominio("a mediação precisa de tipo e de ficha")
    if vt:
        if vt not in ENTIDADES:
            raise ErroDominio("tipo de mediação inválido")
        try:
            vi = int(vi)
        except (TypeError, ValueError):
            raise ErroDominio("mediação inválida")
        E.exigir(c, vt, vi)
    if tipo == "liga" and not rotulo:
        raise ErroDominio("em «ligação livre», diga qual é a ligação (rótulo)")

    # Distinguir ocorrências documentais. Uma relação só é duplicata quando
    # participantes, tipo, rótulo, mediação, data e fonte coincidem. NULL também
    # coincide com NULL: uma relação sem data não se funde com uma datada.
    q = ("SELECT id FROM relations WHERE tipo=? AND ((origem_tipo=? AND origem_id=? "
         "AND destino_tipo=? AND destino_id=?)")
    args = [tipo, ot, oi, dt, di]
    if RELACOES[tipo]["simetrica"]:
        q += " OR (origem_tipo=? AND origem_id=? AND destino_tipo=? AND destino_id=?)"
        args += [dt, di, ot, oi]
    q += (") AND COALESCE(rotulo,'')=COALESCE(?,'') AND COALESCE(via_tipo,'')=COALESCE(?,'') "
          "AND COALESCE(via_id,0)=COALESCE(?,0) AND COALESCE(ano,'')=COALESCE(?,'') "
          "AND COALESCE(fonte,'')=COALESCE(?,'') AND COALESCE(notas,'')=COALESCE(?,'') "
          "AND COALESCE(estatuto,'documentada')=COALESCE(?,'documentada')")
    args += [rotulo, vt, vi, ano, fonte, notas, estatuto]
    ex = c.execute(q, args).fetchone()
    if ex:
        return f"r:{ex['id']}", True
    cur = c.execute("""INSERT INTO relations(origem_tipo,origem_id,destino_tipo,destino_id,tipo,notas,
                       rotulo,via_tipo,via_id,ano,ano_num,fonte,estatuto)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (ot, oi, dt, di, tipo, notas, rotulo, vt, vi, ano, ano_num(ano), fonte, estatuto))
    for t, i in ((ot, oi), (dt, di), (vt, vi)):
        if t:
            E.anexar_perfil(c, pid, t, i)
    return f"r:{cur.lastrowid}", False
