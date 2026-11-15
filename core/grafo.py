"""Motor do grafo. UM grafo só (rizoma): nós de tipos diferentes, ligações tipadas.
Autor×autor e obra×obra não são grafos separados — são PROJEÇÕES do mesmo grafo:
  • projeção "autores": dois autores se ligam quando algo os conecta — uma relação direta,
    uma relação entre obras deles, uma tradução/dedicatória, uma revista ou um evento em comum.
    Cada ligação guarda a MEDIAÇÃO (direta, obra, periódico, evento), responde à pergunta
    "a relação entre dois autores sempre se dá por produções?": não — e o grafo mostra como.
  • projeção "obras": obras ligadas por relações entre textos/mídias ou por publicação conjunta.
Camadas calculadas (nunca gravadas): contemporâneos (vidas sobrepostas), tags e lugares
(nós-concentradores que formam "platôs")."""
from collections import defaultdict, deque
from .db import lista
from .vocab import RELACOES, ENTIDADES
from .datas import ano_preciso
from . import entidades as E
from .relacoes import rotulo_de

def _chave(t, i): return f"{t}:{i}"

def _carregar(c, pid):
    nos = {}
    def put(tipo, sql, mk):
        ids = E.ids_do_perfil(c, pid, tipo)
        for r in lista(c, sql):
            if ids is not None and r["id"] not in ids: continue
            nos[_chave(tipo, r["id"])] = {"id": _chave(tipo, r["id"]), "tipo": tipo, "ref_id": r["id"], **mk(r)}
    put("author", "SELECT id,nome,nascimento,morte,nasc_num,morte_num,notas FROM authors", lambda r: {
        "nome": r["nome"], "ano": r["nasc_num"], "fim": r["morte_num"],
        "nascimento_texto": r["nascimento"], "morte_texto": r["morte"],
        "data": " – ".join(x for x in (r["nascimento"], r["morte"]) if x), "notas": r["notas"]})
    put("work", """SELECT w.id,w.titulo,w.ano,w.ano_num,w.notas,
                   (SELECT wa.author_id FROM work_agents wa WHERE wa.work_id=w.id
                    AND wa.papel='autor_principal' ORDER BY wa.ordem, wa.id LIMIT 1) AS author_id
                   FROM works w""", lambda r: {
        "nome": r["titulo"], "ano": r["ano_num"], "data": r["ano"], "author_id": r["author_id"], "notas": r["notas"]})
    put("periodical", "SELECT id,titulo,ano_inicio,ano_fim,ini_num,fim_num,notas FROM periodicals", lambda r: {
        "nome": r["titulo"], "ano": r["ini_num"], "fim": r["fim_num"],
        "data": " – ".join(x for x in (r["ano_inicio"], r["ano_fim"]) if x), "notas": r["notas"]})
    put("event", "SELECT id,nome,ano,ano_num,notas FROM events", lambda r: {
        "nome": r["nome"], "ano": r["ano_num"], "data": r["ano"], "notas": r["notas"]})
    put("media", "SELECT id,nome,notas FROM media", lambda r: {"nome": r["nome"], "notas": r["notas"]})
    put("institution", "SELECT id,nome,tipo,fundacao,extincao,local,notas FROM institutions", lambda r: {"nome": r["nome"], "data": " – ".join(x for x in (r.get("fundacao"), r.get("extincao")) if x), "notas": r["notas"], "tipo_instituicao": r["tipo"], "local": r["local"]})
    # Objeto / manifestação é a aparição concreta de uma obra (edição, manuscrito,
    # versão ou publicação), e não uma nova obra intelectual. Não tem ficha autônoma:
    # suas notas e metadados são editados na ficha da obra.
    ids_obras = E.ids_do_perfil(c, pid, "work")
    for r in lista(c, """SELECT m.id,m.work_id,m.tipo_aparicao,m.ano_edicao,m.ed_num,m.notas,m.fonte,m.referencia,
                               m.periodical_id,m.container_work_id,m.container_manifestation_id,m.issue_id,m.caminho,m.formato,w.titulo AS obra,
                               p.titulo AS periodico,cw.titulo AS continente,i.volume AS issue_volume,i.numero AS issue_number,
                               i.data AS issue_date,i.titulo AS issue_title
                        FROM manifestations m JOIN works w ON w.id=m.work_id
                        LEFT JOIN periodicals p ON p.id=m.periodical_id
                        LEFT JOIN works cw ON cw.id=m.container_work_id
                        LEFT JOIN periodical_issues i ON i.id=m.issue_id
                        ORDER BY m.id"""):
        if ids_obras is not None and r["work_id"] not in ids_obras: continue
        titulo_contexto = r["periodico"] or r["continente"]
        rotulo = r["tipo_aparicao"] or "manifestação"
        nome = f"{r['obra']} · {rotulo}" + (f" · {titulo_contexto}" if titulo_contexto else "")
        nos[_chave("manifestation", r["id"])] = {
            "id": _chave("manifestation", r["id"]), "tipo": "manifestation", "ref_id": r["id"],
            "nome": nome, "ano": r["ed_num"], "data": r["ano_edicao"], "notas": r["notas"],
            "fonte": r["fonte"], "referencia": r["referencia"], "tipo_aparicao": rotulo,
            "caminho": r["caminho"], "formato": r["formato"], "work_id": r["work_id"],
            "obra_titulo": r["obra"], "periodical_id": r["periodical_id"],
            "periodico_titulo": r["periodico"], "container_work_id": r["container_work_id"],
            "obra_continente_titulo": r["continente"], "issue_id": r["issue_id"],
            "container_manifestation_id": r["container_manifestation_id"], "issue_volume": r["issue_volume"],
            "issue_number": r["issue_number"], "issue_date": r["issue_date"], "issue_title": r["issue_title"]}
    issues = {n.get("issue_id") for n in nos.values() if n.get("tipo") == "manifestation" and n.get("issue_id")}
    if issues:
        for r in lista(c, "SELECT i.*,p.titulo AS periodico FROM periodical_issues i JOIN periodicals p ON p.id=i.periodical_id ORDER BY i.id"):
            if r["id"] not in issues: continue
            partes = [r.get("periodico") or "periódico"]
            if r.get("volume"): partes.append(f"v. {r['volume']}")
            if r.get("numero"): partes.append(f"n. {r['numero']}")
            if r.get("data"): partes.append(r["data"])
            if r.get("titulo"): partes.append(r["titulo"])
            nos[_chave("issue", r["id"])] = {"id": _chave("issue", r["id"]), "tipo": "issue", "ref_id": r["id"],
                "nome": " · ".join(partes), "ano": r.get("data_num"), "data": r.get("data"),
                "periodical_id": r["periodical_id"], "periodico_titulo": r.get("periodico"),
                "volume": r.get("volume"), "numero": r.get("numero"), "referencia": r.get("referencia"), "notas": r.get("notas")}
    return nos

