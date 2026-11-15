"""Scanner (revisão antes de gravar), ingestão e módulo online."""
import re
from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
import difflib
from core import config, files, online, scanner
from core import entidades as E
from core.datas import ano_num
from core.db import conn, lista, js
from core.relacoes import adicionar
from core.texto import normalizar
from .cadastros import vincular_midia, _obter_fasciculo, AUTOR
from .comum import perfil_ativo

router = APIRouter(prefix="/api")

@router.post("/scan")
def scan(arquivo: UploadFile = File(...)):
    nome = (arquivo.filename or "arquivo").split("/")[-1]
    if not any(nome.lower().endswith(x) for x in config.FORMATOS):
        raise HTTPException(400, "formato não suportado (use PDF, DOCX, TXT ou MD)")
    tmp = files.guardar_upload(arquivo)
    with conn() as c:
        autores_db = [{"id": r["id"], "nome": r["nome"], "variantes": js(r["variantes"])} for r in c.execute("SELECT id,nome,variantes FROM authors")]
        periodicos = lista(c, "SELECT id,titulo,issn FROM periodicals")
    try: res = scanner.identificar(tmp, autores_db, nome)
    except Exception as e: res = {"erro": f"falha ao identificar: {e}"}
    if "erro" in res:
        tmp.unlink(missing_ok=True); return res
    for p in res["periodico"]:             # o periódico já existe no acervo?
        achado = next((x for x in periodicos if (p.get("issn") and x["issn"] == p["issn"]) or normalizar(x["titulo"]) == normalizar(p["valor"])), None)
        p["periodical_id"] = achado["id"] if achado else None
    res["arquivo_temporario"] = str(tmp)
    return res

@router.post("/descartar")
def descartar(dados: dict = Body(...)):
    files.tmp_valido(dados.get("arquivo_temporario", "")).unlink(missing_ok=True)
    return {"ok": True}

@router.get("/obras/parecidas")
def obras_parecidas(titulo: str, author_id: int | None = None):
    """Obra com título igual/parecido (do mesmo autor, se já escolhido) — evita duplicar."""
    alvo = normalizar(titulo)
    if len(alvo) < 3: return []
    with conn() as c:
        rows = lista(c, f"""SELECT w.id,w.titulo,w.ano,w.genero,{AUTOR} AS author_id,a.nome AS author_nome
                           FROM works w LEFT JOIN authors a ON a.id={AUTOR}""")
    out = []
    for r in rows:
        if author_id and r["author_id"] and r["author_id"] != author_id: continue
        sim = difflib.SequenceMatcher(None, alvo, normalizar(r["titulo"])).ratio()
        if sim >= 0.85: out.append({**r, "similaridade": round(sim, 2)})
    return sorted(out, key=lambda x: -x["similaridade"])[:5]

# ------------------------------------------------------------------ ingestão
def _extrair_fasciculo(referencia):
    """Extrai apenas volume/número explicitamente identificados na referência."""
    ref = str(referencia or "")
    mv = re.search(r"(?<!\w)(?:v(?:ol(?:ume)?)?|volume)\s*\.?\s*([A-Za-z0-9][A-Za-z0-9.-]*)", ref, re.I)
    mn = re.search(r"(?<!\w)(?:n\s*(?:[º°o])?|n[uú]m(?:ero)?|no\.?)\s*\.?\s*([A-Za-z0-9][A-Za-z0-9.-]*)", ref, re.I)
    return (mv.group(1).strip(".,;:") if mv else None, mn.group(1).strip(".,;:") if mn else None)

class IngestIn(BaseModel):
    arquivo_temporario: str
    titulo: str | None = None
    ano: str | None = None             # ano da OBRA (publicação original)
    genero: str | None = None
    tipo: str | None = None
    author_id: int | None = None
    autor_novo: str | None = None
    coautores: list[dict] = []         # [{"author_id": 3}] ou [{"nome": "Fulano"}]
    editora: str | None = None
    ano_edicao: str | None = None      # ano da EDIÇÃO que você tem em mãos
    idioma: str | None = None
    tradutor: str | None = None        # legado: convertido em crédito se houver autor único
    organizador: str | None = None     # idem
    local: str | None = None           # cidade da edição (folha de rosto: «RIO DE JANEIRO»)
    edicao_nota: str | None = None     # «quarta edição», série, observações
    fonte: str | None = None           # de onde veio o arquivo (ex.: Projeto Gutenberg #55752)
    periodico: dict | None = None      # {"id":1} ou {"titulo":"...","issn":"..."} + "referencia", "ano"
    midias: list[str] = []
    work_id_existente: int | None = None
    criar_mesmo_assim: bool = False    # confirma a criação quando já existe obra com o mesmo título/autor

