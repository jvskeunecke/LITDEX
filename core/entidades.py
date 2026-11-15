"""Registro das entidades e operações que valem para todas elas.

Desde a v14, autoria não é coluna: `works.author_id` deixou de existir e a fonte
canônica é `work_agents`. Os helpers `autor_principal` e `definir_autor_principal`
concentram essa regra para que nenhuma rota precise reimplementá-la.
"""
import json

from .datas import ano_num
from .erros import ErroDominio
from .vocab import ENTIDADES
from . import config, files

# tabela, coluna do nome, campos editáveis, campos de data -> coluna numérica, se aceita imagem
ENT = {
    "author": dict(tabela="authors", nome="nome",
                   campos={"nome", "variantes", "nascimento", "morte", "bio", "notas"},
                   datas={"nascimento": "nasc_num", "morte": "morte_num"}, imagem=True),
    "work": dict(tabela="works", nome="titulo",
                 campos={"titulo", "ano", "genero", "tipo", "notas"},
                 datas={"ano": "ano_num"}, imagem=True),
    "periodical": dict(tabela="periodicals", nome="titulo",
                       campos={"titulo", "tipo", "issn", "ano_inicio", "ano_fim", "notas"},
                       datas={"ano_inicio": "ini_num", "ano_fim": "fim_num"}, imagem=True),
    "event": dict(tabela="events", nome="nome",
                  campos={"nome", "tipo", "ano", "notas"}, datas={"ano": "ano_num"}, imagem=True),
    "media": dict(tabela="media", nome="nome", campos={"nome", "notas"}, datas={}, imagem=False),
    "institution": dict(tabela="institutions", nome="nome",
                        campos={"nome", "tipo", "fundacao", "extincao", "local", "notas"},
                        datas={}, imagem=False),
}
assert set(ENT) == set(ENTIDADES)

# papéis aceitos em cada escopo — uma lista, usada por API, grafo e interface
PAPEIS_OBRA = ("autor_principal", "coautor", "tradutor", "organizador", "ilustrador",
               "prefaciador", "entrevistador", "entrevistado")
PAPEIS_MANIFESTACAO = ("tradutor", "organizador", "ilustrador", "prefaciador",
                       "entrevistador", "entrevistado", "autor_principal", "coautor")


def ent(tipo):
    if tipo not in ENT:
        raise ErroDominio(f"tipo de entidade desconhecido: {tipo}", 404)
    return ENT[tipo]


def existe(c, tipo, eid):
    e = ent(tipo)
    return c.execute(f"SELECT 1 FROM {e['tabela']} WHERE id=?", (eid,)).fetchone() is not None


def nome_de(c, tipo, eid):
    e = ent(tipo)
    r = c.execute(f"SELECT {e['nome']} AS n FROM {e['tabela']} WHERE id=?", (eid,)).fetchone()
    return r["n"] if r else None


def resumo(c, tipo, eid):
    n = nome_de(c, tipo, eid)
    return {"tipo": tipo, "id": eid, "nome": n} if n is not None else None


def exigir(c, tipo, eid):
    if not existe(c, tipo, eid):
        raise ErroDominio(f"{ENTIDADES[tipo]['rotulo']} {eid} não existe", 404)


def preparar_campos(tipo, dados):
    """Filtra os campos editáveis e calcula as colunas numéricas de data."""
    e = ent(tipo)
    campos = {k: v for k, v in dados.items() if k in e["campos"]}
    if "variantes" in campos and not isinstance(campos["variantes"], str):
        campos["variantes"] = json.dumps(campos["variantes"], ensure_ascii=False)
    for k, v in list(campos.items()):
        if isinstance(v, str) and k not in ("bio", "notas"):
            campos[k] = v.strip()
        if k in e["datas"]:
            if not str(campos[k] or "").strip():
                campos[k] = None
            campos[e["datas"][k]] = ano_num(campos[k])
        elif k in ("tipo", "genero", "issn") and campos[k] in ("", None):
            campos[k] = None
    if "genero" in campos and campos["genero"] not in config.GENEROS:
        campos["genero"] = None
    if e["nome"] in campos and not str(campos[e["nome"]] or "").strip():
        raise ErroDominio("o nome/título não pode ficar vazio")
    return campos


# ------------------------------------------------------------------ autoria (fonte única)
def autor_principal(c, work_id):
    r = c.execute("""SELECT author_id FROM work_agents WHERE work_id=? AND papel='autor_principal'
                     ORDER BY ordem, id LIMIT 1""", (work_id,)).fetchone()
    return r["author_id"] if r else None


def definir_autor_principal(c, work_id, author_id, *, ano=None, fonte=None, notas=None):
    """Troca o autor principal de uma obra sem apagar o histórico do anterior.

    O antigo principal é rebaixado a coautor (preservando ano/fonte/notas); se a
    pessoa já era coautora, a linha é promovida em vez de duplicada.
    """
    if author_id is not None:
        exigir(c, "author", author_id)
    atual = c.execute("""SELECT id,author_id FROM work_agents WHERE work_id=? AND papel='autor_principal'
                         ORDER BY ordem, id LIMIT 1""", (work_id,)).fetchone()
    if author_id is None:
        if atual:
            c.execute("DELETE FROM work_agents WHERE id=?", (atual["id"],))
        return None
    if atual and atual["author_id"] == author_id:
        return atual["id"]
    if atual:
        c.execute("UPDATE work_agents SET papel='coautor' WHERE id=?", (atual["id"],))
    linha = c.execute("SELECT id FROM work_agents WHERE work_id=? AND author_id=? AND papel='coautor'",
                      (work_id, author_id)).fetchone()
    if linha:
        c.execute("UPDATE work_agents SET papel='autor_principal', ano=COALESCE(?,ano), "
                  "ano_num=COALESCE(?,ano_num), fonte=COALESCE(?,fonte), notas=COALESCE(?,notas) WHERE id=?",
                  (ano, ano_num(ano), fonte, notas, linha["id"]))
        return linha["id"]
    ordem = c.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM work_agents WHERE work_id=?", (work_id,)).fetchone()[0]
    return c.execute("""INSERT INTO work_agents(work_id,author_id,papel,ordem,ano,ano_num,fonte,notas)
                        VALUES(?,?,'autor_principal',?,?,?,?,?)""",
                     (work_id, author_id, ordem, ano, ano_num(ano), fonte, notas)).lastrowid