def _autores_de(no, nos, coautores):
    """Conjunto de chaves de autores ligados a um nó (autor -> ele mesmo; obra -> autor principal + coautores)."""
    if no["tipo"] == "author": return {no["id"]}
    if no["tipo"] == "work":
        s = set(coautores.get(no["id"], ()))
        if no.get("author_id") and _chave("author", no["author_id"]) in nos: s.add(_chave("author", no["author_id"]))
        return s
    return set()

def construir(c, pid=None, tipos=None, familias=None, camadas=(), projecao="nenhuma", foco=None, profundidade=2):
    # Na vista crua, objetos/manifestações entram como nós distintos; mídia fica optativa.
    # Mídia descreve a obra (ou o suporte) e fica como nó opcional, não como
    # concentrador automático que polui o grafo principal.
    tipos_explicitos = tipos is not None
    tipos = ((set(ENTIDADES) - {"media"}) | {"manifestation", "issue"}) if tipos is None else set(tipos)
    nos = _carregar(c, pid); arestas = []
    # --- relações guardadas
    # Um vínculo legado obra→periódico só aparece no grafo se não houver já uma
    # manifestação canônica que represente a mesma publicação. Isso evita duplicar
    # a mesma informação em duas camadas do modelo.
    pares_manifestados = {(n.get("work_id"), n.get("periodical_id")) for n in nos.values()
                          if n.get("tipo") == "manifestation" and n.get("periodical_id")}
    for r in lista(c, "SELECT * FROM relations"):
        o, d = _chave(r["origem_tipo"], r["origem_id"]), _chave(r["destino_tipo"], r["destino_id"])
        if o not in nos or d not in nos: continue
        if r["tipo"] == "publicado_em" and r["origem_tipo"] == "work" and r["destino_tipo"] == "periodical" and (r["origem_id"], r["destino_id"]) in pares_manifestados:
            continue
        v = RELACOES.get(r["tipo"], {"familia": "livre", "simetrica": False})
        via = _chave(r["via_tipo"], r["via_id"]) if r.get("via_tipo") else None
        arestas.append({"id": f"r{r['id']}", "origem": o, "destino": d, "tipo": r["tipo"], "familia": v["familia"],
                        "rotulo": rotulo_de(r, True), "simetrica": v["simetrica"], "ano": r.get("ano"),
                        "nota": r.get("notas"), "fonte": r.get("fonte"),
                        "via": ({"id": via, "nome": nos[via]["nome"], "tipo": r["via_tipo"]} if via in nos else None),
                        "derivada": False, "estatuto": r.get("estatuto") or "documentada"})
    # --- participações de agentes em obras: fonte canônica work_agents
    papel_tipo = {"autor_principal": "autor_de", "coautor": "autor_de", "tradutor": "traduziu",
                  "organizador": "organizou", "ilustrador": "ilustrou", "prefaciador": "prefaciou",
                  "entrevistador": "entrevistou", "entrevistado": "entrevistado_em"}
    for r in lista(c, """SELECT wa.*,a.nome AS agente FROM work_agents wa JOIN authors a ON a.id=wa.author_id ORDER BY wa.id"""):
        ak, wk = _chave("author", r["author_id"]), _chave("work", r["work_id"])
        if ak not in nos or wk not in nos or r["papel"] not in papel_tipo: continue
        rel_tipo = papel_tipo[r["papel"]]
        vv = RELACOES.get(rel_tipo, {"familia": "autoria", "simetrica": False})
        principal = r["papel"] in ("autor_principal", "coautor")
        # Um tipo visual estável para autoria, com o papel concreto no atributo.
        # Isso mantém compatibilidade com filtros e símbolos já utilizados pelo rizoma.
        tipo_aresta = "autoria" if principal else rel_tipo
        rotulo_aresta = ("é autor(a) principal de" if r["papel"] == "autor_principal"
                         else ("é coautor(a) de" if r["papel"] == "coautor" else vv["direta"]))
        arestas.append({"id": f"wa:{r['id']}", "origem": ak, "destino": wk,
                        "tipo": tipo_aresta, "familia": "autoria", "rotulo": rotulo_aresta,
                        "simetrica": False, "ano": r.get("ano"), "nota": r.get("notas"), "fonte": r.get("fonte"),
                        "papel": r["papel"], "derivada": "estrutural" if principal else False})
    # Papéis de agente atribuídos à manifestação específica (p.ex. tradutor desta edição).
    for r in lista(c, """SELECT ma.*,a.nome AS agente,m.work_id,m.tipo_aparicao,m.ano_edicao,m.referencia
                              FROM manifestation_agents ma JOIN authors a ON a.id=ma.author_id
                              JOIN manifestations m ON m.id=ma.manifestation_id ORDER BY ma.id"""):
        ak, mk = _chave("author", r["author_id"]), _chave("manifestation", r["manifestation_id"])
        if ak not in nos or mk not in nos: continue
        rel = {"tradutor": "traduziu", "organizador": "organizou", "ilustrador": "ilustrou",
               "prefaciador": "prefaciou", "entrevistador": "entrevistou", "entrevistado": "entrevistado_em"}.get(r["papel"], r["papel"])
        arestas.append({"id": f"ma:{r['id']}", "origem": ak, "destino": mk, "tipo": rel,
                        "familia": "autoria", "rotulo": f"{r['papel']} nesta manifestação", "simetrica": False,
                        "papel": r["papel"], "ano": r.get("ano_edicao"), "nota": r.get("notas"),
                        "fonte": r.get("fonte"), "derivada": False})
    # A obra intelectual e cada aparição concreta são nós diferentes, ligados
    # explicitamente. A manifestação também pode apontar para o periódico em que
    # apareceu e/ou para a obra-volume que a contém; isso não duplica a obra.
    for n in list(nos.values()):
        if n["tipo"] != "manifestation": continue
        wid = n.get("work_id")
        work_key = _chave("work", wid) if wid else None
        if work_key in nos:
            arestas.append({"id": f"am{n['ref_id']}", "origem": work_key, "destino": n["id"],
                            "tipo": "manifestacao_de", "familia": "publicacao",
                            "rotulo": "tem esta manifestação", "simetrica": False, "derivada": "estrutural"})
        issue_id = n.get("issue_id")
        issue_key = _chave("issue", issue_id) if issue_id else None
        pid_per = n.get("periodical_id")
        per_key = _chave("periodical", pid_per) if pid_per else None
        if issue_key in nos and (not tipos_explicitos or "issue" in tipos):
            arestas.append({"id": f"mi:{n['ref_id']}", "origem": n["id"], "destino": issue_key,
                            "tipo": "publicada_no_fasciculo", "familia": "publicacao",
                            "rotulo": "apareceu neste fascículo", "simetrica": False, "derivada": "estrutural"})
        elif per_key in nos:
            arestas.append({"id": f"ap{n['ref_id']}", "origem": n["id"], "destino": per_key,
                            "tipo": "apareceu_em", "familia": "publicacao",
                            "rotulo": "apareceu em (fascículo não identificado)", "simetrica": False, "derivada": "estrutural"})
        if issue_key in nos and per_key in nos:
            arestas.append({"id": f"ip:{issue_id}", "origem": issue_key, "destino": per_key,
                            "tipo": "fasciculo_de", "familia": "publicacao",
                            "rotulo": "fascículo de", "simetrica": False, "derivada": "estrutural"})
        cid = n.get("container_work_id")
        container_key = _chave("work", cid) if cid else None
        if container_key in nos:
            arestas.append({"id": f"ac{n['ref_id']}", "origem": n["id"], "destino": container_key,
                            "tipo": "incluida_em", "familia": "publicacao",
                            "rotulo": "associada à obra continente (edição específica não indicada)", "simetrica": False, "derivada": "estrutural"})
        cmid = n.get("container_manifestation_id")
        cmkey = _chave("manifestation", cmid) if cmid else None
        if cmkey in nos:
            arestas.append({"id": f"cm:{n['ref_id']}", "origem": n["id"], "destino": cmkey,
                            "tipo": "contida_na_manifestacao", "familia": "publicacao",
                            "rotulo": "contida nesta edição concreta", "simetrica": False, "derivada": "estrutural"})
    for r in lista(c, "SELECT wm.work_id w, wm.media_id m, md.nome FROM work_media wm JOIN media md ON md.id=wm.media_id"):
        o, d = _chave("work", r["w"]), _chave("media", r["m"])
        if o in nos and d in nos:
            arestas.append({"id": f"m{r['w']}-{r['m']}", "origem": o, "destino": d, "tipo": "midia", "familia": "intermidial", "rotulo": "está em mídia: " + r["nome"],
                            "simetrica": False, "derivada": "estrutural"})
    coautores = defaultdict(set)
    for a in arestas:
        if a.get("familia") == "autoria" and a.get("papel") in ("autor_principal", "coautor"):
            coautores[a["destino"]].add(a["origem"])

    # --- projeções
    if projecao == "autores": nos, arestas = _projetar_autores(nos, arestas, coautores)
    elif projecao == "obras": nos, arestas = _projetar_obras(nos, arestas)
    else:
        nos = {k: v for k, v in nos.items() if v["tipo"] in tipos}
        arestas = [a for a in arestas if a["origem"] in nos and a["destino"] in nos]
        if familias is not None: arestas = [a for a in arestas if a["familia"] in familias]

    if projecao != "nenhuma" and familias is not None:
        pass   # famílias filtram só o grafo "cru"; a projeção mostra todas as mediações

    # --- camadas calculadas
    if "contemporaneo" in camadas: arestas += _contemporaneos([n for n in nos.values() if n["tipo"] == "author"])
    if "tags" in camadas: nos, arestas = _hubs(c, nos, arestas, "tag", "tag", """
        SELECT et.entity_tipo AS t, et.entity_id AS i, g.id AS hid, g.nome AS hn FROM entity_tags et JOIN tags g ON g.id=et.tag_id""")
    if "lugares" in camadas: nos, arestas = _hubs(c, nos, arestas, "lugar", "lugar", """
        SELECT ep.entity_tipo AS t, ep.entity_id AS i, p.id AS hid, p.nome AS hn, ep.papel FROM entity_places ep
        JOIN places p ON p.id=ep.place_id""")

    # Estatuto epistemológico uniforme: a interface não precisa inferir pelo estilo
    # se uma aresta é documental, estrutural ou calculada.
    for a in arestas:
        if a.get("estatuto"):
            continue
        if a.get("derivada") == "estrutural": a["estatuto"] = "estrutural"
        elif a.get("derivada") in ("calculada", "projecao"): a["estatuto"] = "derivada"
        else: a["estatuto"] = "documentada"
    if foco and foco in nos: nos, arestas = _foco(nos, arestas, foco, max(1, min(int(profundidade), 6)))
    grau = defaultdict(int)
    for a in arestas: grau[a["origem"]] += 1; grau[a["destino"]] += 1
    for n in nos.values(): n["grau"] = grau[n["id"]]
    return {"nos": list(nos.values()), "arestas": arestas, "projecao": projecao}

