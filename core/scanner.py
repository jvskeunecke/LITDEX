"""Scanner: lê só o COMEÇO de um arquivo (é lá que ficam título, autor, edição) e propõe
candidatos para cada campo — sempre com a evidência de onde saíram. Nada é gravado aqui:
quem decide é o usuário, na tela de revisão.

Cada campo devolve [{"valor", "origens": [...]}], do mais provável ao menos."""
import re, statistics
from pathlib import Path
from .texto import normalizar, limpar, slug

# ------------------------------------------------------------------ leitura
def extrair_texto(caminho, max_pag=10, lim=30000):
    """Levanta ValueError se não conseguir ler."""
    caminho = Path(caminho); suf = caminho.suffix.lower()
    try:
        if suf == ".pdf":
            from pypdf import PdfReader
            r = PdfReader(str(caminho))
            return "\n".join((p.extract_text() or "") for p in r.pages[:max_pag])[:lim]
        if suf == ".docx":
            import docx
            return "\n".join(p.text for p in docx.Document(str(caminho)).paragraphs)[:lim]
        if suf in (".txt", ".md"):
            b = caminho.read_bytes()
            try: return b.decode("utf-8")[:lim]
            except UnicodeDecodeError: return b.decode("cp1252", errors="replace")[:lim]
    except Exception as e:
        raise ValueError(f"não consegui ler o arquivo ({e})")
    raise ValueError("formato não suportado (use PDF, DOCX, TXT ou MD)")

def metadados_arquivo(caminho):
    """Título/autor gravados dentro do PDF ou DOCX, descartando o lixo típico."""
    caminho = Path(caminho); m = {}
    try:
        if caminho.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            i = PdfReader(str(caminho)).metadata or {}
            m = {"titulo": i.get("/Title"), "autor": i.get("/Author")}
        elif caminho.suffix.lower() == ".docx":
            import docx
            p = docx.Document(str(caminho)).core_properties
            m = {"titulo": p.title, "autor": p.author}
    except Exception:
        return {}
    lixo = re.compile(r"microsoft|\bword\b|admin|\buser\b|unknown|untitled|\.docx?|\.pdf|scanner|adobe|"
                      r"libreoffice|python-docx|reportlab|pdftex|latex|calibre", re.I)
    return {k: v.strip() for k, v in m.items() if isinstance(v, str) and len(v.strip()) > 2 and not lixo.search(v)}

# ------------------------------------------------------------------ padrões
_PART  = r"[A-ZÀ-Ý][\wÀ-ÿ'’.\-]+"
_NOME  = rf"{_PART}(?:\s+(?:(?:d[aeo]s?|e|van|von|di)\s+)?{_PART}){{1,4}}"
_NOME2 = rf"{_PART}(?:\s+(?:(?:d[aeo]s?|van|von|di)\s+)?{_PART}){{1,4}}"     # sem o conector "e"
_MARCA = "*†‡§¹²³⁴⁵⁶⁷⁸⁹⁰"

_RE_BYLINE = re.compile(rf"^(?i:por|by|autor|autora|escrito por)\s*:?\s+({_NOME})\s*$")
_RE_ASSINATURA = re.compile(rf"^[—–-]{{1,2}}\s*({_NOME})\s*$")
_RE_INST = re.compile(r"^(?:da |do |de |academia|livraria|ty?pograph|tipograf|imprensa|companhia|livreiro|bibliotheca|biblioteca|s[eé]rie|edi[cç][aã]o|"
                      r"revista|jornal|journal|editora|universidade|university|instituto|departamento|programa|"
                      r"cadernos?|anais|faculdade|centro|grupo|laborat[oó]rio|escola|secretaria|minist[eé]rio|"
                      r"biblioteca|sociedade|associa[cç][aã]o|copyright|creative|professor[a]?)\b", re.I)
_RE_RUIDO = re.compile(
    r"^(?:©.*|copyright.*|isbn.*|issn.*|doi.*|https?://.*|www\..*|\S+@\S+|todos os direitos.*|todo o conte[uú]do.*|"
    r"editora\b.*|sum[aá]rio|[ií]ndice|resumo|abstract|palavras[- ]chave.*|keywords.*|recebido.*|aprovado.*|"
    r"cap[ií]tulo\s+\S+.*|\d+\s*[ªa]?\s*edi[cç][aã]o.*|p[aá]gina\s+\d+.*|produced by.*|e-text prepared.*|(?:the )?project gutenberg.*|"
    r"release date.*|language\s*:.*|title\s*:.*|author\s*:.*|this e-?book is for.*|\*\*\*.*)$", re.I)
