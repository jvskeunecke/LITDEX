"""Banco SQLite: esquema v14, migração não destrutiva e conexão.

A partir da v14 existe **uma** fonte de verdade para autoria (work_agents) e para
créditos de edição (manifestation_agents). As colunas legadas `works.author_id`,
`manifestations.tradutor` e `manifestations.organizador` são convertidas e removidas
na primeira abertura de um banco antigo; nada é descartado sem antes virar registro
canônico ou evidência em revisão.
"""
import json
import sqlite3
from contextlib import contextmanager

from . import config
from .datas import ano_num
from .texto import normalizar
from .vocab import LEGADO

_PERIODICALS_SQL = """
CREATE TABLE IF NOT EXISTS periodicals(
 id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, tipo TEXT, issn TEXT,
 ano_inicio TEXT, ano_fim TEXT, ini_num INTEGER, fim_num INTEGER,
 notas TEXT, imagem TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS authors(
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, variantes TEXT,
 nascimento TEXT, morte TEXT, nasc_num INTEGER, morte_num INTEGER,
 bio TEXT, notas TEXT, imagem TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS works(
 id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, ano TEXT, ano_num INTEGER,
 genero TEXT, tipo TEXT, notas TEXT, imagem TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS events(
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, tipo TEXT, ano TEXT, ano_num INTEGER,
 notas TEXT, imagem TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS media(
 id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, notas TEXT,
 criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS institutions(
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, tipo TEXT, fundacao TEXT, extincao TEXT,
 local TEXT, notas TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS work_media(
 work_id INTEGER REFERENCES works(id) ON DELETE CASCADE,
 media_id INTEGER REFERENCES media(id) ON DELETE CASCADE,
 ordem INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(work_id, media_id));
CREATE TABLE IF NOT EXISTS periodical_issues(
 id INTEGER PRIMARY KEY, periodical_id INTEGER NOT NULL REFERENCES periodicals(id) ON DELETE CASCADE,
 volume TEXT, numero TEXT, data TEXT, data_num INTEGER, titulo TEXT, referencia TEXT, notas TEXT,
 criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS manifestations(
 id INTEGER PRIMARY KEY, work_id INTEGER REFERENCES works(id) ON DELETE CASCADE,
 caminho TEXT NOT NULL DEFAULT '', formato TEXT,
 editora TEXT, ano_edicao TEXT, ed_num INTEGER, idioma TEXT, notas TEXT,
 local TEXT, fonte TEXT, paginas INTEGER,
 tipo_aparicao TEXT DEFAULT 'edição', periodical_id INTEGER REFERENCES periodicals(id) ON DELETE SET NULL,
 container_work_id INTEGER REFERENCES works(id) ON DELETE SET NULL, referencia TEXT,
 issue_id INTEGER REFERENCES periodical_issues(id) ON DELETE RESTRICT,
 container_manifestation_id INTEGER REFERENCES manifestations(id) ON DELETE RESTRICT,
 criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS work_agents(
 id INTEGER PRIMARY KEY, work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
 author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
 papel TEXT NOT NULL, ordem INTEGER NOT NULL DEFAULT 0, ano TEXT, ano_num INTEGER,
 fonte TEXT, notas TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(work_id,author_id,papel));
CREATE TABLE IF NOT EXISTS manifestation_agents(
 id INTEGER PRIMARY KEY, manifestation_id INTEGER NOT NULL REFERENCES manifestations(id) ON DELETE CASCADE,
 author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
 papel TEXT NOT NULL, ordem INTEGER NOT NULL DEFAULT 0, fonte TEXT, notas TEXT,
 criado_em TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(manifestation_id,author_id,papel));
CREATE TABLE IF NOT EXISTS tags(
 id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS entity_tags(
 entity_tipo TEXT, entity_id INTEGER, tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
 PRIMARY KEY(entity_tipo, entity_id, tag_id));
CREATE TABLE IF NOT EXISTS places(
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, lat REAL, lon REAL, tipo TEXT, contexto TEXT, notas TEXT,
 parent_id INTEGER REFERENCES places(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS genre_terms(
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
 parent_id INTEGER REFERENCES genre_terms(id) ON DELETE SET NULL,
 notas TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS work_genres(
 work_id INTEGER REFERENCES works(id) ON DELETE CASCADE,
 genre_id INTEGER REFERENCES genre_terms(id) ON DELETE CASCADE,
 ordem INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(work_id, genre_id));
CREATE TABLE IF NOT EXISTS entity_places(
 entity_tipo TEXT NOT NULL, entity_id INTEGER NOT NULL, place_id INTEGER REFERENCES places(id) ON DELETE CASCADE,
 papel TEXT NOT NULL DEFAULT '', ordem INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(entity_tipo, entity_id, place_id, papel));
CREATE TABLE IF NOT EXISTS relations(
 id INTEGER PRIMARY KEY, origem_tipo TEXT, origem_id INTEGER, destino_tipo TEXT, destino_id INTEGER,
 tipo TEXT, notas TEXT, rotulo TEXT, via_tipo TEXT, via_id INTEGER,
 ano TEXT, ano_num INTEGER, fonte TEXT, estatuto TEXT NOT NULL DEFAULT 'documentada',
 criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sources(
 id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, tipo TEXT, autor TEXT, data TEXT,
 url TEXT, identificador TEXT, referencia TEXT, notas TEXT,
 criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS evidences(
 id INTEGER PRIMARY KEY, source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
 entidade_tipo TEXT NOT NULL, entidade_id INTEGER NOT NULL, afirmacao TEXT NOT NULL,
 alvo_tipo TEXT, alvo_id TEXT, trecho TEXT, localizador TEXT, data_consulta TEXT, notas TEXT,
 estado TEXT NOT NULL DEFAULT 'vigente', motivo_revisao TEXT, criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS assets(
 id INTEGER PRIMARY KEY, entity_tipo TEXT, entity_id INTEGER, caminho TEXT,
 legenda TEXT, tipo_asset TEXT, ordem INTEGER DEFAULT 0,
 criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS profiles(
 id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, notas TEXT,
 criado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS profile_items(
 profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
 entity_tipo TEXT, entity_id INTEGER, PRIMARY KEY(profile_id, entity_tipo, entity_id));
"""

