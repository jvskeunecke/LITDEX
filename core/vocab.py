"""Vocabulário das relações — onde a teoria entra no programa.

Cada relação é uma ligação TIPADA entre entidades (autor, obra, periódico, evento, mídia, instituição). Os tipos estão agrupados em famílias, cada uma ancorada num repertório:

 • transtextual  — literatura comparada; Genette (Palimpsestos, 1982): intertextualidade
                   (citação, alusão), paratextualidade (epígrafe), metatextualidade
                   (comentário), hipertextualidade (paródia, pastiche, continuação, reescrita).
 • intermidial   — as três subcategorias de Rajewsky (2015), apresentadas em Ghirardi,
                   Rajewsky e Diniz (2020): transposição midiática, combinação de mídias,
                   referências intermidiáticas (écfrase, escrita fílmica, musicalização...).
 • estrutura     — descrição em níveis, como nos instrumentos arquivísticos (fundo > série >
                   item): um poema que é parte de um livro, um trecho recortado de uma obra.
 • publicacao/encontro — o que medeia as relações entre pessoas: periódicos, cartas, eventos.
 • livre         — "ligação livre" com rótulo à escolha: o mapa nunca está fechado
                   (Deleuze e Guattari: o rizoma é sempre conectável a algo novo).

`origem`/`destino` dizem entre quais tipos de entidade a relação faz sentido; a interface só
oferece o que cabe, mas "ligação livre" aceita qualquer par."""

ENTIDADES = {
    "author":     {"rotulo": "Autor",    "plural": "Autores",    "cor": "#8b3a1f", "simbolo": "circle"},
    "work":       {"rotulo": "Obra",     "plural": "Obras",      "cor": "#2f6f8f", "simbolo": "square"},
    "periodical": {"rotulo": "Periódico","plural": "Periódicos", "cor": "#5d8a2f", "simbolo": "diamond"},
    "event":      {"rotulo": "Evento",   "plural": "Eventos",    "cor": "#b8860b", "simbolo": "triangle"},
    "media":      {"rotulo": "Mídia",    "plural": "Mídias",     "cor": "#7a4fa3", "simbolo": "star"},
    "institution":{"rotulo":"Instituição","plural":"Instituições","cor":"#9b4f78","simbolo":"hexagon"},
}

FAMILIAS = [
    ("autoria",      "Autoria e papéis",       "#9a8f7c", "Quem fez, traduziu, organizou, ilustrou."),
    ("estrutura",    "Parte e todo",           "#7b8794", "Descrição em níveis: capítulo, poema num livro, recorte."),
    ("transtextual", "Relações entre textos",  "#b5502a", "Genette (1982): inter, para, meta e hipertextualidade."),
    ("intermidial",  "Intermidialidade",       "#6a3fa0", "Rajewsky (2015): transposição, combinação e referência entre mídias."),
    ("social",       "Vínculos entre pessoas", "#2e7d5b", "Influência, amizade, correspondência, polêmica..."),
    ("discurso",     "Avaliação e discurso",    "#a23d63", "Elogio, crítica e outras tomadas de posição atribuídas a uma fonte e a um contexto."),
    ("publicacao",   "Publicação e suportes",  "#c28a0e", "Revistas, jornais, almanaques: o que circula entre as pessoas."),
    ("encontro",     "Encontros e eventos",    "#1f7a99", "Saraus, congressos, lançamentos, exposições."),
    ("livre",        "Ligação livre",          "#8a8175", "Rótulo à escolha — para o que ainda não tem nome."),
]

def _r(familia, direta, inversa, origem, destino, simetrica=False, desc=""):
    return {"familia": familia, "direta": direta, "inversa": inversa, "simetrica": simetrica,
            "origem": origem, "destino": destino, "desc": desc}

A, W, P, E, M, I = "author", "work", "periodical", "event", "media", "institution"