# ------------------------------------------------------------------ projeções
def _projetar_autores(nos, arestas, coautores):
    """Projeta caminhos entre autores sem converter contexto bibliográfico em vínculo pessoal.

    Arestas da projeção são agregadores; cada mediação conserva a direção original,
    a entidade que a sustenta e seu estatuto epistemológico. Um periódico só cria
    coocorrência quando há fascículo identificado em comum — nunca apenas por duas
    pessoas terem publicado na mesma revista em algum momento.
    """
    pares = defaultdict(list)

    def liga(a, b, med):
        if not a or not b or a == b:
            return
        par = tuple(sorted((a, b)))
        med.setdefault("origem_autor", a)
        med.setdefault("destino_autor", b)
        med.setdefault("direcional", a != b)
        pares[par].append(med)

    # 1) Relações explicitamente documentadas. Só projetar autor↔autor ou obra↔obra.
    # Relações mistas (autor↔obra/periódico) têm significado próprio e não autorizam
    # inferir uma relação entre o agente e todos os autores associados ao outro nó.
    for e in arestas:
        if e.get("derivada") == "estrutural":
            continue
        o, d = nos.get(e["origem"]), nos.get(e["destino"])
        if not o or not d:
            continue
        evid = {"ocorrencia_id": e.get("id"), "ano": e.get("ano"),
                "fonte": e.get("fonte"), "nota": e.get("nota") or e.get("notas")}
        if o["tipo"] == d["tipo"] == "author":
            # Relação entre pessoas explicitamente cadastrada: não a inventamos,
            # apenas a projetamos preservando o tipo e a direção.
            liga(o["id"], d["id"], {"como": "direta", "relacao": e.get("rotulo") or e["tipo"],
                  "tipo": e["tipo"], "entidade": None, "estatuto": "documentada", **evid})
        elif o["tipo"] == d["tipo"] == "work":
            # Só relações semânticas entre textos geram caminho autoral. Parte/todo
            # e outros vínculos estruturais não significam diálogo entre autores.
            if e.get("familia") not in {"transtextual", "intermidial", "livre", "discurso"}:
                continue
            autores_o = sorted(_autores_de(o, nos, coautores))
            autores_d = sorted(_autores_de(d, nos, coautores))
            for a in autores_o:
                for b in autores_d:
                    liga(a, b, {"como": "obra", "relacao": e.get("rotulo") or e["tipo"],
                          "tipo": e["tipo"], "entidade": {
                              "origem": {"id": o["id"], "nome": o["nome"], "tipo": "work"},
                              "destino": {"id": d["id"], "nome": d["nome"], "tipo": "work"}},
                          "estatuto": "derivada_de_relacao_entre_obras", **evid})

    # 2) Coautoria: mediação documental pela mesma obra, não relação social presumida.
    for wk, aus in coautores.items():
        lista_aus = sorted(aus)
        if len(lista_aus) < 2:
            continue
        work_node = nos.get(wk)
        for i in range(len(lista_aus)):
            for j in range(i + 1, len(lista_aus)):
                a, b = lista_aus[i], lista_aus[j]
                liga(a, b, {"como": "obra", "relacao": "coautoria na mesma obra",
                      "tipo": "coautoria", "entidade": ({"id": wk, "nome": work_node["nome"], "tipo": "work"} if work_node else None),
                      "estatuto": "derivada_de_participacoes_de_autoria"})

    # 3) Participação em evento: só participantes explicitamente vinculados ao
    # mesmo evento (ou obras explicitamente apresentadas nele) geram coocorrência.
    # Arestas de outros tipos para eventos não são reinterpretadas como presença.
    por_evento = defaultdict(set)
    for e in arestas:
        o, d = nos.get(e["origem"]), nos.get(e["destino"])
        if not o or not d or e.get("familia") != "encontro":
            continue
        if o["tipo"] == "author" and d["tipo"] == "event" and e.get("tipo") == "participou":
            por_evento[d["id"]].add(o["id"])
        elif o["tipo"] == "work" and d["tipo"] == "event" and e.get("tipo") == "apresentada_em":
            por_evento[d["id"]].update(_autores_de(o, nos, coautores))
        elif d["tipo"] == "author" and o["tipo"] == "event" and e.get("tipo") == "participou":
            por_evento[o["id"]].add(d["id"])
    for ev, autores in por_evento.items():
        lista_ev = sorted(autores)
        for i in range(len(lista_ev)):
            for j in range(i + 1, len(lista_ev)):
                a, b = lista_ev[i], lista_ev[j]
                liga(a, b, {"como": "event", "relacao": "participação documentada no mesmo evento (não implica vínculo pessoal)",
                      "tipo": "coocorrencia_evento", "entidade": {"id": ev, "nome": nos[ev]["nome"], "tipo": "event"},
                      "estatuto": "coocorrencia_documental; nao implica vinculo pessoal"})

    # 4) Papéis em uma manifestação: o papel é documentado; a aproximação com
    # autores da obra é contextual e limitada àquela edição, sem alegação pessoal.
    for e in arestas:
        if not str(e.get("id", "")).startswith("ma:"):
            continue
        ak, mk = e["origem"], e["destino"]
        manifest = nos.get(mk)
        if not manifest:
            continue
        work = nos.get(_chave("work", manifest.get("work_id")))
        if not work:
            continue
        for outro in sorted(_autores_de(work, nos, coautores)):
            if outro == ak:
                continue
            liga(ak, outro, {"como": "manifestacao", "relacao": f"papel documentado na manifestação: {e.get('papel') or e.get('tipo')}",
                  "tipo": "participacao_manifestacao", "entidade": {
                      "id": work["id"], "nome": work["nome"], "tipo": "work",
                      "manifestacao_id": manifest["ref_id"], "manifestacao_nome": manifest["nome"],
                      "referencia": manifest.get("referencia")},
                  "fonte": e.get("fonte"), "nota": e.get("nota"),
                  "estatuto": "contexto_de_producao; nao implica vinculo pessoal"})

    # 5) Coocorrência editorial: exige fascículo identificado em comum.
    # Publicar no mesmo periódico em anos/números diferentes NÃO cria aresta.
    por_fasciculo = defaultdict(set)
    for n in nos.values():
        if n.get("tipo") != "manifestation" or not n.get("issue_id"):
            continue
        wk = _chave("work", n.get("work_id"))
        ik = _chave("issue", n.get("issue_id"))
        if wk not in nos or ik not in nos:
            continue
        autores = _autores_de(nos[wk], nos, coautores)
        for ma in arestas:
            if ma.get("destino") == n["id"] and str(ma.get("id", "")).startswith("ma:"):
                autores.add(ma["origem"])
        for autor in autores:
            por_fasciculo[ik].add((autor, n["id"], wk))

    for ik, creditos in por_fasciculo.items():
        autores = sorted({x[0] for x in creditos})
        if len(autores) < 2:
            continue
        issue = nos[ik]
        for i in range(len(autores)):
            for j in range(i + 1, len(autores)):
                a, b = autores[i], autores[j]
                creditos_a = [x for x in creditos if x[0] == a]
                creditos_b = [x for x in creditos if x[0] == b]
                for ca in creditos_a:
                    for cb in creditos_b:
                        if ca[2] == cb[2]:
                            continue
                        liga(a, b, {"como": "issue", "relacao": "coocorrência no mesmo fascículo (não implica vínculo pessoal)",
                              "tipo": "coaparece_no_fasciculo", "entidade": {
                                  "id": ik, "nome": issue["nome"], "tipo": "issue"},
                              "manifestacao_a": ca[1], "manifestacao_b": cb[1],
                              "estatuto": "coocorrencia_documental; nao implica vinculo pessoal"})

    novos = {k: v for k, v in nos.items() if v["tipo"] == "author"}
    saida = []
    for (a, b), meds in sorted(pares.items()):
        vistas, unicas = set(), []
        for m in meds:
            ent = m.get("entidade") or {}
            chave = (m.get("estatuto"), m.get("tipo"), m.get("origem_autor"), m.get("destino_autor"),
                     ent.get("id"), (ent.get("origem") or {}).get("id"), (ent.get("destino") or {}).get("id"),
                     m.get("ocorrencia_id"), m.get("manifestacao_a"), m.get("manifestacao_b"),
                     m.get("ano"), m.get("fonte"), m.get("nota"))
            if chave not in vistas:
                vistas.add(chave); unicas.append(m)
        saida.append({"id": f"p{a}|{b}", "origem": a, "destino": b, "tipo": "mediada",
                      "familia": "projecao", "rotulo": f"{len(unicas)} mediação(ões)",
                      "simetrica": True, "derivada": "projecao", "estatuto": "projecao_analitica",
                      "mediacoes": unicas, "peso": len(unicas)})
    return novos, saida