_RE_EDICAO = re.compile(r"©|copyright|direitos|edi[cç][aã]o|impress|isbn|editora|ltda|reimpress|tiragem|printed|published by|release date|gutenberg|e-?book|livreiro", re.I)
_RE_ANO = re.compile(r"\b(1[4-9]\d{2}|20[0-2]\d)\b")
_RE_FIM_CORPO = re.compile(r"^(?:refer[eê]ncias(?: bibliogr[aá]ficas)?|bibliografia|references|obras citadas)\s*$", re.I)
_RE_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)")
_RE_ISSN = re.compile(r"\bISSN[:\s]*(\d{4}-\d{3}[\dXx])\b")
_RE_REVISTA = re.compile(
    r"((?:Revista|Rev\.|Journal|Cadernos?|Boletim|Anais|Jornal|Almanaque)\s[^,.;|\n]{2,70}?)\s*,\s*v\.\s*(\d+)"
    r"(?:\s*,\s*n\.\s*(\d+))?(?:\s*,\s*p\.\s*([\d\-–]+))?(?:\s*,\s*(?:[a-zç]{3,9}\.?\s*)?((?:1[4-9]|20)\d{2}))?", re.I)
_RE_REVISTA_PIPE = re.compile(r"\|\s*((?:Revista|Journal|Cadernos?|Boletim)[^|\n]{2,70})$", re.I)
_RE_TRAD = re.compile(r"(?i:tradu[cç][aã]o(?:\s+e\s+notas)?|traduzid[oa]|trad\.|translated|traductor|tradutor(?:a)?)"
                      r"\s*(?:de|por|by)?\s*:?\s+(.+)$")
_RE_ORG = re.compile(r"(?i:organiza[cç][aã]o|organizad[oa]\s+por|org\.|organizador(?:a)?|edited\s+by|"
                     r"sele[cç][aã]o(?:\s+e\s+organiza[cç][aã]o)?)\s*(?:de|por|by)?\s*:?\s+(.+)$")
_RE_EDITORA = re.compile(r"^(?i:(editora|edi[cç][oõ]es|ed\.|livraria|imprensa|publisher|published by|publicado por|press))"
                         r"\s*:?\s*([A-ZÀ-Ý0-9][^\n,;]{0,50})$")
_RE_PALAVRA_EDITORA = re.compile(r"editora|edi[cç][oõ]es|press|publishers?|livros|books|companhia|cia\.|ltda|s\.a\.|verlag|[eé]ditions|edizioni|editorial", re.I)
_RE_ORIGINAL = re.compile(r"(?i:publicad[oa]\s+originalmente\s+em|originalmente\s+publicad[oa]\s+em|originally\s+published\s+in|t[ií]tulo\s+original[^\n]*?\()\s*((?:1[4-9]|20)\d{2})")

_RE_PG_CAMPO = re.compile(r"^(Title|Author|Translator|Editor|Illustrator|Release Date|Language|Produced by|Credits)\s*:\s*(.*)$", re.I)
_RE_PG_EBOOK = re.compile(r"\[e-?book\s*#\s*(\d+)\]", re.I)
_RE_PG_CREDITO = re.compile(r"^(?:produced by|e-text prepared by|this e-?book was produced|transcriber)", re.I)
_RE_EDICAO_ROTULO = re.compile(r"^(?:(primeira|segunda|terceira|quarta|quinta|sexta|s[eé]tima|oitava|nona|d[eé]cima|\d+\s*[ªa]?)\s+edi[cç][aã]o)$", re.I)
_RE_EDITORA_LINHA = re.compile(r"(?:livreiro[- ]editor|\bed[iy]tora\b|\bty?pograph?ia\b|\btipografia\b|\bimprensa\b|\blivraria\b|\bcompanhia\b|\bedi[cç][oõ]es\b)", re.I)
_RE_DATA_REDACAO = re.compile(r"^[A-ZÀ-Ý][\wÀ-ÿ ]{2,30},\s+(?:\d{1,2}\s+de\s+)?[a-zç]+\s+de\s+((?:1[4-9]|20)\d{2})\.?\s*$")
_RE_ABNT = re.compile(r"^(?:Fonte|Refer[eê]ncia)\s*:\s*([A-ZÀ-Ý][A-ZÀ-Ý' ]+),\s*(.+?)\.\s+(.+)$")
# cidades de edição (a lista cresce com o uso: o que o usuário cadastra como lugar também vale)
_CIDADES = {"pariz": "Paris", **{normalizar(c): c for c in ("Lisboa", "Porto", "Coimbra", "Rio de Janeiro", "São Paulo", "Belo Horizonte", "Salvador", "Recife", "Porto Alegre",
            "Curitiba", "Brasília", "Fortaleza", "São Luís", "Paris", "Londres", "Madrid", "Madri", "Barcelona", "Roma", "Milão", "Berlim",
            "Nova York", "Buenos Aires", "Lima", "Santiago", "Bruxelas", "Lausanne", "Leipzig")}}