RELACOES = {
    # autoria
    "autor_de":   _r("autoria", "é autor(a) de", "tem como autor(a)", [A], [W], desc="Coautoria (o autor principal fica na própria obra)."),
    "traduziu":   _r("autoria", "traduziu", "foi traduzida por", [A], [W]),
    "organizou":  _r("autoria", "organizou", "foi organizada por", [A], [W]),
    "ilustrou":   _r("autoria", "ilustrou", "foi ilustrada por", [A], [W]),
    "prefaciou":  _r("autoria", "prefaciou", "foi prefaciada por", [A], [W]),
    "entrevistou": _r("autoria", "entrevistou", "teve como entrevistador(a)", [A], [W], desc="Papel no documento de entrevista; não confundir com autoria do texto transcrito."),
    "entrevistado_em": _r("autoria", "foi entrevistado(a) em", "teve como entrevistado(a)", [A], [W], desc="Papel da pessoa entrevistada, diferente de autor, editor ou entrevistador."),
    # estrutura
    "parte_de":   _r("estrutura", "é parte de", "contém", [W], [W], desc="Capítulo, conto numa coletânea, poema num livro, trecho recortado."),
    "versao_de":  _r("estrutura", "é versão de", "tem como versão", [W], [W], desc="Variantes e reelaborações do mesmo texto."),
    # transtextual
    "alude":      _r("transtextual", "alude a", "é aludida por", [W], [W], desc="Intertextualidade: alusão."),
    "epigrafe":   _r("transtextual", "usa como epígrafe", "é epígrafe de", [W], [W], desc="Paratextualidade."),
    "comenta":    _r("transtextual", "comenta", "é comentada por", [W, A], [W, A, P, I], desc="Comentário sobre entidade identificada; não implica avaliação negativa."),
    "menciona":   _r("discurso", "menciona", "é mencionada por", [A, W, P, E], [A, W, P, E, M, I], desc="Menção neutra: não registra elogio nem crítica."),
    "cita":       _r("transtextual", "cita", "é citada por", [W], [W, A, P, M, I], desc="Citação explícita; pode ter como alvo obra, autor, periódico, mídia ou instituição."),
    "parodia":    _r("transtextual", "parodia", "é parodiada por", [W], [W], desc="Hipertextualidade."),
    "pastiche":   _r("transtextual", "imita (pastiche)", "é imitada por", [W], [W], desc="Hipertextualidade."),
    "continua":   _r("transtextual", "continua", "é continuada por", [W], [W], desc="Hipertextualidade."),
    "reescreve":  _r("transtextual", "reescreve", "é reescrita por", [W], [W], desc="Hipertextualidade."),
    "responde":   _r("transtextual", "responde a", "é respondida por", [W], [W]),
    "traducao_de":_r("transtextual", "é tradução de", "foi traduzida em", [W], [W]),
    "dedica":     _r("transtextual", "é dedicada a", "recebeu a dedicatória de", [W], [A], desc="Paratextualidade."),
    "homenageia": _r("transtextual", "homenageia", "é homenageado(a) por", [A, W], [A, W]),
    # intermidialidade (Rajewsky 2015)
    "transposicao":    _r("intermidial", "é transposição midiática de", "foi transposta em", [W], [W],
                          desc="Rajewsky 1: um texto-fonte numa mídia gera um produto em outra (romance → filme)."),
    "combina_com":     _r("intermidial", "combina-se com (co-presença)", "combina-se com (co-presença)", [W], [W], True,
                          desc="Rajewsky 2: mídias co-presentes no mesmo artefato (iluminura, HQ, livro de artista)."),
    "ilustra":         _r("intermidial", "ilustra", "é ilustrada por", [W], [W], desc="Combinação de mídias: imagem e texto."),
    "ref_intermidial": _r("intermidial", "faz referência intermidiática a", "é referenciada por", [W], [W, M],
                          desc="Rajewsky 3: refere-se a outra mídia (a uma obra ou à mídia como sistema)."),
    "ecfrase":         _r("intermidial", "descreve (écfrase)", "é descrita em", [W], [W, M], desc="Referência a obras das Belas Artes."),
    "escrita_filmica": _r("intermidial", "evoca o cinema (escrita fílmica)", "é evocada em", [W], [W, M]),
    "musicalizacao":   _r("intermidial", "evoca a música (musicalização)", "é evocada em", [W], [W, M]),
    # vínculos entre pessoas
    "influencia":       _r("social", "influencia", "é influenciado(a) por", [A], [A]),
    "mestre_discipulo": _r("social", "é mestre de", "é discípulo(a) de", [A], [A]),
    "correspondencia":  _r("social", "correspondeu-se com", "correspondeu-se com", [A], [A], True),
    "amizade":          _r("social", "é amigo(a) de", "é amigo(a) de", [A], [A], True),
    "amoroso":          _r("social", "teve relação amorosa com", "teve relação amorosa com", [A], [A], True),
    "parentesco":       _r("social", "é parente de", "é parente de", [A], [A], True),
    "polemica":         _r("social", "polemizou com", "polemizou com", [A], [A], True),
    # avaliações direcionais: permitem registrar mais de uma ocorrência, em datas e suportes diferentes
    "elogia":           _r("discurso", "elogiou", "foi elogiado(a) por", [A, W], [A, W, P, I]),
    "critica":          _r("discurso", "criticou", "foi criticado(a) por", [A, W], [A, W, P, I]),
    "colaboracao":      _r("social", "colaborou com", "colaborou com", [A], [A], True),
    # publicação
    "publicado_em":  _r("publicacao", "foi publicado(a) em", "publicou", [W], [P], desc="Vínculo bibliográfico entre uma obra e o periódico que a publicou; prefira registrar também a manifestação/fascículo quando identificados."),
    "colaborou_em":  _r("publicacao", "colaborou em", "teve a colaboração de", [A], [P]),
    "editou":        _r("publicacao", "editou / dirigiu", "foi editado(a) por", [A], [P]),
    "fundou":        _r("publicacao", "fundou", "foi fundado(a) por", [A], [P]),
    # encontros
    "participou":    _r("encontro", "participou de", "teve a participação de", [A], [E]),
    "apresentada_em":_r("encontro", "foi apresentada em", "apresentou", [W], [E]),
    # livre
    "liga": _r("livre", "liga-se a", "liga-se a", [A, W, P, E, M, I], [A, W, P, E, M, I], True,
               desc="Use o campo 'rótulo' para dizer qual é a ligação."),
}