def _projetar_obras(nos, arestas):
    novos = {k: v for k, v in nos.items() if v["tipo"] == "work"}
    saida = []
    # Apenas relações diretamente entre obras permanecem como relações explícitas.
    for e in arestas:
        if e.get("derivada") == "estrutural": continue
        o, d = nos[e["origem"]], nos[e["destino"]]
        if o["tipo"] == "work" and d["tipo"] == "work": saida.append(e)

    # Coaparição exige o mesmo fascículo identificado, não apenas o periódico.
    por_fasciculo = defaultdict(set)
    for n in nos.values():
        if n.get("tipo") == "manifestation" and n.get("issue_id"):
            wk = _chave("work", n.get("work_id"))
            ik = _chave("issue", n.get("issue_id"))
            if wk in novos and ik in nos: por_fasciculo[ik].add(wk)
    for ik, works in por_fasciculo.items():
        if len(works) < 2: continue
        membros = sorted(works)
        issue = nos[ik]
        for i in range(len(membros)):
            for j in range(i + 1, len(membros)):
                a, b = membros[i], membros[j]
                saida.append({"id": f"issue:{issue['ref_id']}:{a}|{b}", "origem": a, "destino": b,
                              "tipo": "coaparece_no_fasciculo", "familia": "projecao",
                              "rotulo": f"mesmo fascículo: {issue['nome']}", "simetrica": True,
                              "derivada": "projecao", "fasciculo": issue})

    # Contenção por edição específica só é derivada quando há uma manifestation
    # concreta identificada. container_work_id é um vínculo geral, não prova qual edição.
    for n in nos.values():
        if n.get("tipo") != "manifestation" or not n.get("container_manifestation_id"): continue
        wk = _chave("work", n.get("work_id"))
        parent = nos.get(_chave("manifestation", n.get("container_manifestation_id")))
        if wk not in novos or not parent: continue
        ck = _chave("work", parent.get("work_id"))
        if ck in novos and wk != ck:
            saida.append({"id": f"container-manifestation:{n['ref_id']}", "origem": wk, "destino": ck,
                          "tipo": "contida_na_edicao", "familia": "projecao",
                          "rotulo": f"contida na edição de {parent['obra_titulo']}", "simetrica": False,
                          "derivada": "projecao", "manifestacao_id": n["ref_id"],
                          "manifestacao_continente_id": parent["ref_id"]})
    return novos, saida

