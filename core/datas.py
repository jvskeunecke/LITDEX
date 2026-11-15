"""Datas em texto livre -> âncora numérica e classificação de precisão.

Uma data histórica tem duas camadas, e o LitDex nunca as confunde:

  • o **rótulo** que o pesquisador escreveu ("c. 800 a.C.", "séc. XIX", "1850-1900");
  • a **âncora numérica** usada para ordenar, filtrar e desenhar.

`ano_num` é a âncora (inteiro; a.C. é negativo). `parse_data_historica` devolve a
faixa e o tipo de precisão. `ano_preciso` só responde quando a expressão denota um
ano pontual — é o que as inferências (contemporaneidade, alertas) exigem.

Regras que este módulo garante:

  • era é um token, não uma letra: "384 a.C." é exato (-384), mas "Machado" não é
    uma era e "1850-1900" não vira intervalo negativo;
  • século vira faixa (1801-1900), nunca um ano artificial;
  • intervalos explícitos viram faixa; "pós-" e "pré-" viram faixa aberta;
  • marcadores de aproximação (c., ca., circa, aprox., ~) rebaixam a precisão,
    sem alterar a âncora.
"""
import re

_ROM = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}

# Era escrita como palavra própria, admitindo pontuação e fim de string.
_ERA = r"(?:a\.?\s*c\.?|aec|bc|bce|antes\s+de\s+cristo|d\.?\s*c\.?|ad|ce|ec)"
_ERA_AC = {"ac", "aec", "bc", "bce", "antesdecristo"}

_NUM_ERA = re.compile(rf"(?<![\w/])(-?\d{{1,4}})\s*({_ERA})?(?![\w/])", re.I)
_SECULO = re.compile(r"\bs[ée]c(?:ulo)?\.?\s*([ivxlcdm]+|\d{1,2})\b", re.I)
_SECULO_ERA = re.compile(rf"s[ée]c(?:ulo)?\.?\s*(?:[ivxlcdm]+|\d{{1,2}})\s*({_ERA})", re.I)
_APROX = re.compile(
    r"(?:(?<![.\w])c\.\s*|(?<![.\w])ca\.\s*|\bcirca\b|\baprox(?:imadamente)?\.?\b|\bpor volta de\b|\bcerca de\b|[~≈])",
    re.I)
_INFERIDA = re.compile(r"\b(inferid[oa]|provável|provavelmente|estimad[oa]|calc\.)\b", re.I)
_INTERVALO = re.compile(
    r"(?:(?:entre\s+)?(-?\d{3,4})\s*(?:–|—|-|\ba\b|\baté\b|\be\b)\s*(-?\d{3,4}))", re.I)
_POS = re.compile(r"\bpós[-\s]?\s*(\d{3,4})\b", re.I)
_PRE = re.compile(r"\bpré[-\s]?\s*(\d{3,4})\b", re.I)
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_BR = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def _romano(txt):
    n, ant = 0, 0
    for ch in reversed(txt.lower()):
        v = _ROM.get(ch, 0)
        n += -v if v < ant else v
        ant = max(ant, v)
    return n


def _normaliza_era(era):
    if not era:
        return None
    e = re.sub(r"[.\s]", "", era.lower())
    if e in {"ac", "aec", "bc", "bce", "antesdecristo"}:
        return "ac"
    if e in {"dc", "ad", "ce", "ec"}:
        return "dc"
    return None


def _com_era(ano, era):
    """Aplica a era ao número; ano já negativo é preservado como a.C."""
    era = _normaliza_era(era)
    if ano < 0:
        return ano
    return -ano if era == "ac" else ano


def _precisao(texto, base="exata"):
    if _INFERIDA.search(texto):
        return "inferida"
    if _APROX.search(texto):
        return "aproximada"
    if "?" in texto or "~" in texto:
        return "aproximada"
    return base


def _intervalo_seculo(sec, negativo):
    if negativo:
        return (-sec * 100, -(sec - 1) * 100 - 1)
    return ((sec - 1) * 100 + 1, sec * 100)


def _vazia(original):
    return {"ano_inicio": None, "ano_fim": None, "tipo_precisao": "desconhecida",
            "rotulo_original": original}