INDICES = [
    "CREATE INDEX IF NOT EXISTS i_rel_o ON relations(origem_tipo, origem_id)",
    "CREATE INDEX IF NOT EXISTS i_rel_d ON relations(destino_tipo, destino_id)",
    "CREATE INDEX IF NOT EXISTS i_man_w ON manifestations(work_id)",
    "CREATE INDEX IF NOT EXISTS i_pi ON profile_items(entity_tipo, entity_id)",
    "CREATE INDEX IF NOT EXISTS i_place_parent ON places(parent_id)",
    "CREATE INDEX IF NOT EXISTS i_work_genres_term ON work_genres(genre_id, work_id)",
    "CREATE INDEX IF NOT EXISTS i_work_agents_author ON work_agents(author_id, work_id)",
    "CREATE INDEX IF NOT EXISTS i_manifestation_agents_author ON manifestation_agents(author_id, manifestation_id)",
    "CREATE INDEX IF NOT EXISTS i_issues_periodical ON periodical_issues(periodical_id, data_num, volume, numero)",
    "CREATE INDEX IF NOT EXISTS i_evidences_entity ON evidences(entidade_tipo, entidade_id)",
    "CREATE INDEX IF NOT EXISTS i_evidences_source ON evidences(source_id)",
    "CREATE INDEX IF NOT EXISTS i_evidences_target ON evidences(alvo_tipo, alvo_id)",
]

VERSAO = 14

# avisos da última migração (mostrados no Diagnóstico; nunca interrompem o uso)
AVISOS = []