# Relações guardadas por versões anteriores -> (tipo novo, rótulo)
LEGADO = {
    "traducao":      ("liga", "traduzido por"),
    "dedicatoria":   ("liga", "dedicado a"),
    "resposta":      ("liga", "responde a"),
    "parodia_autor": ("liga", "parodia"),
    "contemporaneo": ("liga", "contemporâneo de"),
}

TIPOS_PERIODICO = ["revista", "jornal", "suplemento", "almanaque", "boletim", "periódico acadêmico", "blog", "outro"]
TIPOS_EVENTO    = ["encontro", "sarau", "congresso", "lançamento", "exposição", "viagem", "polêmica", "outro"]
MIDIAS_SUGERIDAS = ["texto verbal", "pintura", "fotografia", "cinema", "música", "teatro",
                    "história em quadrinhos", "escultura", "televisão", "jogo digital", "performance"]

def validar(tipo, origem_tipo, destino_tipo):
    """None se a relação cabe entre esses tipos; senão, a mensagem de erro."""
    r = RELACOES.get(tipo)
    if not r: return f"tipo de relação desconhecido: {tipo}"
    if origem_tipo in r["origem"] and destino_tipo in r["destino"]: return None
    if r["simetrica"] and destino_tipo in r["origem"] and origem_tipo in r["destino"]: return None
    return (f"«{r['direta']}» não se aplica de {ENTIDADES[origem_tipo]['rotulo'].lower()} "
            f"para {ENTIDADES[destino_tipo]['rotulo'].lower()}")

def vocab_publico():
    return {
        "entidades": ENTIDADES,
        "familias": [{"chave": k, "titulo": t, "cor": c, "desc": d} for k, t, c, d in FAMILIAS],
        "relacoes": RELACOES,
        "tipos_periodico": TIPOS_PERIODICO, "tipos_evento": TIPOS_EVENTO,
        "midias_sugeridas": MIDIAS_SUGERIDAS, "generos": ["prosa", "verso"],
    }