def _autor(c, author_id=None, nome=None, pid=None):
    """(id, nome, criado). Cria a ficha se o nome não existir."""
    criado = False
    if author_id:
        r = c.execute("SELECT id,nome FROM authors WHERE id=?", (author_id,)).fetchone()
        if not r: raise HTTPException(404, "autor não encontrado")
    elif (nome or "").strip():
        nome = nome.strip()
        r = next((x for x in c.execute("SELECT id,nome FROM authors") if normalizar(x["nome"]) == normalizar(nome)), None)
        if not r:
            cur = c.execute("INSERT INTO authors(nome) VALUES(?)", (nome,)); r = {"id": cur.lastrowid, "nome": nome}; criado = True
    else: return None, None, False
    E.anexar_perfil(c, pid, "author", r["id"])
    return r["id"], r["nome"], criado

@router.post("/ingest")
def ingerir(p: IngestIn, request: Request):
    origem = files.tmp_valido(p.arquivo_temporario)
    pid = perfil_ativo(request)
    ed = {k: ((getattr(p, k) or "").strip() or None)
          for k in ("editora", "ano_edicao", "idioma", "local", "edicao_nota", "fonte")}
    promocoes = []

    with conn() as c:
        def resolver_periodico():
            pj = p.periodico
            if not pj: return None
            if pj.get("periodical_id") or pj.get("id"):
                pid_per = int(pj.get("periodical_id") or pj.get("id"))
                E.exigir(c, "periodical", pid_per)
                return pid_per
            titulo_per = (pj.get("titulo") or pj.get("valor") or "").strip()
            if not titulo_per: return None
            issn = (pj.get("issn") or "").strip() or None
            existente = next((x for x in c.execute("SELECT id,titulo,issn FROM periodicals")
                              if (issn and x["issn"] == issn) or normalizar(x["titulo"]) == normalizar(titulo_per)), None)
            if existente: return existente["id"]
            return c.execute("INSERT INTO periodicals(titulo,tipo,issn) VALUES(?,?,?)",
                             (titulo_per, "periódico acadêmico" if issn else None, issn)).lastrowid

        def creditos_legados(mid):
            """Converte texto livre de tradutor/organizador em crédito quando o autor é inequívoco.

            Sem correspondência única, o texto não é descartado: vira evidência em revisão na
            própria manifestação, para que o pesquisador identifique a pessoa depois.
            """
            for campo in ("tradutor", "organizador"):
                texto = (getattr(p, campo) or "").strip()
                if not texto: continue
                ids = [r["id"] for r in c.execute("SELECT id,nome FROM authors")
                       if normalizar(r["nome"]) == normalizar(texto)]
                if len(ids) == 1:
                    c.execute("INSERT OR IGNORE INTO manifestation_agents(manifestation_id,author_id,papel) "
                              "VALUES(?,?,?)", (mid, ids[0], campo))
                else:
                    c.execute("""INSERT INTO evidences(entidade_tipo,entidade_id,afirmacao,trecho,notas,
                                 estado,motivo_revisao)
                                 VALUES('manifestation',?,?,?,?,'revisao_necessaria',?)""",
                              (mid, f"Crédito de {campo} informado na importação, sem autor identificado no catálogo",
                               texto, "Texto informado no scanner; converta em crédito estruturado na ficha da edição.",
                               "Identifique a pessoa e registre o papel em «Créditos desta edição»."))

        def gravar_edicao(wid, autor_nome, titulo, periodical_id=None):
            caminho = files.estacionar(origem) if origem.is_file() else ""
            pj = p.periodico or {}
            tipo_aparicao = "publicação em periódico" if periodical_id else "edição"
            referencia = (pj.get("referencia") or "").strip() or None if periodical_id else None
            ano_manifestacao = (pj.get("ano") or ed["ano_edicao"]) if periodical_id else ed["ano_edicao"]
            issue_id = None
            if periodical_id and referencia:
                volume, numero = _extrair_fasciculo(referencia)
                if volume or numero:
                    issue_id = _obter_fasciculo(c, periodical_id, volume, numero, ano_manifestacao,
                                                titulo=None, referencia=referencia, notas=ed["edicao_nota"])
            mid = c.execute("""INSERT INTO manifestations(work_id,caminho,formato,editora,ano_edicao,ed_num,
                                idioma,local,notas,fonte,paginas,tipo_aparicao,periodical_id,referencia,issue_id)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (wid, caminho, __import__("pathlib").Path(caminho).suffix.lstrip(".") if caminho else None,
                             ed["editora"], ano_manifestacao, ano_num(ano_manifestacao), ed["idioma"], ed["local"],
                             ed["edicao_nota"], ed["fonte"],
                             files.paginas(config.DATA / caminho) if caminho else None,
                             tipo_aparicao, periodical_id, referencia, issue_id)).lastrowid
            creditos_legados(mid)
            promocoes.append((mid, caminho, autor_nome, titulo))
            return mid

        periodical_id = resolver_periodico()
        if p.work_id_existente:
            w = c.execute(f"""SELECT w.id,w.titulo,{AUTOR} AS author_id,a.nome AS author_nome FROM works w
                              LEFT JOIN authors a ON a.id={AUTOR} WHERE w.id=?""", (p.work_id_existente,)).fetchone()
            if not w: raise HTTPException(404, "obra não encontrada")
            gravar_edicao(w["id"], w["author_nome"], w["titulo"], periodical_id)
            E.anexar_perfil(c, pid, "work", w["id"])
            if periodical_id: E.anexar_perfil(c, pid, "periodical", periodical_id)
            resposta = {"work_id": w["id"], "anexado": True, "author_id": w["author_id"],
                        "author_nome": w["author_nome"], "periodical_id": periodical_id}
        else:
            aid, anome, criado = _autor(c, p.author_id, p.autor_novo, pid)
            titulo = (p.titulo or "").strip() or re.sub(r"\.[^.]+$", "", files.nome_original(origem))
            ano = (p.ano or "").strip() or None
            # deduplicação no servidor: mesma obra + mesmo autor pede confirmação explícita
            if not p.criar_mesmo_assim:
                alvo = normalizar(titulo)
                for r in c.execute(f"SELECT w.id,w.titulo,{AUTOR} AS autor FROM works w WHERE {AUTOR} IS ?", (aid,)):
                    if normalizar(r["titulo"]) == alvo:
                        raise HTTPException(409, f"Já existe «{r['titulo']}» (#{r['id']}) com este autor. "
                                                 "Abra a ficha e anexe como nova edição, ou reenvie confirmando "
                                                 "que se trata de outra obra.")
            wid = c.execute("INSERT INTO works(titulo,ano,ano_num,genero,tipo) VALUES(?,?,?,?,?)",
                            (titulo, ano, ano_num(ano),
                             p.genero if p.genero in config.GENEROS else None,
                             (p.tipo or "").strip() or None)).lastrowid
            if aid is not None:
                E.definir_autor_principal(c, wid, aid)
            E.anexar_perfil(c, pid, "work", wid)
            n_rel = 0
            for m in p.midias:
                if (m or "").strip(): vincular_midia(c, wid, m, pid)
            for co in p.coautores:
                cid, _, _ = _autor(c, co.get("author_id"), co.get("nome"), pid)
                if cid and cid != aid:
                    _, dup = adicionar(c, {"origem_tipo": "author", "origem_id": cid,
                                           "destino_tipo": "work", "destino_id": wid,
                                           "tipo": "autor_de"}, pid)
                    n_rel += 0 if dup else 1
            gravar_edicao(wid, anome, titulo, periodical_id)
            if periodical_id: E.anexar_perfil(c, pid, "periodical", periodical_id)
            resposta = {"work_id": wid, "author_id": aid, "author_nome": anome, "autor_criado": criado,
                        "periodical_id": periodical_id, "participacoes_criadas": n_rel,
                        "relacoes_criadas": n_rel}

    # Depois do commit: promove cada arquivo da área de entrada para a estante.
    # Se a promoção falhar, o registro continua apontando para o arquivo estacionado.
    for mid, caminho, autor, titulo in promocoes:
        if not caminho: continue
        final = files.promover(caminho, autor, titulo)
        if final != caminho:
            with conn() as c:
                c.execute("UPDATE manifestations SET caminho=? WHERE id=?", (final, mid))
    return resposta

# ------------------------------------------------------------------ online (opcional)
@router.get("/config")
def ler_config(): return {"online": online.ativo()}

@router.post("/config")
def gravar_config(dados: dict = Body(...)):
    if "online" in dados: online.definir_ativo(bool(dados["online"]))
    return {"online": online.ativo()}

def _exigir_online():
    if not online.ativo():
        raise HTTPException(403, "o módulo online está desligado (ative em Diagnóstico ou no botão da tela de revisão)")

@router.post("/online/obra")
def online_obra(dados: dict = Body(...)):
    _exigir_online()
    try: return online.obra(dados.get("titulo"), dados.get("autor"), dados.get("doi"))
    except online.OnlineErro as e: raise HTTPException(502, str(e))

@router.post("/online/autor")
def online_autor(dados: dict = Body(...)):
    _exigir_online()
    if not (dados.get("nome") or "").strip(): raise HTTPException(400, "informe o nome")
    try: return online.autor(dados["nome"].strip())
    except online.OnlineErro as e: raise HTTPException(502, str(e))