def _tabelas(c):
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _colunas(c, t):
    return {r[1] for r in c.execute(f"PRAGMA table_info({t})")}


def _lugar(c, nome, tipo=None):
    r = c.execute("SELECT id FROM places WHERE lower(nome)=lower(?)", (nome,)).fetchone()
    return r["id"] if r else c.execute("INSERT INTO places(nome,tipo) VALUES(?,?)", (nome, tipo)).lastrowid


def _legado_periodicals(c):
    """A versão do DeepSeek já tinha `periodicals` com outras colunas (nome, inicio, fim, cidade).
    Como o esquema só cria tabelas que faltam, a colisão deixava grafo e linha do tempo com erro 500.
    A tabela antiga é preservada (periodicals_v1) e reconstruída no formato atual."""
    cols = _colunas(c, "periodicals")
    if "titulo" in cols or "nome" not in cols:
        return
    c.execute("ALTER TABLE periodicals RENAME TO periodicals_v1")
    c.executescript(_PERIODICALS_SQL)
    for r in c.execute("SELECT * FROM periodicals_v1").fetchall():
        r = dict(r)
        notas = (r.get("notas") or "").strip()
        if r.get("editora"):
            notas = (f"Editora: {r['editora']}\n\n{notas}").strip()
        c.execute("""INSERT INTO periodicals(id,titulo,tipo,issn,ano_inicio,ano_fim,ini_num,fim_num,notas,imagem)
                     VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  (r["id"], r["nome"], r.get("tipo"), r.get("issn"), r.get("inicio"), r.get("fim"),
                   ano_num(r.get("inicio")), ano_num(r.get("fim")), notas or None, r.get("imagem")))
        if r.get("cidade"):
            c.execute("INSERT OR IGNORE INTO entity_places(entity_tipo,entity_id,place_id,papel,ordem) VALUES('periodical',?,?,?,0)",
                      (r["id"], _lugar(c, r["cidade"], "cidade"), "publicação"))


def _legado_deepseek(c):
    """Tabelas do DeepSeek que viram o modelo atual: coleções → perfis; papéis em periódicos
    e obras em edições de revista → relações."""
    t = _tabelas(c)
    if "collections" in t:
        for r in c.execute("SELECT * FROM collections").fetchall():
            c.execute("INSERT OR IGNORE INTO profiles(nome,notas) VALUES(?,?)",
                      (r["nome"], r["descricao"] if "descricao" in r.keys() else None))
            pid = c.execute("SELECT id FROM profiles WHERE nome=?", (r["nome"],)).fetchone()["id"]
            if "collection_items" in t:
                c.execute("INSERT OR IGNORE INTO profile_items(profile_id,entity_tipo,entity_id) "
                          "SELECT ?,entity_tipo,entity_id FROM collection_items WHERE collection_id=?", (pid, r["id"]))
    if "author_periodicals" in t:
        papel = {"editor": "editou", "diretor": "editou", "fundador": "fundou"}
        for r in c.execute("SELECT * FROM author_periodicals").fetchall():
            tipo = papel.get((r["papel"] or "").lower(), "colaborou_em")
            if not c.execute("SELECT 1 FROM relations WHERE tipo=? AND origem_tipo='author' AND origem_id=? "
                             "AND destino_tipo='periodical' AND destino_id=?",
                             (tipo, r["author_id"], r["periodical_id"])).fetchone():
                c.execute("INSERT INTO relations(origem_tipo,origem_id,destino_tipo,destino_id,tipo,notas) "
                          "VALUES('author',?,'periodical',?,?,?)",
                          (r["author_id"], r["periodical_id"], tipo, r["notas"]))
    if "work_in_issue" in t and "issues" in t and "rotulo" in _colunas(c, "issues"):
        for r in c.execute("SELECT w.work_id,i.periodical_id,i.rotulo,i.ano,w.paginas "
                           "FROM work_in_issue w JOIN issues i ON i.id=w.issue_id").fetchall():
            nota = ", ".join(x for x in (r["rotulo"], f"p. {r['paginas']}" if r["paginas"] else "") if x) or None
            c.execute("""INSERT INTO relations(origem_tipo,origem_id,destino_tipo,destino_id,tipo,notas,ano,ano_num)
                         VALUES('work',?,'periodical',?,'publicado_em',?,?,?)""",
                      (r["work_id"], r["periodical_id"], nota, r["ano"], ano_num(r["ano"])))
    if "midia" in _colunas(c, "works"):
        for r in c.execute("SELECT id,midia FROM works WHERE midia IS NOT NULL AND midia<>''").fetchall():
            nome = "texto verbal" if r["midia"].lower() == "literatura" else r["midia"].lower()
            m = c.execute("SELECT id FROM media WHERE nome=?", (nome,)).fetchone()
            mid = m["id"] if m else c.execute("INSERT INTO media(nome) VALUES(?)", (nome,)).lastrowid
            c.execute("INSERT OR IGNORE INTO work_media(work_id,media_id,ordem) VALUES(?,?,0)", (r["id"], mid))


def _caminhos_posix(c):
    """Windows grava 'library\\autor\\obra.pdf'; o navegador precisa de '/'. Idempotente."""
    for tabela, col in (("manifestations", "caminho"), ("authors", "imagem"), ("works", "imagem"),
                        ("periodicals", "imagem"), ("events", "imagem"), ("assets", "caminho")):
        if col in _colunas(c, tabela):
            c.execute(f"UPDATE {tabela} SET {col}=REPLACE({col}, char(92), '/') "
                      f"WHERE {col} LIKE '%'||char(92)||'%'")


def _alinhar_colunas(c):
    """Qualquer tabela que já exista com colunas a menos recebe as que faltam, comparando com
    o esquema esperado. Evita erro 500 por coluna ausente, seja qual for a origem do banco."""
    mem = sqlite3.connect(":memory:")
    mem.executescript(SCHEMA)
    mem.executescript(_PERIODICALS_SQL)
    existentes = _tabelas(c)
    for (t,) in mem.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        if t not in existentes:
            continue
        tem = _colunas(c, t)
        for _cid, nome, tipo, _nn, _df, _pk in mem.execute(f"PRAGMA table_info({t})").fetchall():
            if nome not in tem:
                c.execute(f"ALTER TABLE {t} ADD COLUMN {nome} {tipo or ''}")
    mem.close()


def _migrar_entity_places_papel(c):
    """Inclui o papel na identidade do vínculo geográfico, preservando registros antigos."""
    info = c.execute("PRAGMA table_info(entity_places)").fetchall()
    pk = {r["name"] for r in info if r["pk"]}
    if {"entity_tipo", "entity_id", "place_id", "papel"}.issubset(pk):
        return
    c.execute("ALTER TABLE entity_places RENAME TO entity_places_v7")
    c.execute("""CREATE TABLE entity_places(
        entity_tipo TEXT NOT NULL, entity_id INTEGER NOT NULL,
        place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
        papel TEXT NOT NULL DEFAULT '', ordem INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(entity_tipo,entity_id,place_id,papel))""")
    c.execute("""INSERT OR IGNORE INTO entity_places(entity_tipo,entity_id,place_id,papel,ordem)
                 SELECT entity_tipo,entity_id,place_id,COALESCE(papel,''),COALESCE(ordem,0)
                 FROM entity_places_v7""")
    c.execute("DROP TABLE entity_places_v7")


def _sincronizar_modelo_documental(c):
    """Projeta participações e fascículos sem inventar identidades quando faltam dados."""
    if "author_id" in _colunas(c, "works"):
        for r in c.execute("SELECT id,author_id FROM works WHERE author_id IS NOT NULL").fetchall():
            c.execute("INSERT OR IGNORE INTO work_agents(work_id,author_id,papel,ordem) "
                      "VALUES(?,?, 'autor_principal',0)", (r["id"], r["author_id"]))

    roles = {"autor_de": "coautor", "traduziu": "tradutor", "organizou": "organizador",
             "ilustrou": "ilustrador", "prefaciou": "prefaciador", "entrevistou": "entrevistador",
             "entrevistado_em": "entrevistado"}
    rows = c.execute("""SELECT id,origem_id AS aid,destino_id AS wid,tipo,ano,fonte,notas
                        FROM relations WHERE origem_tipo='author' AND destino_tipo='work'
                        AND tipo IN ('autor_de','traduziu','organizou','ilustrou','prefaciou',
                                     'entrevistou','entrevistado_em')""").fetchall()
    ids = []
    for r in rows:
        # A relação com data/fonte/notas é uma ocorrência documental: não a fundimos
        # numa participação única, pois isso apagaria a especificidade do registro.
        if any((r[k] or "").strip() for k in ("ano", "fonte", "notas")):
            continue
        papel = roles[r["tipo"]]
        principal = c.execute("SELECT author_id FROM work_agents WHERE work_id=? AND papel='autor_principal'",
                              (r["wid"],)).fetchone()
        if principal and principal["author_id"] == r["aid"]:
            papel = "autor_principal"
        c.execute("INSERT OR IGNORE INTO work_agents(work_id,author_id,papel,ordem) VALUES(?,?,?,0)",
                  (r["wid"], r["aid"], papel))
        ids.append(r["id"])
    if ids:
        c.executemany("DELETE FROM relations WHERE id=?", ((i,) for i in ids))

    if "tradutor" in _colunas(c, "manifestations") or "organizador" in _colunas(c, "manifestations"):
        cols = [x for x in ("tradutor", "organizador") if x in _colunas(c, "manifestations")]
        autores = c.execute("SELECT id,nome FROM authors").fetchall()
        idx = {}
        for a in autores:
            idx.setdefault(normalizar(a["nome"]), []).append(a["id"])
        for m in c.execute(f"SELECT id,{','.join(cols)} FROM manifestations").fetchall():
            for campo, papel in (("tradutor", "tradutor"), ("organizador", "organizador")):
                if campo not in cols:
                    continue
                valor = (m[campo] or "").strip()
                candidatos = idx.get(normalizar(valor), []) if valor else []
                if len(candidatos) == 1:
                    c.execute("INSERT OR IGNORE INTO manifestation_agents(manifestation_id,author_id,papel) "
                              "VALUES(?,?,?)", (m["id"], candidatos[0], papel))

    # Só infere fascículo a partir de indicação explícita no texto de referência;
    # nunca deduz número ou volume a partir de um ano ou nome de seção.
    import re
    for m in c.execute("""SELECT id,periodical_id,ano_edicao,referencia FROM manifestations
                          WHERE periodical_id IS NOT NULL AND issue_id IS NULL""").fetchall():
        ref = m["referencia"] or ""
        mv = re.search(r"\b(?:v(?:ol(?:ume)?)?\.?|volume)\s*([\w.-]+)", ref, re.I)
        mn = re.search(r"\b(?:n(?:[ºoúmúmero]*)?\.?|número)\s*([\w.-]+)", ref, re.I)
        if not (mv or mn):
            continue
        volume, numero = (mv.group(1) if mv else None), (mn.group(1) if mn else None)
        data_fasciculo = m["ano_edicao"]
        cur = c.execute("""SELECT id FROM periodical_issues WHERE periodical_id=?
                           AND COALESCE(volume,'')=COALESCE(?,'') AND COALESCE(numero,'')=COALESCE(?,'')
                           AND COALESCE(data,'')=COALESCE(?,'') ORDER BY id LIMIT 1""",
                        (m["periodical_id"], volume, numero, data_fasciculo)).fetchone()
        issue_id = cur["id"] if cur else c.execute(
            "INSERT INTO periodical_issues(periodical_id,volume,numero,data,data_num,referencia) "
            "VALUES(?,?,?,?,?,?)",
            (m["periodical_id"], volume, numero, data_fasciculo, ano_num(data_fasciculo), ref)).lastrowid
        c.execute("UPDATE manifestations SET issue_id=? WHERE id=?", (issue_id, m["id"]))


def _remover_coluna(c, tabela, coluna):
    """Remove uma coluna; se o SQLite for antigo, mantém e avisa (o código ignora)."""
    try:
        c.execute(f"ALTER TABLE {tabela} DROP COLUMN {coluna}")
        return True
    except sqlite3.OperationalError as e:
        AVISOS.append(f"não foi possível remover {tabela}.{coluna} ({e}); a coluna será ignorada")
        return False


def _remover_legado_v14(c):
    """Converte autoria e créditos legados em registros canônicos e remove as colunas."""
    if "author_id" in _colunas(c, "works"):
        for r in c.execute("SELECT id,author_id FROM works WHERE author_id IS NOT NULL").fetchall():
            tem_principal = c.execute(
                "SELECT author_id FROM work_agents WHERE work_id=? AND papel='autor_principal' LIMIT 1",
                (r["id"],)).fetchone()
            if tem_principal is None:
                c.execute("INSERT OR IGNORE INTO work_agents(work_id,author_id,papel,ordem) "
                          "VALUES(?,?,'autor_principal',0)", (r["id"], r["author_id"]))
            elif tem_principal["author_id"] != r["author_id"]:
                # já havia outro principal: o autor legado vira coautor, sem perder o vínculo
                c.execute("INSERT OR IGNORE INTO work_agents(work_id,author_id,papel,ordem) "
                          "VALUES(?,?,'coautor',1)", (r["id"], r["author_id"]))
        c.execute("DROP INDEX IF EXISTS i_works_a")
        if _remover_coluna(c, "works", "author_id"):
            AVISOS.append("v14: works.author_id convertido em work_agents e removido")

    if "tradutor" in _colunas(c, "manifestations") or "organizador" in _colunas(c, "manifestations"):
        cols = [x for x in ("tradutor", "organizador") if x in _colunas(c, "manifestations")]
        idx = {}
        for a in c.execute("SELECT id,nome FROM authors").fetchall():
            idx.setdefault(normalizar(a["nome"]), []).append(a["id"])
        for m in c.execute(f"SELECT id,work_id,{','.join(cols)} FROM manifestations").fetchall():
            for campo in ("tradutor", "organizador"):
                if campo not in cols:
                    continue
                valor = (m[campo] or "").strip()
                if not valor:
                    continue
                candidatos = idx.get(normalizar(valor), [])
                if len(candidatos) == 1:
                    c.execute("INSERT OR IGNORE INTO manifestation_agents(manifestation_id,author_id,papel) "
                              "VALUES(?,?,?)", (m["id"], candidatos[0], campo))
                else:
                    # sem autor inequívoco: preserva o texto como evidência em revisão,
                    # em vez de inventar uma ficha de autor ou descartar a informação
                    c.execute("""INSERT INTO evidences(entidade_tipo,entidade_id,afirmacao,trecho,notas,
                                                        estado,motivo_revisao)
                                 VALUES('manifestation',?,?,?,?,'revisao_necessaria',?)""",
                              (m["id"],
                               f"Crédito de {campo} declarado na edição, sem autor identificado no catálogo",
                               valor,
                               f"Reconciliação automática da v14 (manifestação {m['id']})",
                               "Texto legado preservado: identifique o autor e converta em crédito estruturado."))
        if _remover_coluna(c, "manifestations", "tradutor"):
            AVISOS.append("v14: manifestations.tradutor convertido em manifestation_agents/evidência")
        _remover_coluna(c, "manifestations", "organizador")


def _criar_indices_unicos(c):
    """Índices de identidade de fascículo — tolerantes a bancos antigos com duplicatas.

    Antes, uma duplicata pré-existente derrubava a migração e, com ela, todas as
    requisições. Agora o índice é opcional: sem ele o sistema continua funcionando e
    o Diagnóstico mostra o aviso para o pesquisador resolver a duplicidade.
    """
    c.execute("DROP INDEX IF EXISTS i_issue_identity")
    for sql, rotulo in (
        ("""CREATE UNIQUE INDEX IF NOT EXISTS i_issue_identity_number
            ON periodical_issues(periodical_id, COALESCE(volume,''), COALESCE(numero,''), COALESCE(data,''))
            WHERE length(trim(COALESCE(volume,'')))>0 OR length(trim(COALESCE(numero,'')))>0""", "número"),
        ("""CREATE UNIQUE INDEX IF NOT EXISTS i_issue_identity_title
            ON periodical_issues(periodical_id, lower(trim(titulo)), COALESCE(data,''))
            WHERE length(trim(COALESCE(volume,'')))=0 AND length(trim(COALESCE(numero,'')))=0
              AND length(trim(COALESCE(titulo,'')))>0""", "título"),
    ):
        try:
            c.execute(sql)
        except sqlite3.IntegrityError:
            AVISOS.append(f"v14: há fascículos duplicados por {rotulo}; o índice de unicidade não foi criado "
                          f"(o acervo segue utilizável — corrija as duplicatas no Fichário)")


def _generos_base(c):
    generos = {
        "Poesia": ["Épica", "Lírica", "Satírica", "Dramática", "Visual", "Concreta"],
        "Romance": ["Policial", "Autoficção", "De formação", "Histórico", "Epistolar", "Psicológico", "Distópico", "Fantástico"],
        "Conto": ["Fantástico", "Policial", "Histórico"],
        "Teatro": ["Tragédia", "Comédia", "Drama", "Auto"],
        "Não ficção": ["Ensaio", "Crônica", "Memórias", "Biografia", "Autobiografia", "Diário", "Entrevista", "Artigo acadêmico"],
    }
    for pai, filhos in generos.items():
        row = c.execute("SELECT id FROM genre_terms WHERE lower(nome)=lower(?)", (pai,)).fetchone()
        pid = row["id"] if row else c.execute("INSERT INTO genre_terms(nome) VALUES(?)", (pai,)).lastrowid
        for filho in filhos:
            row = c.execute("SELECT id,parent_id FROM genre_terms WHERE lower(nome)=lower(?)", (filho,)).fetchone()
            if row is None:
                c.execute("INSERT INTO genre_terms(nome,parent_id) VALUES(?,?)", (filho, pid))
            elif row["parent_id"] is None:
                c.execute("UPDATE genre_terms SET parent_id=? WHERE id=?", (pid, row["id"]))


def _migrar(c):
    AVISOS.clear()
    if "periodicals" in _tabelas(c):
        _legado_periodicals(c)
    c.executescript(SCHEMA)
    c.executescript(_PERIODICALS_SQL)
    _alinhar_colunas(c)

    # campos aditivos que não dependem do número de versão
    if "estatuto" not in _colunas(c, "relations"):
        c.execute("ALTER TABLE relations ADD COLUMN estatuto TEXT NOT NULL DEFAULT 'documentada'")
    for coluna, definicao in (("alvo_tipo", "TEXT"), ("alvo_id", "TEXT"),
                              ("estado", "TEXT NOT NULL DEFAULT 'vigente'"), ("motivo_revisao", "TEXT")):
        if coluna not in _colunas(c, "evidences"):
            c.execute(f"ALTER TABLE evidences ADD COLUMN {coluna} {definicao}")
    c.execute("UPDATE evidences SET estado='vigente' WHERE estado IS NULL OR trim(estado)=''")
    c.execute("UPDATE relations SET estatuto='documentada' WHERE estatuto IS NULL OR trim(estatuto)=''")
    for sql in INDICES:
        c.execute(sql)
    _caminhos_posix(c)

    if c.execute("PRAGMA user_version").fetchone()[0] >= VERSAO:
        return

    _migrar_entity_places_papel(c)
    for r in c.execute("SELECT id,nascimento,morte FROM authors").fetchall():
        c.execute("UPDATE authors SET nasc_num=?, morte_num=? WHERE id=?",
                  (ano_num(r["nascimento"]), ano_num(r["morte"]), r["id"]))
    for r in c.execute("SELECT id,ano FROM works").fetchall():
        c.execute("UPDATE works SET ano_num=? WHERE id=?", (ano_num(r["ano"]), r["id"]))

    tabelas = _tabelas(c)
    if "author_tags" in tabelas:
        c.execute("INSERT OR IGNORE INTO entity_tags(entity_tipo,entity_id,tag_id) "
                  "SELECT 'author',author_id,tag_id FROM author_tags")
    if "author_places" in tabelas:
        c.execute("INSERT OR IGNORE INTO entity_places(entity_tipo,entity_id,place_id,ordem) "
                  "SELECT 'author',author_id,place_id,ordem FROM author_places")
    for antigo, (novo, rotulo) in LEGADO.items():
        c.execute("UPDATE relations SET tipo=?, rotulo=? WHERE tipo=?", (novo, rotulo, antigo))
    try:
        _legado_deepseek(c)
    except Exception as e:  # migração de terceiros nunca deve impedir o uso
        AVISOS.append(f"parte da migração de banco antigo foi ignorada: {e}")

    # publicação em periódico é manifestação, não aresta
    legadas = c.execute("""SELECT id,origem_id AS work_id,destino_id AS periodical_id,ano,notas,fonte
                           FROM relations WHERE tipo='publicado_em' AND origem_tipo='work'
                           AND destino_tipo='periodical'""").fetchall()
    for r in legadas:
        existe = c.execute("""SELECT 1 FROM manifestations WHERE work_id=? AND periodical_id=?
                              AND COALESCE(ano_edicao,'')=COALESCE(?,'')
                              AND COALESCE(referencia,'')=COALESCE(?,'') LIMIT 1""",
                           (r["work_id"], r["periodical_id"], r["ano"], r["notas"])).fetchone()
        if not existe:
            c.execute("""INSERT INTO manifestations(work_id,tipo_aparicao,periodical_id,ano_edicao,ed_num,
                                                    referencia,fonte,notas)
                         VALUES(?,'publicação em periódico',?,?,?,?,?,?)""",
                      (r["work_id"], r["periodical_id"], r["ano"], ano_num(r["ano"]),
                       r["notas"], r["fonte"], r["notas"]))
        c.execute("DELETE FROM relations WHERE id=?", (r["id"],))

    _sincronizar_modelo_documental(c)
    _remover_legado_v14(c)
    _criar_indices_unicos(c)
    _generos_base(c)
    c.execute("UPDATE manifestations SET tipo_aparicao='edição' "
              "WHERE tipo_aparicao IS NULL OR trim(tipo_aparicao)=''")
    c.execute(f"PRAGMA user_version = {VERSAO}")


_prontos = set()


@contextmanager
def conn():
    """Commit/rollback E fechamento (o `with` do sqlite3 sozinho não fecha a conexão)."""
    c = sqlite3.connect(config.DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    if str(config.DB) not in _prontos:
        _migrar(c)
        c.commit()
        _prontos.add(str(config.DB))
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def lista(c, sql, params=()):
    return [dict(r) for r in c.execute(sql, params)]


def um(c, sql, params=()):
    r = c.execute(sql, params).fetchone()
    return dict(r) if r else None


def js(valor, padrao=None):
    """json.loads tolerante."""
    try:
        return json.loads(valor) if valor else (padrao if padrao is not None else [])
    except (TypeError, ValueError):
        return padrao if padrao is not None else []
