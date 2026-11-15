"""Módulo ONLINE (opcional, desligado por padrão).

O que ele faz: dado o que já está na tela de revisão (título, autor, DOI) ou o nome de um
autor, consulta fontes abertas e devolve SUGESTÕES com o link da fonte:
  • Crossref   — artigos com DOI: título, autores, periódico (volume/número/páginas), ano.
  • Open Library — livros: ano da primeira publicação, editoras, idioma.
  • Wikidata   — pessoas: nascimento, morte (inclusive a.C.), descrição, país/lugar.
O que ele NÃO faz: enviar o arquivo, gravar qualquer coisa sozinho ou rodar sem o usuário ligar."""
import json, re, urllib.parse, urllib.request
from . import config

UA = "LitDex/1.0 (fichario pessoal de literatura)"

class OnlineErro(Exception): pass

# ------------------------------------------------------------------ configuração
def ler_config():
    try: return json.loads(config.CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError): return {}

def ativo(): return bool(ler_config().get("online"))

def definir_ativo(valor):
    c = ler_config(); c["online"] = bool(valor)
    config.CONFIG.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")

def _get_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise OnlineErro(f"sem resposta de {urllib.parse.urlparse(url).netloc} ({e})")

def _c(valor, origem, **extra): return {"valor": valor, "origens": [origem], **extra}

# ------------------------------------------------------------------ Crossref
def parse_crossref(j, doi):
    m = j.get("message", {}); fonte = f"Crossref: https://doi.org/{doi}"; out = {}
    if m.get("title"): out["titulo"] = [_c(m["title"][0], fonte)]
    nomes = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in m.get("author", []) if a.get("family")]
    if nomes: out["autor"] = [_c(n, fonte) for n in nomes]
    partes = (m.get("issued", {}).get("date-parts") or [[None]])[0]
    ano = str(partes[0]) if partes and partes[0] else None
    if ano: out["ano"] = [_c(ano, fonte)]
    if m.get("container-title"):
        ref = ", ".join(x for x in (f"v. {m['volume']}" if m.get("volume") else "",
                                    f"n. {m['issue']}" if m.get("issue") else "",
                                    f"p. {m['page']}" if m.get("page") else "") if x)
        out["periodico"] = [_c(m["container-title"][0], fonte, issn=(m.get("ISSN") or [None])[0], referencia=ref, ano=ano)]
    if m.get("publisher"): out["editora"] = [_c(m["publisher"], fonte)]
    return out

# ------------------------------------------------------------------ Open Library
_LINGUAS = {"por": "português", "eng": "inglês", "spa": "espanhol", "fre": "francês", "fra": "francês",
            "ger": "alemão", "deu": "alemão", "ita": "italiano"}

def parse_openlibrary(j):
    out = {"autor": [], "ano": [], "editora": [], "idioma": []}
    for d in (j.get("docs") or [])[:3]:
        fonte = f"Open Library: https://openlibrary.org{d.get('key', '')}"
        if d.get("author_name"): out["autor"].append(_c(d["author_name"][0], fonte))
        if d.get("first_publish_year"): out["ano"].append(_c(str(d["first_publish_year"]), fonte + " (1ª publicação)"))
        for p in (d.get("publisher") or [])[:2]: out["editora"].append(_c(p, fonte))
        for lg in (d.get("language") or [])[:1]:
            if lg in _LINGUAS: out["idioma"].append(_c(_LINGUAS[lg], fonte))
    return {k: v for k, v in out.items() if v}

def _unir(a, b):
    for k, v in b.items():
        lista = a.setdefault(k, [])
        for c in v:
            if not any(x["valor"].lower() == c["valor"].lower() for x in lista): lista.append(c)
    return a