# ------------------------------------------------------------------ camadas e foco
def _contemporaneos(autores, minimo=20, limite=4000):
    """Só deriva contemporaneidade quando nascimento e morte estão documentados nos dois lados.

    Não estima vidas com base numa expectativa demográfica. Datas parciais permanecem
    incertezas e não geram arestas aparentemente factuais.
    """
    vivos = []
    for a in autores:
        # ano_num é propositalmente permissivo para ordenar c. 800 a.C. ou séc. XIX.
        # Não é suficientemente preciso para declarar contemporaneidade. Exigimos
        # expressões pontuais explícitas nos dois limites da vida.
        ini = ano_preciso(a.get("nascimento_texto"))
        fim = ano_preciso(a.get("morte_texto"))
        if ini is None or fim is None or fim < ini: continue
        vivos.append((a["id"], ini, fim))
    out = []
    for i in range(len(vivos)):
        for j in range(i + 1, len(vivos)):
            sobra = min(vivos[i][2], vivos[j][2]) - max(vivos[i][1], vivos[j][1])
            if sobra >= minimo:
                out.append({"id": f"k{vivos[i][0]}|{vivos[j][0]}", "origem": vivos[i][0], "destino": vivos[j][0],
                            "tipo": "contemporaneo", "familia": "calculada", "rotulo": f"contemporâneos ({sobra} anos em comum; intervalos registrados)",
                            "simetrica": True, "derivada": "calculada"})
                if len(out) >= limite: return out
    return out