def _sem_marca(s): return re.sub(rf"[{re.escape(_MARCA)}]+$", "", s).strip()
def _trecho(i, l): return f"linha {i+1}: «{limpar(l)[:60]}»"

def _e_ruido(l):
    l = limpar(l)
    return (len(l) < 3 or bool(re.fullmatch(r"\d+|[IVXLCDM]{1,7}[.)]?", l))
            or bool(_RE_RUIDO.match(l)) or bool(_RE_BYLINE.match(l)))

def _juntar(lista, valor, origem, **extra):
    for c in lista:
        if normalizar(c["valor"]) == normalizar(valor):
            if origem not in c["origens"]: c["origens"].append(origem)
            for k, v in extra.items(): c.setdefault(k, v)
            return
    lista.append({"valor": valor, "origens": [origem], **extra})

def _como_nome(nome):
    nome = _sem_marca(limpar(nome)).strip(" .;")
    if nome.count(",") == 1:                      # "Pessoa, Fernando" -> "Fernando Pessoa"
        a, b = nome.split(","); nome = f"{b.strip()} {a.strip()}"
    if nome.isupper():                            # "MACHADO DE ASSIS" -> "Machado de Assis"
        nome = re.sub(r"\b(De|Da|Do|Das|Dos|E)\b", lambda m: m.group(1).lower(), nome.title())
    return nome