def obra(titulo=None, autor=None, doi=None):
    """Sugestões para a tela de revisão, no mesmo formato do scanner."""
    out = {}
    if doi:
        _unir(out, parse_crossref(_get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")), doi))
    if titulo and not doi:
        q = {"title": titulo, "limit": 3, "fields": "key,title,author_name,first_publish_year,publisher,language"}
        if autor: q["author"] = autor
        _unir(out, parse_openlibrary(_get_json("https://openlibrary.org/search.json?" + urllib.parse.urlencode(q))))
    return out

# ------------------------------------------------------------------ Wikidata (pessoas, obras, periódicos, eventos)
def tempo_para_texto(v):
    """{'time': '+1839-06-21T00:00:00Z', 'precision': 11} -> '1839-06-21'; a.C. -> '384 a.C.'"""
    m = re.match(r"([+-])(\d+)-(\d\d)-(\d\d)", v.get("time", ""))
    if not m: return None
    sinal, ano, mes, dia = m.group(1), int(m.group(2)), m.group(3), m.group(4)
    p = v.get("precision", 9)
    if sinal == "-": return f"{ano} a.C." if p >= 9 else f"c. {ano} a.C."
    if p >= 11 and mes != "00" and dia != "00": return f"{ano:04d}-{mes}-{dia}"
    if p == 10 and mes != "00": return f"{ano:04d}-{mes}"
    return str(ano) if p >= 9 else f"c. {ano}"

def _claim(ent, pid):
    return [c["mainsnak"]["datavalue"]["value"] for c in ent.get("claims", {}).get(pid, [])
            if c.get("mainsnak", {}).get("datavalue")]

_TEMPOS = ("P569", "P570", "P577", "P571", "P576", "P585", "P580", "P582")      # nascimento, morte, publicação, início, fim, data, início, fim
_ITENS = ("P27", "P19", "P50", "P291", "P276", "P17", "P31")                     # cidadania, nascimento, autor, lugar de publicação, local, país, instância de
_TEXTOS = ("P236",)                                                              # ISSN

def parse_wikidata(entidades, rotulos):
    """Entidades do Wikidata em forma neutra: nome, descrição, tempos, itens (rótulos) e textos."""
    out = []
    for qid, e in entidades.items():
        nome = (e.get("labels", {}).get("pt") or e.get("labels", {}).get("en") or {}).get("value")
        if not nome: continue
        desc = (e.get("descriptions", {}).get("pt") or e.get("descriptions", {}).get("en") or {}).get("value", "")
        tempos = {p: t for p in _TEMPOS for t in [next((tempo_para_texto(v) for v in _claim(e, p) if isinstance(v, dict)), None)] if t}
        itens = {p: [rotulos.get(v["id"]) or v["id"] for v in _claim(e, p) if isinstance(v, dict) and v.get("id")] for p in _ITENS}
        textos = {p: [v for v in _claim(e, p) if isinstance(v, str)] for p in _TEXTOS}
        out.append({"qid": qid, "nome": nome, "descricao": desc, "tempos": tempos, "itens": {k: v for k, v in itens.items() if v},
                    "textos": {k: v for k, v in textos.items() if v}, "ids_itens": {p: [v["id"] for v in _claim(e, p) if isinstance(v, dict) and v.get("id")] for p in _ITENS},
                    "fonte": f"Wikidata: https://www.wikidata.org/wiki/{qid}"})
    return out

def _wd(params):
    return "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})

def wikidata(nome, limite=4):
    achados = _get_json(_wd({"action": "wbsearchentities", "search": nome, "language": "pt", "uselang": "pt", "type": "item", "limit": 6})).get("search", [])
    ids = [a["id"] for a in achados][:6]
    if not ids: return []
    ents = _get_json(_wd({"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|labels|descriptions", "languages": "pt|en"})).get("entities", {})
    precisa = {v["id"] for e in ents.values() for p in _ITENS for v in _claim(e, p) if isinstance(v, dict) and v.get("id")}
    rotulos = {}
    if precisa:
        rs = _get_json(_wd({"action": "wbgetentities", "ids": "|".join(sorted(precisa)[:45]), "props": "labels", "languages": "pt|en"})).get("entities", {})
        rotulos = {q: (x.get("labels", {}).get("pt") or x.get("labels", {}).get("en") or {}).get("value") for q, x in rs.items()}
    return parse_wikidata({q: ents[q] for q in ids if q in ents}, rotulos)[:limite]

def autor(nome):
    """Pessoas homônimas (P31 = humano) com datas e lugares — formato usado pela ficha do autor."""
    out = []
    for e in wikidata(nome, 6):
        if "Q5" not in e["ids_itens"].get("P31", []): continue
        out.append({"nome": e["nome"], "descricao": e["descricao"], "nascimento": e["tempos"].get("P569"), "morte": e["tempos"].get("P570"),
                    "lugares": [*e["itens"].get("P27", []), *e["itens"].get("P19", [])], "fonte": e["fonte"]})
    return out[:3]

# ------------------------------------------------------------------ cartões de sugestão (todas as fichas)
def _cartao(titulo, descricao, fonte, campos=None, lugares=None, tags=None, edicao=None):
    return {"titulo": titulo, "descricao": descricao, "fonte": fonte, "campos": {k: v for k, v in (campos or {}).items() if v},
            "lugares": [{"nome": n} for n in (lugares or []) if n], "tags": tags or [], "edicao": {k: v for k, v in (edicao or {}).items() if v}}

def parse_openlibrary_cartoes(j):
    out = []
    for d in (j.get("docs") or [])[:3]:
        fonte = f"Open Library: https://openlibrary.org{d.get('key', '')}"
        lg = _LINGUAS.get((d.get("language") or [""])[0])
        out.append(_cartao(d.get("title", "?"), ", ".join(d.get("author_name") or []), fonte,
                           campos={"ano": str(d["first_publish_year"]) if d.get("first_publish_year") else None},
                           tags=[x.lower() for x in (d.get("subject") or [])[:5]],
                           edicao={"editora": (d.get("publisher") or [None])[0], "idioma": lg}))
    return out

def sugerir(tipo, f):
    """Cartões de sugestão para a ficha `f` (dict da ficha). Cada cartão traz campos aplicáveis e a fonte."""
    nome = f.get("_nome") or ""
    if tipo == "author":
        return [_cartao(p["nome"], p["descricao"], p["fonte"], {"nascimento": p["nascimento"], "morte": p["morte"]}, p["lugares"]) for p in autor(nome)]
    if tipo == "work":
        out = []
        q = {"title": nome, "limit": 3, "fields": "key,title,author_name,first_publish_year,publisher,language,subject"}
        if f.get("author_nome"): q["author"] = f["author_nome"]
        out += parse_openlibrary_cartoes(_get_json("https://openlibrary.org/search.json?" + urllib.parse.urlencode(q)))
        for e in wikidata(nome, 3):
            if e["tempos"].get("P577") or e["itens"].get("P50"):
                out.append(_cartao(e["nome"], (e["descricao"] + (" · " + ", ".join(e["itens"]["P50"]) if e["itens"].get("P50") else "")).strip(" ·"), e["fonte"],
                                   {"ano": e["tempos"].get("P577")}))
        return out
    if tipo == "periodical":
        out = []
        if f.get("issn"):
            m = _get_json("https://api.crossref.org/journals/" + urllib.parse.quote(f["issn"])).get("message", {})
            if m.get("title"): out.append(_cartao(m["title"], m.get("publisher", ""), f"Crossref: ISSN {f['issn']}", {"issn": (m.get("ISSN") or [f["issn"]])[0]}))
        else:
            for m in (_get_json("https://api.crossref.org/journals?" + urllib.parse.urlencode({"query": nome, "rows": 3})).get("message", {}).get("items") or [])[:3]:
                out.append(_cartao(m.get("title", "?"), m.get("publisher", ""), "Crossref: periódicos", {"issn": (m.get("ISSN") or [None])[0], "tipo": "periódico acadêmico"}))
        for e in wikidata(nome, 3):
            if e["tempos"].get("P571") or e["itens"].get("P291") or e["textos"].get("P236"):
                out.append(_cartao(e["nome"], e["descricao"], e["fonte"], {"ano_inicio": e["tempos"].get("P571"), "ano_fim": e["tempos"].get("P576"),
                                   "issn": (e["textos"].get("P236") or [None])[0]}, e["itens"].get("P291")))
        return out
    if tipo == "event":
        return [_cartao(e["nome"], e["descricao"], e["fonte"], {"ano": e["tempos"].get("P585") or e["tempos"].get("P580")},
                        [*e["itens"].get("P276", []), *e["itens"].get("P17", [])]) for e in wikidata(nome, 4) if e["tempos"].get("P585") or e["tempos"].get("P580")]
    return [_cartao(e["nome"], e["descricao"], e["fonte"], {"notas": e["descricao"]}) for e in wikidata(nome, 3) if e["descricao"]]

# ------------------------------------------------------------------ lugares (Nominatim / OpenStreetMap)
_TIPO_OSM = {"country": "pais", "state": "estado", "region": "estado", "province": "estado", "city": "cidade", "town": "cidade", "village": "cidade",
             "municipality": "cidade", "suburb": "cidade", "neighbourhood": "cidade", "city_district": "cidade", "county": "cidade"}

def parse_nominatim(lista):
    out = []
    for r in lista[:6]:
        a = r.get("address") or {}; tipo = _TIPO_OSM.get(r.get("addresstype") or r.get("type"), "outro")
        nome = r.get("name") or (r.get("display_name") or "").split(",")[0]
        partes = [a.get(k) for k in ("city", "town", "village", "state", "country") if a.get(k) and a.get(k) != nome]
        out.append({"nome": nome, "tipo": tipo, "contexto": ", ".join(dict.fromkeys(partes)), "lat": round(float(r["lat"]), 4), "lon": round(float(r["lon"]), 4),
                    "fonte": "OpenStreetMap/Nominatim"})
    return out

def lugar(q):
    return parse_nominatim(_get_json("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "addressdetails": 1, "limit": 6, "accept-language": "pt-BR"})))