def limpar(c, tipo, eid):
    """Remove tudo que aponta para a entidade (relações, tags, lugares, perfis, imagens).

    Evidências não são apagadas: elas guardam trechos e fontes que podem interessar ao
    pesquisador. Ficam marcadas como `nao_sustenta`, com motivo, e aparecem no Diagnóstico.
    """
    e = ent(tipo)
    lote = files.novo_lote()
    c.execute("UPDATE relations SET via_tipo=NULL, via_id=NULL WHERE via_tipo=? AND via_id=?", (tipo, eid))
    removidas = c.execute("""SELECT id FROM relations
                             WHERE (origem_tipo=? AND origem_id=?) OR (destino_tipo=? AND destino_id=?)""",
                          (tipo, eid, tipo, eid)).fetchall()
    if removidas:
        ids = [r["id"] for r in removidas]
        marks = ",".join("?" for _ in ids)
        c.execute(f"""UPDATE evidences SET estado='nao_sustenta',
                      motivo_revisao='A relação à qual esta evidência se referia foi excluída com a ficha.'
                      WHERE alvo_tipo='relation' AND alvo_id IN ({marks})""",
                  [str(i) for i in ids] + [f"r:{i}" for i in ids] + [f"r{i}" for i in ids])
        c.execute(f"""DELETE FROM relations WHERE id IN ({marks})""", ids)
    c.execute("""UPDATE evidences SET estado='nao_sustenta',
                 motivo_revisao='A ficha à qual esta evidência se referia foi excluída.'
                 WHERE entidade_tipo=? AND entidade_id=?""", (tipo, eid))
    for t in ("entity_tags", "entity_places", "profile_items"):
        c.execute(f"DELETE FROM {t} WHERE entity_tipo=? AND entity_id=?", (tipo, eid))
    for r in c.execute("SELECT caminho FROM assets WHERE entity_tipo=? AND entity_id=?", (tipo, eid)).fetchall():
        files.mover_para_lixo(r["caminho"], lote)
    c.execute("DELETE FROM assets WHERE entity_tipo=? AND entity_id=?", (tipo, eid))
    if e["imagem"]:
        r = c.execute(f"SELECT imagem FROM {e['tabela']} WHERE id=?", (eid,)).fetchone()
        if r and r["imagem"]:
            files.mover_para_lixo(r["imagem"], lote)
    if tipo == "work":
        manifestacoes = c.execute("SELECT id,caminho FROM manifestations WHERE work_id=?", (eid,)).fetchall()
        ids_manifestacoes = [r["id"] for r in manifestacoes]
        if ids_manifestacoes:
            marks = ",".join("?" for _ in ids_manifestacoes)
            # evidências das edições também deixam de ter a que se referir
            c.execute(f"""UPDATE evidences SET estado='nao_sustenta',
                          motivo_revisao='A manifestação à qual esta evidência se referia foi excluída com a obra.'
                          WHERE entidade_tipo='manifestation' AND entidade_id IN ({marks})""", ids_manifestacoes)
            # Preserva manifestações de outras obras quando a edição continente é
            # excluída; apenas desfaz o vínculo para não violar FK nem apagar a filha.
            c.execute(f"UPDATE manifestations SET container_manifestation_id=NULL "
                      f"WHERE container_manifestation_id IN ({marks})", ids_manifestacoes)
            for r in manifestacoes:
                files.mover_para_lixo(r["caminho"], lote)
    if tipo == "periodical":
        issue_ids = [r["id"] for r in c.execute(
            "SELECT id FROM periodical_issues WHERE periodical_id=?", (eid,)).fetchall()]
        if issue_ids:
            marks = ",".join("?" for _ in issue_ids)
            c.execute(f"""UPDATE evidences SET estado='nao_sustenta',
                          motivo_revisao='O fascículo ao qual esta evidência se referia foi excluído com o periódico.'
                          WHERE entidade_tipo='issue' AND entidade_id IN ({marks})""", issue_ids)
            c.execute(f"UPDATE manifestations SET issue_id=NULL WHERE issue_id IN ({marks})", issue_ids)
        c.execute("UPDATE manifestations SET periodical_id=NULL WHERE periodical_id=?", (eid,))
    c.execute(f"DELETE FROM {e['tabela']} WHERE id=?", (eid,))


def anexar_perfil(c, pid, tipo, eid):
    """Põe a entidade no perfil (idempotente). pid None = perfil Geral (nada a fazer)."""
    if not pid:
        return
    if not c.execute("SELECT 1 FROM profiles WHERE id=?", (pid,)).fetchone():
        raise ErroDominio(f"perfil {pid} não existe", 404)
    c.execute("INSERT OR IGNORE INTO profile_items(profile_id,entity_tipo,entity_id) VALUES(?,?,?)",
              (pid, tipo, eid))


def ids_do_perfil(c, pid, tipo):
    """Conjunto de ids no perfil; None = sem filtro (Geral)."""
    if not pid:
        return None
    return {r["entity_id"] for r in c.execute(
        "SELECT entity_id FROM profile_items WHERE profile_id=? AND entity_tipo=?", (pid, tipo))}