def dedup_linha(l):
    """Slides costumam desenhar o texto duas vezes (sombra): 'Título Título' -> 'Título'."""
    s = limpar(l); n = len(s)
    if n < 8: return l
    for h in {n // 2, (n - 1) // 2}:
        a, b = s[:h].strip(), s[h:].strip()
        if a and a == b: return a
    return l

def corpo(linhas):
    """Linhas até a lista de referências (depois dela, tudo é citação de OUTRAS obras)."""
    for i, l in enumerate(linhas):
        if i > 5 and _RE_FIM_CORPO.match(limpar(l)): return linhas[:i]
    return linhas

# ------------------------------------------------------------------ formatos reais de arquivos de domínio público
def cabecalho_gutenberg(linhas):
    """Cabeçalho do Projeto Gutenberg ('Title:', 'Author:', 'Release Date:'…). {} se não for um."""
    texto = "\n".join(linhas[:60])
    if "gutenberg" not in texto.lower(): return {}
    out, i = {}, 0
    while i < min(len(linhas), 50):
        m = _RE_PG_CAMPO.match(linhas[i].strip())
        if m:
            chave, valor = m.group(1).lower(), m.group(2).strip()
            while i + 1 < len(linhas) and linhas[i + 1][:1] in (" ", "\t") and linhas[i + 1].strip():
                i += 1; valor += " | " + linhas[i].strip()
            out.setdefault(chave, valor)
        i += 1
    n = _RE_PG_EBOOK.search(texto)
    if n: out["numero"] = n.group(1)
    return out if ("title" in out or "author" in out) else {}

def depois_do_cabecalho(linhas):
    """Corpo depois da licença do Gutenberg (e do parágrafo de créditos 'Produced by…'). PDFs não têm linhas em
    branco entre parágrafos e quebram a linha '*** START … ***' em duas: trata os dois casos."""
    for i, l in enumerate(linhas[:140]):
        if not l.strip().startswith("*** START"): continue
        j = i + 1
        if not l.rstrip().endswith("***"):
            while j < len(linhas) and j < i + 4 and not linhas[j].rstrip().endswith("***"): j += 1
            j += 1
        resto = linhas[j:]
        while resto and not resto[0].strip(): resto = resto[1:]
        if resto and _RE_PG_CREDITO.match(resto[0].strip()):
            k = 0
            while k < min(len(resto), 14) and resto[k].strip() and not (resto[k].strip().isupper() and len(resto[k].strip()) >= 4): k += 1
            resto = resto[k:]
        return resto
    return linhas

def _blocos(linhas, limite=90):
    """Folha de rosto: blocos de linhas separados por linha em branco."""
    blocos, atual = [], []
    for l in linhas[:limite]:
        if l.strip(): atual.append(limpar(l))
        elif atual: blocos.append(" ".join(atual)); atual = []
    if atual: blocos.append(" ".join(atual))
    return blocos

def _nome_proprio_caps(s):
    s = limpar(s)
    return bool(re.fullmatch(_NOME, s.title() if s.isupper() else s)) and not _RE_INST.match(s)

def folha_de_rosto(linhas, pg_titulo=None):
    """Lê a folha de rosto de edições antigas: «DOM CASMURRO / POR / MACHADO DE ASSIS / H. GARNIER, LIVREIRO-EDITOR /
    RIO DE JANEIRO / 1890». Devolve candidatos por campo, com a evidência."""
    out = {k: [] for k in ("autor", "titulo", "editora", "local", "ano_edicao", "edicao_nota")}
    blocos = [limpar(l) for l in linhas if l.strip()][:45]; alvo_titulo = normalizar(re.split(r"\s{2,}|:", pg_titulo)[0]) if pg_titulo else None
    for i, b in enumerate(blocos):
        r = f"folha de rosto: «{b[:50]}»"
        if re.fullmatch(r"(?i)por|by|par", b) and i + 1 < len(blocos) and _nome_proprio_caps(blocos[i + 1]):
            _juntar(out["autor"], _como_nome(blocos[i + 1]), f"folha de rosto: «POR» + «{blocos[i + 1][:40]}»")
            if i > 0 and blocos[i - 1].isupper() and len(blocos[i - 1]) <= 60 and not _RE_EDITORA_LINHA.search(blocos[i - 1]):
                _juntar(out["titulo"], blocos[i - 1].title(), f"folha de rosto: «{blocos[i - 1][:40]}»")
        elif re.fullmatch(r"(?:1[4-9]|20)\d{2}", b): _juntar(out["ano_edicao"], b, "ano isolado na folha de rosto")
        elif _RE_EDICAO_ROTULO.match(b): _juntar(out["edicao_nota"], b.lower(), r)
        elif normalizar(b) in _CIDADES: _juntar(out["local"], _CIDADES[normalizar(b)], r)
        elif _RE_EDITORA_LINHA.search(b) and len(b) <= 70 and b.isupper() or (_RE_EDITORA_LINHA.search(b) and len(b) <= 40):
            nome = re.sub(r"(?i),?\s*livreiro[- ]editor", "", b).strip(" ,.")
            _juntar(out["editora"], nome.title() if nome.isupper() else nome, r)
        elif alvo_titulo and b.isupper() and normalizar(b) == alvo_titulo: _juntar(out["titulo"], b.title(), r)
        elif b.isupper() and _nome_proprio_caps(b) and not out["autor"] and i <= 2 and alvo_titulo:
            _juntar(out["autor"], _como_nome(b), r)                     # «ALUIZIO AZEVEDO» antes do título
    return out

def referencia_abnt(linhas):
    """«Fonte: ALENCAR, José de. Iracema. 24. ed., São Paulo: Ática, 1991.» (edições BVE/MEC)"""
    for i, l in enumerate(linhas[:60]):
        m = _RE_ABNT.match(limpar(l))
        if not m: continue
        sobrenome, prenome, resto = m.group(1), m.group(2), m.group(3)
        titulo, _, resto2 = resto.partition(". ")
        mm = re.match(r"(?:(\d+)\.?\s*ed\.?,?\s*)?([^:,]+):\s*([^,]+),\s*((?:1[4-9]|20)\d{2})", resto2.strip())
        if not mm: continue
        return {"autor": f"{prenome} {sobrenome.title()}", "titulo": titulo.strip(), "edicao": mm.group(1), "local": mm.group(2).strip(),
                "editora": mm.group(3).strip(), "ano_edicao": mm.group(4), "origem": f"linha {i + 1}: «{limpar(l)[:60]}»"}
    return None

# ------------------------------------------------------------------ título
def _eh_titulo(ls):
    ls = ls.strip(" /–-")
    return not (_e_ruido(ls) or not 3 <= len(ls) <= 90 or ls[-1] in ".,;" or len(ls.split()) > 14)

def _linha_de_titulo(linhas, excluir=()):
    """(índice, título). Título quebrado em várias linhas (a seguinte começa em minúscula) é reunido."""
    for i, l in enumerate(linhas[:25]):
        ls = limpar(l).strip(" /–-")
        if not (_eh_titulo(ls) and normalizar(ls) not in excluir): continue
        j = i + 1
        while j < min(i + 4, len(linhas)) and ls[-1] not in ".!?":
            prox = limpar(linhas[j])
            if prox and prox[0].islower() and len(prox) <= 60 and not _e_ruido(prox):
                ls = f"{ls} {prox.strip(' /–-')}"; j += 1
            else: break
        return i, ls
    return None, None

# ------------------------------------------------------------------ autor
def candidatos_autor(linhas, nome_arquivo, meta, formas, extras=()):
    """`formas` = {grafia -> nome da ficha}: só as fichas que o usuário já criou
    (nome e 'também aparece como'). O índice cresce com o uso; nada vem pronto."""
    achados = {}                                  # nome -> {fonte: origem}
    def add(nome, fonte, origem):
        n = normalizar(nome)
        canon = next((c for f, c in formas.items() if normalizar(f) == n), nome)
        achados.setdefault(canon, {}).setdefault(fonte, origem)
    for nome_x, fonte_x, origem_x in extras: add(nome_x, fonte_x, origem_x)
    if meta.get("autor"):                          # metadado é muitas vezes lixo: só vale se o texto confirma
        nm = _como_nome(meta["autor"]); nmn = normalizar(nm)
        confirmado = any(nmn in normalizar(l) for l in linhas[:80])
        add(nm, 0 if confirmado else 6, "metadados do arquivo" + ("" if confirmado else " (não aparece no texto)"))
    for i, l in enumerate(linhas[:20]):           # "por Fulano de Tal"
        m = _RE_BYLINE.match(limpar(l))
        if m: add(_como_nome(m.group(1)), 1, _trecho(i, l))
    if len([l for l in linhas if l.strip()]) <= 60:   # "— Fulano de Tal": só em textos curtos
        for i, l in enumerate(linhas):
            m = _RE_ASSINATURA.match(limpar(l))
            if m: add(_como_nome(m.group(1)), 2, _trecho(i, l))
    titulo_i, _ = _linha_de_titulo(linhas)        # linhas que só têm um nome, perto do topo
    forte = any(f <= 1 for v in achados.values() for f in v)
    for i, l in enumerate(linhas[:0 if forte else 45]):
        ls = _sem_marca(limpar(l))
        if re.fullmatch(_NOME, ls) and not _e_ruido(ls) and not _RE_INST.match(ls) and normalizar(ls) not in _CIDADES:
            if i >= 14:      # longe do topo, só vale se vier seguido de um parágrafo (filiação, bio)
                prox = next((limpar(x) for x in linhas[i + 1:i + 4] if limpar(x)), "")
                if len(prox) < 60 or prox[0] in "•-–*": continue
            add(_como_nome(ls), 5 if i == titulo_i else 3, _trecho(i, l))   # 5 = provavelmente é o título
    topo = linhas[:60]; topo_n = [normalizar(l) for l in topo]
    stem = f"-{slug(Path(nome_arquivo).stem)}-"
    for forma, canon in formas.items():           # fichas existentes
        for i, l in enumerate(topo):
            if _contem(forma, l, topo_n[i]): add(canon, 3, _trecho(i, l)); break
        if f"-{slug(forma)}-" in stem: add(canon, 4, "nome do arquivo")
    partes = re.split(r"\s+[-–—]\s+|\s*_-_\s*", Path(nome_arquivo).stem)   # "Autor - Título.pdf"
    if len(partes) > 1 and re.fullmatch(_NOME, partes[0].strip()):
        add(_como_nome(partes[0]), 4, "nome do arquivo")
    if any(min(v) < 5 for v in achados.values()):   # palpites fracos (5-6) só valem se não há outro
        fortes = {n: v for n, v in achados.items() if min(v) < 5}
        achados = {**fortes, **{n: v for n, v in achados.items() if n not in fortes and min(v) == 6}}
    ordem = sorted(achados.items(), key=lambda kv: (-len(kv[1]), min(kv[1])))
    def origens(f):
        vistas = []
        for _, o in sorted(f.items()):
            if o not in vistas: vistas.append(o)
        return vistas[:3]
    return [{"valor": n, "origens": origens(f)} for n, f in ordem[:6]]

def _contem(forma, linha, linha_norm):
    """Nome composto: sem acento. Nome de uma palavra (Camões, Poe): maiúscula e grafia exata."""
    if " " in forma.strip():
        return re.search(rf"\b{re.escape(normalizar(forma))}\b", linha_norm) is not None
    return re.search(rf"\b(?:{re.escape(forma)}|{re.escape(forma.upper())})\b", linha) is not None

# ------------------------------------------------------------------ título e anos
def candidatos_titulo(linhas, nome_arquivo, meta, nomes_autores):
    c, aut = [], {normalizar(n) for n in nomes_autores}
    if meta.get("titulo"): _juntar(c, meta["titulo"].strip(), "metadados do arquivo")
    i, ls = _linha_de_titulo(linhas, aut)
    if ls:
        _juntar(c, ls.title() if ls.isupper() else ls, f"linha {i+1} do texto")
        if limpar(linhas[i]).endswith("/") and i + 1 < len(linhas):     # "Título / Title" (bilíngue)
            alt = limpar(linhas[i + 1])
            if _eh_titulo(alt): _juntar(c, alt, f"linha {i+2}: título em outra língua")
    stem = Path(nome_arquivo).stem
    if " " not in stem: stem = re.sub(r"[-_]+", " ", stem)
    partes = [re.sub(r"_+", " ", p) for p in re.split(r"\s+[-–—]\s+|\s*_-_\s*", stem)]
    partes = [re.sub(r"\b(?:1[4-9]|20)\d{2}\b", "", p).strip(" -_.()") for p in partes]
    partes = [p for p in partes if len(p) >= 3 and normalizar(p) not in aut]
    if partes:
        p = max(partes, key=len)
        _juntar(c, p.title() if p.islower() else p, "nome do arquivo")
    for x in c: x["valor"] = x["valor"].strip(" .;:—-·•/")
    return [x for x in c if len(x["valor"]) >= 3][:4]

def _sem_codigos(l):
    l = re.sub(r"(?i)\b(?:issn|isbn)[:\s]*[\dXx-]+", " ", l)
    l = re.sub(r"10\.\d{4,9}/\S+", " ", l)
    return re.sub(r"https?://\S+|www\.\S+", " ", l)

def candidatos_anos(linhas, nome_arquivo, rosto=None, abnt=None, pg=None):
    """(ano da OBRA, ano da EDIÇÃO). Ficha técnica (©, 'edição', ano isolado na folha de rosto) = ano da edição que
    você tem em mãos; o da obra é o da publicação original. A data do e-book (Gutenberg) é só a da edição digital."""
    obra, edicao = [], []
    for i, l in enumerate(linhas[:300]):
        m = _RE_ORIGINAL.search(_sem_codigos(l))
        if m: _juntar(obra, m.group(1), _trecho(i, l) + " — publicação original")
    for i, l in enumerate(linhas[:400]):
        m = _RE_DATA_REDACAO.match(limpar(l))
        if m: _juntar(obra, m.group(1), _trecho(i, l) + " — data de redação (prólogo/carta)")
    for a in _RE_ANO.findall(Path(nome_arquivo).stem): _juntar(obra, a, "nome do arquivo")
    if rosto:
        for c in rosto["ano_edicao"]: _juntar(edicao, c["valor"], c["origens"][0])
    if abnt: _juntar(edicao, abnt["ano_edicao"], abnt["origem"])
    ja_edicao = {c["valor"] for c in edicao}
    for i, l in enumerate(linhas[:60]):
        if len(l) > 80 or len(l.split()) > 6: continue  # datas em texto corrido (biografia, prosa) não valem
        alvo = edicao if _RE_EDICAO.search(l) else obra
        for a in _RE_ANO.findall(_sem_codigos(l)):
            if alvo is obra and a in ja_edicao: continue   # o mesmo ano já é o da edição (folha de rosto / Fonte:)
            _juntar(alvo, a, _trecho(i, l) + (" — ficha técnica, pode ser o ano da edição" if alvo is edicao else ""))
    if pg and pg.get("release date"):
        m = _RE_ANO.search(pg["release date"])
        if m: _juntar(edicao, m.group(1), "edição digital (Projeto Gutenberg" + (f" #{pg['numero']}" if pg.get("numero") else "") + ")")
    return obra[:3], edicao[:3]

# ------------------------------------------------------------------ edição: editora, tradutor, organizador
def _creditos(linhas, rx):
    out = []
    for i, l in enumerate(linhas[:150]):
        m = rx.search(limpar(l))
        if not m: continue
        partes = [_sem_marca(p.strip(" .;:")) for p in re.split(r"\s+e\s+|\s*&\s*|\s*;\s*|\s*,\s*", m.group(1)) if p.strip()]
        ok = [_como_nome(p) for p in partes if re.fullmatch(_NOME2, p)]
        if ok:
            valor = ok[0] if len(ok) == 1 else ", ".join(ok[:-1]) + " e " + ok[-1]
            _juntar(out, valor, _trecho(i, l))
    return out[:3]

def candidatos_editora(linhas):
    out = []
    for i, l in enumerate(linhas[:150]):
        ls = limpar(l)
        m = _RE_EDITORA.match(ls)
        if m:
            chave, nome = m.group(1).lower(), m.group(2).strip(" .")
            valor = nome if chave in ("editora", "ed.", "publisher", "published by", "publicado por") else f"{m.group(1).capitalize()} {nome}"
            _juntar(out, valor, _trecho(i, l)); continue
        m = re.search(r"©\s*(?:1[4-9]|20)\d{2}\s+(?:by\s+)?([A-ZÀ-Ý][^\n.;]{2,50})", ls)
        if m and _RE_PALAVRA_EDITORA.search(m.group(1)):
            nome = re.sub(r"^(?i:editora)\s+", "", m.group(1)).strip(" .")
            _juntar(out, nome, _trecho(i, l) + " — titular do © (pode não ser a editora)")
    return out[:3]

# ------------------------------------------------------------------ periódico, DOI, idioma, gênero
def candidatos_periodico(linhas):
    out = []
    issn = next((m.group(1) for l in linhas[:80] if (m := _RE_ISSN.search(l))), None)
    for i, l in enumerate(linhas[:120]):
        ls = limpar(l)
        m = _RE_REVISTA.search(ls)
        if m:
            ref = f"v. {m.group(2)}" + (f", n. {m.group(3)}" if m.group(3) else "") + (f", p. {m.group(4)}" if m.group(4) else "")
            _juntar(out, limpar(m.group(1)), _trecho(i, l), issn=issn, referencia=ref, ano=m.group(5))
            continue
        m = _RE_REVISTA_PIPE.search(ls)
        if m: _juntar(out, limpar(m.group(1)), _trecho(i, l), issn=issn)
    if issn and not out:
        out.append({"valor": f"ISSN {issn}", "origens": ["ISSN no cabeçalho — digite o nome do periódico"], "issn": issn, "incompleto": True})
    return out[:3]

def detectar_doi(linhas):
    for l in linhas[:150]:
        m = _RE_DOI.search(l)
        if m: return m.group(1).rstrip(".,;)")
    return None

_STOP = {
    "português": "de a o que e do da em um para é com não uma os no se na por mais as dos como mas foi ao ele das tem seu sua ou ser quando muito nos já está também só pelo pela até isso ela entre era depois sem mesmo aos ter".split(),
    "inglês": "the of and to in is that for it as with was on be by this are from or an at not have his but which had they you were their one all we can has there been if more when will would who so no".split(),
    "espanhol": "de la que el en y a los se del las un por con no una su para es al lo como más pero sus le ya o este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos".split(),
    "francês": "de la le et les des en un du une que est pour qui dans a par plus pas au sur ne se ce il sont ou avec son aux d' l' mais nous comme cette ses leur ont été fait tout".split(),
    "alemão": "der die und in den von zu das mit sich des auf für ist im dem nicht ein eine als auch es an werden aus er hat daß dass sie nach wird bei einer um am sind noch wie einem über einen so zum war haben nur oder aber vor zur bis mehr durch man sein wurde".split(),
    "italiano": "di e il la che è per un in con non una le si i da del come ma al dei più gli lo è della nel sono ha alla anche suo questo ci se tra o loro delle nella sua era dal".split(),
}

def detectar_idioma(texto):
    palavras = re.findall(r"[a-zà-ÿ']+", texto.lower()[:20000])
    if len(palavras) < 40: return []
    pont = {lg: sum(1 for p in palavras if p in set(ws)) / len(palavras) for lg, ws in _STOP.items()}
    ordem = sorted(pont.items(), key=lambda kv: -kv[1])
    (lg, s1), (_, s2) = ordem[0], ordem[1]
    if s1 < 0.12 or s1 - s2 < 0.015: return []
    return [{"valor": lg, "origens": [f"{round(100*s1)}% das palavras são comuns em {lg}"]}]

def candidatos_genero(linhas):
    """Prosa ou verso. Verso = linhas curtas E quase todas iniciadas em maiúscula. Conta-se o TEXTO
    (não o número de linhas): poucas linhas curtas de folha de rosto não devem enganar. Prosa quebrada
    em coluna de PDF tem linhas curtas, mas continua em minúscula."""
    uteis = [limpar(l) for l in linhas if not _e_ruido(l)]
    if len(uteis) < 6: return []
    caixa = round(100 * sum(l[0].isupper() for l in uteis) / len(uteis))
    total = sum(len(l) for l in uteis)
    longas = round(100 * sum(len(l) for l in uteis if len(l) > 60) / total)
    valor = "verso" if caixa >= 70 and longas < 35 else "prosa"
    return [{"valor": valor, "origens": [f"{caixa}% das linhas começam com maiúscula; {longas}% do texto está em linhas longas"]}]

# ------------------------------------------------------------------ tudo junto
_IDIOMAS_PG = {"portuguese": "português", "english": "inglês", "spanish": "espanhol", "french": "francês", "german": "alemão", "italian": "italiano"}

def identificar(caminho, autores_db=(), nome=None):
    """autores_db: fichas já criadas [{"id","nome","variantes":[...]}]. Devolve candidatos por campo, ou {"erro"}."""
    caminho = Path(caminho); nome = nome or caminho.name
    try: texto = extrair_texto(caminho)
    except ValueError as e: return {"erro": str(e)}
    if not texto.strip():
        return {"erro": "PDF sem camada de texto (escaneado?) — sem OCR não dá para ler"
                if caminho.suffix.lower() == ".pdf" else "arquivo sem texto legível"}
    todas = [dedup_linha(l) for l in texto.splitlines()]; meta = metadados_arquivo(caminho)
    pg = cabecalho_gutenberg(todas); util = depois_do_cabecalho(todas) if pg else todas
    linhas = corpo(util)
    formas, existentes = {}, {}
    for a in autores_db:
        formas[a["nome"]] = a["nome"]; existentes[normalizar(a["nome"])] = a["id"]
        for v in a.get("variantes") or []: formas[v] = a["nome"]
    pg_completo = (pg.get("title") or "").strip() or None
    pg_titulo = pg_completo.split(" | ")[0].strip() if pg_completo else None
    rosto = folha_de_rosto(linhas, pg_titulo); abnt = referencia_abnt(todas)
    extras = [(c["valor"], 0, c["origens"][0]) for c in rosto["autor"]]
    if abnt: extras.append((abnt["autor"], 0, "referência «Fonte:» — " + abnt["origem"]))
    if pg.get("author"): extras.append((_como_nome(pg["author"]), 1, "cabeçalho do Projeto Gutenberg: «Author»"))
    autores = candidatos_autor(linhas, nome, meta, formas, extras)
    for c in autores: c["author_id"] = existentes.get(normalizar(c["valor"]))
    titulos = candidatos_titulo(linhas, nome, meta, [c["valor"] for c in autores])
    pri = []
    if abnt: _juntar(pri, abnt["titulo"], "referência «Fonte:» — " + abnt["origem"])
    if pg_titulo: _juntar(pri, pg_titulo, "cabeçalho do Projeto Gutenberg: «Title»")
    for c in rosto["titulo"]: _juntar(pri, c["valor"], c["origens"][0])
    if pg_completo and " | " in pg_completo:
        _juntar(pri, pg_completo.replace(" | ", ": "), "cabeçalho do Projeto Gutenberg: título com subtítulo")
    for c in titulos:                       # títulos "adivinhados" só entram se nada mais forte apareceu
        if not pri or c["origens"][0] == "nome do arquivo" or c["origens"][0] == "metadados do arquivo": _juntar(pri, c["valor"], c["origens"][0])
    if len(pri) >= 2 and len(pri[1]["valor"]) < len(pri[0]["valor"]) and normalizar(pri[0]["valor"]).startswith(normalizar(pri[1]["valor"])):
        pri[0], pri[1] = pri[1], pri[0]          # "Iracema" antes de "Iracema com uma notícia biográfica…"
    ano, ano_edicao = candidatos_anos(linhas, nome, rosto, abnt, pg)
    # DOI só conta no começo do corpo: em «Referências» ele é citação, não identidade do documento
    doi = detectar_doi(linhas[:60]); periodico = candidatos_periodico(linhas)
    editora = candidatos_editora(linhas)
    for c in rosto["editora"]: _juntar(editora, c["valor"], c["origens"][0])
    if abnt: _juntar(editora, abnt["editora"], "referência «Fonte:» — " + abnt["origem"])
    local = list(rosto["local"])
    if abnt: _juntar(local, abnt["local"], "referência «Fonte:» — " + abnt["origem"])
    nota_ed = list(rosto["edicao_nota"])
    if abnt and abnt.get("edicao"): _juntar(nota_ed, f"{abnt['edicao']}ª edição", "referência «Fonte:» — " + abnt["origem"])
    idioma = detectar_idioma(texto)
    if pg.get("language"):
        lg = _IDIOMAS_PG.get(pg["language"].lower())
        if lg: _juntar(idioma, lg, "cabeçalho do Projeto Gutenberg: «Language»")
        idioma.sort(key=lambda c: 0 if "Gutenberg" in c["origens"][0] else 1)
    fonte = [{"valor": f"Projeto Gutenberg #{pg['numero']}", "origens": ["cabeçalho do Projeto Gutenberg"]}] if pg.get("numero") else []
    return {"arquivo": nome, "doi": doi, "autor": autores, "titulo": pri[:4],
            "ano": ano, "ano_edicao": ano_edicao, "editora": editora[:3], "local": local[:2], "edicao_nota": nota_ed[:2],
            "tradutor": _creditos(linhas, _RE_TRAD), "organizador": _creditos(linhas, _RE_ORG),
            "periodico": periodico, "idioma": idioma, "genero": candidatos_genero(util), "fonte": fonte,
            "tipo": [{"valor": "artigo", "origens": ["tem DOI ou citação de periódico"]}] if (doi or any(p.get("referencia") or p.get("issn") for p in periodico)) else []}