def _tokens_de_ano(texto):
    """Anos reconhecíveis, com a era de cada um, na ordem em que aparecem."""
    out = []
    for m in _NUM_ERA.finditer(texto):
        antes = texto[max(0, m.start() - 14):m.start()].lower()
        if re.search(r"s[ée]c(?:ulo)?\.?\s*$", antes):
            continue  # número que pertence a um século já tratado
        out.append((m.start(), m.end(), _com_era(int(m.group(1)), m.group(2))))
    return out


def analisar(texto_data):
    """Analisa a data e devolve faixa + precisão. Função única por trás de tudo."""
    original = "" if texto_data is None else str(texto_data).strip()
    if not original:
        return _vazia(original)
    t = original.strip()

    # 1. datas completas
    m = _ISO.match(t)
    if m:
        ano = int(m.group(1))
        return {"ano_inicio": ano, "ano_fim": ano, "tipo_precisao": "exata", "rotulo_original": original}
    m = _BR.match(t)
    if m:
        ano = int(m.group(3))
        return {"ano_inicio": ano, "ano_fim": ano, "tipo_precisao": "exata", "rotulo_original": original}

    # 2. século (romano ou arábico), com era opcional
    m = _SECULO.search(t)
    if m:
        bruto = m.group(1)
        sec = int(bruto) if bruto.isdigit() else _romano(bruto)
        if sec:
            me = _SECULO_ERA.search(t)
            neg = bool(me) and _normaliza_era(me.group(1)) == "ac"
            ini, fim = _intervalo_seculo(sec, neg)
            return {"ano_inicio": ini, "ano_fim": fim, "tipo_precisao": "intervalo",
                    "rotulo_original": original}

    # 3. intervalo explícito entre dois anos
    m = _INTERVALO.search(t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        era = None
        me = re.match(rf"\s*({_ERA})", t[m.end():m.end() + 16], re.I)
        if me:
            era = _normaliza_era(me.group(1))
        if era == "ac" or (a < 0 or b < 0):
            a, b = -abs(a), -abs(b)
        return {"ano_inicio": min(a, b), "ano_fim": max(a, b),
                "tipo_precisao": _precisao(t, "intervalo"), "rotulo_original": original}

    # 4. faixas abertas
    m = _POS.search(t)
    if m:
        return {"ano_inicio": int(m.group(1)), "ano_fim": None, "tipo_precisao": "inferida",
                "rotulo_original": original}
    m = _PRE.search(t)
    if m:
        return {"ano_inicio": None, "ano_fim": int(m.group(1)), "tipo_precisao": "inferida",
                "rotulo_original": original}

    # 5. um ano pontual (o primeiro token com era, se houver)
    tokens = _tokens_de_ano(t)
    if tokens:
        ano = tokens[0][2]
        return {"ano_inicio": ano, "ano_fim": ano, "tipo_precisao": _precisao(t, "exata"),
                "rotulo_original": original}

    # 6. nada legível
    return _vazia(original)


# compatibilidade: o nome antigo continua válido
def parse_data_historica(texto_data):
    return analisar(texto_data)


def ano_num(s):
    """Âncora numérica para ordenar/desenhar: inteiro, a.C. negativo, século no meio.

    Sem data legível -> None. Intervalos usam o início; séculos usam o ponto médio.
    """
    r = analisar(s)
    ini, fim = r["ano_inicio"], r["ano_fim"]
    if ini is None and fim is None:
        return None
    if r["tipo_precisao"] == "intervalo" and ini is not None and fim is not None:
        if _SECULO.search(str(s) or ""):
            return (ini + fim) // 2
        return ini
    return ini if ini is not None else fim


def rotulo_ano(n):
    if n is None:
        return ""
    return f"{-n} a.C." if n < 0 else str(n)


def ano_preciso(s):
    """Ano pontual explícito, ou None. Usado em inferências que exigem certeza."""
    r = analisar(s)
    if r["tipo_precisao"] != "exata":
        return None
    ini, fim = r["ano_inicio"], r["ano_fim"]
    return ini if ini == fim else None