def _hubs(c, nos, arestas, tipo_hub, prefixo, sql):
    # Um nó por entidade/lugar, mesmo se a entidade tiver papéis diferentes no
    # mesmo local. Os papéis são preservados na aresta em vez de criar arestas
    # visualmente duplicadas com o mesmo ID.
    por = defaultdict(lambda: defaultdict(set)); nomes = {}
    for r in lista(c, sql):
        k = _chave(r["t"], r["i"])
        if k not in nos: continue
        papel = (r.get("papel") or "").strip()
        por[r["hid"]][k].add((papel, False))
        nomes[r["hid"]] = r["hn"]
        # Uma atribuição a uma cidade permite explorar os ancestrais, mas isso
        # é contexto territorial herdado, não uma segunda atribuição direta.
        if tipo_hub == "lugar":
            atual = c.execute("SELECT id,parent_id,nome FROM places WHERE id=?", (r["hid"],)).fetchone()
            vistos = {r["hid"]}
            while atual and atual["parent_id"] and atual["parent_id"] not in vistos:
                pai = c.execute("SELECT id,parent_id,nome FROM places WHERE id=?", (atual["parent_id"],)).fetchone()
                if not pai: break
                vistos.add(pai["id"])
                por[pai["id"]][k].add((papel, True))
                nomes[pai["id"]] = pai["nome"]
                atual = pai
    nos = dict(nos); arestas = list(arestas)
    for hid, membros in por.items():
        if tipo_hub == "tag" and len(membros) < 2: continue
        h = f"{prefixo}:{hid}"
        nos[h] = {"id": h, "tipo": tipo_hub, "ref_id": hid, "nome": nomes[hid]}
        for m, atribuicoes in membros.items():
            papéis = sorted({p for p, _ in atribuicoes if p})
            herdado = any(h for _, h in atribuicoes)
            rotulo = tipo_hub
            if papéis: rotulo += ": " + ", ".join(papéis)
            if herdado: rotulo += " (inclui hierarquia territorial)"
            arestas.append({"id": f"h{h}|{m}", "origem": m, "destino": h, "tipo": tipo_hub, "familia": "calculada",
                            "rotulo": rotulo, "simetrica": True, "derivada": "calculada",
                            "papeis_geograficos": papéis if tipo_hub == "lugar" else [],
                            "hierarquia_territorial": herdado if tipo_hub == "lugar" else False})
    return nos, arestas

def _foco(nos, arestas, foco, prof):
    viz = defaultdict(set)
    for a in arestas: viz[a["origem"]].add(a["destino"]); viz[a["destino"]].add(a["origem"])
    dist, fila = {foco: 0}, deque([foco])
    while fila:
        x = fila.popleft()
        if dist[x] >= prof: continue
        for y in viz[x]:
            if y not in dist: dist[y] = dist[x] + 1; fila.append(y)
    return ({k: v for k, v in nos.items() if k in dist},
            [a for a in arestas if a["origem"] in dist and a["destino"] in dist])
