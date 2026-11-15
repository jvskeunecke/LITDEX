"""Operações de evidência usadas por vários módulos.

Centraliza a marcação de revisão para que todo alvo use **as mesmas formas de id**
(`12`, `r12`, `r:12`, `wa:12`, `ma:12`). Antes, cada rota montava o prefixo à mão e
uma delas gravava `work:5` em vez de `wa:5` — a evidência nunca era reencontrada.
"""

FORMAS = {
    "relation": lambda i: (str(i), f"r{i}", f"r:{i}"),
    "work_agent": lambda i: (str(i), f"wa:{i}"),
    "manifestation_agent": lambda i: (str(i), f"ma:{i}"),
}


def marcar_revisao(c, alvo_tipo, ids, motivo):
    """Marca para revisão as evidências ligadas a uma afirmação específica."""
    montar = FORMAS.get(alvo_tipo)
    if not montar:
        return 0
    total = 0
    for i in ids:
        if i is None:
            continue
        formas = montar(i)
        marks = ",".join("?" for _ in formas)
        cur = c.execute(f"""UPDATE evidences
                            SET estado='revisao_necessaria', motivo_revisao=?
                            WHERE alvo_tipo=? AND alvo_id IN ({marks})""",
                        (motivo, alvo_tipo, *formas))
        total += cur.rowcount
    return total


def marcar_entidade(c, tipo, eid, motivo, estado="nao_sustenta"):
    """Marca as evidências cuja ficha deixou de existir."""
    return c.execute("""UPDATE evidences SET estado=?, motivo_revisao=?
                        WHERE entidade_tipo=? AND entidade_id=?""",
                     (estado, motivo, tipo, eid)).rowcount


def listar(c, entidade_tipo=None, entidade_id=None, source_id=None, alvo_tipo=None, alvo_id=None):
    q = ["SELECT e.*,s.titulo AS fonte_titulo,s.url AS fonte_url FROM evidences e "
         "LEFT JOIN sources s ON s.id=e.source_id WHERE 1=1"]
    args = []
    for campo, valor in (("e.entidade_tipo", entidade_tipo), ("e.entidade_id", entidade_id),
                         ("e.source_id", source_id), ("e.alvo_tipo", alvo_tipo), ("e.alvo_id", alvo_id)):
        if valor is not None:
            q.append(f"AND {campo}=?")
            args.append(valor)
    q.append("ORDER BY e.id")
    return [dict(r) for r in c.execute(" ".join(q), args)]
