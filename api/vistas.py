"""Representações: busca, grafo, linha do tempo, mapa, diagnóstico."""
import difflib, shutil, sys, re
from collections import defaultdict
from fastapi import APIRouter, Request
from core import config, grafo, online
from core import entidades as E
from core.db import conn, lista, js, AVISOS
from core.texto import normalizar
from core.vocab import ENTIDADES
from core.datas import ano_preciso, ano_num, parse_data_historica
from .comum import perfil_ativo
from .cadastros import _caminho_lugar, AUTOR

router = APIRouter(prefix="/api")

# ------------------------------------------------------------------ busca (em tudo, ignora o perfil)
@router.get("/busca/estado-indexacao")
def estado_indexacao_busca():
    """Expõe os limites reais da busca para não interpretar silêncio como ausência documental."""
    with conn() as c:
        anexos = c.execute("SELECT COUNT(*) FROM manifestations WHERE trim(COALESCE(caminho,''))<>''").fetchone()[0]
        pdfs = c.execute("SELECT COUNT(*) FROM manifestations WHERE lower(caminho) LIKE '%.pdf'").fetchone()[0]
    return {"busca_metadados": True, "indice_texto_integral_ativo": False,
            "anexos_com_caminho": anexos, "pdfs_anexados": pdfs,
            "ocr_automatico": False,
            "mensagem": "A busca consulta fichas, metadados, relações e proveniência; não pesquisa o texto integral dos anexos. PDFs digitalizados exigem OCR externo ou leitura manual.",
            "interpretacao": "Zero resultados significa apenas que o termo não apareceu nos campos indexados; não prova ausência na documentação."}

@router.get("/busca")
def busca(q: str, tipos: str = ""):
    """Busca entidades e evidências em metadados, relações e manifestações.

    O resultado aponta o campo correspondente, para o pesquisador saber por que
    aquela ficha foi encontrada. Não finge buscar no texto integral de PDFs.
    """
    alvo = normalizar(q)
    if len(alvo) < 2: return []
    quer = set(tipos.split(",")) & set(ENTIDADES) if tipos else set(ENTIDADES)
    # Acumula correspondências por entidade para não devolver a mesma ficha várias vezes.
    candidatos = {}
    def add(tipo, eid, nome, sub, campo, valor):
        if tipo not in quer or eid is None or nome in (None, "") or valor in (None, ""): return
        chave = (tipo, int(eid))
        x = candidatos.setdefault(chave, {"tipo": tipo, "id": int(eid), "nome": str(nome), "sub": str(sub or ""), "_campos": []})
        x["_campos"].append((campo, str(valor)))

    with conn() as c:
        for r in lista(c, "SELECT * FROM authors"):
            for f in ("nome", "variantes", "nascimento", "morte", "bio", "notas"):
                if f == "variantes":
                    for v in js(r[f]): add("author", r["id"], r["nome"], "autor", f"variante de nome", v)
                else: add("author", r["id"], r["nome"], "autor", f, r.get(f))
        for r in lista(c, f"SELECT w.*,a.nome AS autor FROM works w LEFT JOIN authors a ON a.id={AUTOR}"):
            sub = " · ".join(x for x in (r["autor"], r["ano"], r["tipo"]) if x)
            for f in ("titulo", "ano", "genero", "tipo", "notas"):
                add("work", r["id"], r["titulo"], sub, f, r.get(f))
            add("work", r["id"], r["titulo"], sub, "autor", r.get("autor"))
        for r in lista(c, "SELECT * FROM periodicals"):
            sub = " · ".join(x for x in (r.get("tipo"), r.get("issn")) if x)
            for f in ("titulo", "tipo", "issn", "ano_inicio", "ano_fim", "notas"):
                add("periodical", r["id"], r["titulo"], sub, f, r.get(f))
        for r in lista(c, "SELECT * FROM events"):
            for f in ("nome", "tipo", "ano", "notas"):
                add("event", r["id"], r["nome"], r.get("tipo") or "evento", f, r.get(f))
        for r in lista(c, "SELECT * FROM media"):
            for f in ("nome", "notas"): add("media", r["id"], r["nome"], "mídia", f, r.get(f))
        for r in lista(c, "SELECT * FROM institutions"):
            for f in ("nome", "tipo", "fundacao", "extincao", "local", "notas"): add("institution", r["id"], r["nome"], r.get("tipo") or "instituição", f, r.get(f))

        for r in lista(c, """SELECT m.*,w.titulo AS obra,p.titulo AS periodico,i.volume,i.numero,i.data AS data_fasciculo,i.titulo AS titulo_fasciculo
                               FROM manifestations m JOIN works w ON w.id=m.work_id
                               LEFT JOIN periodicals p ON p.id=m.periodical_id LEFT JOIN periodical_issues i ON i.id=m.issue_id"""):
            sub = " · ".join(x for x in (r["obra"], r["periodico"], r["ano_edicao"]) if x)
            for f in ("caminho", "formato", "editora", "ano_edicao", "idioma", "tradutor", "organizador", "notas", "local", "fonte", "tipo_aparicao", "referencia"):
                add("work", r["work_id"], r["obra"], sub, f"manifestação · {f}", r.get(f))
            for f in ("volume", "numero", "data_fasciculo", "titulo_fasciculo"):
                add("work", r["work_id"], r["obra"], sub, f"fascículo · {f}", r.get(f))
            add("periodical", r["periodical_id"], r.get("periodico"), sub, "manifestação publicada no periódico", r.get("referencia"))
        for r in lista(c, """SELECT wa.*,a.nome AS agente,w.titulo FROM work_agents wa JOIN authors a ON a.id=wa.author_id JOIN works w ON w.id=wa.work_id"""):
            add("author", r["author_id"], r["agente"], r["papel"] + " · " + r["titulo"], "papel na obra", r["titulo"] + " " + r["papel"] + " " + (r.get("notas") or "") + " " + (r.get("fonte") or ""))
            add("work", r["work_id"], r["titulo"], r["papel"] + " · " + r["agente"], "participação de agente", r["agente"] + " " + r["papel"] + " " + (r.get("notas") or "") + " " + (r.get("fonte") or ""))
        for r in lista(c, """SELECT ma.*,a.nome AS agente,m.work_id,w.titulo FROM manifestation_agents ma
                               JOIN authors a ON a.id=ma.author_id JOIN manifestations m ON m.id=ma.manifestation_id
                               JOIN works w ON w.id=m.work_id"""):
            add("author", r["author_id"], r["agente"], r["papel"] + " · " + r["titulo"], "papel na manifestação", r["titulo"] + " " + r["papel"] + " " + (r.get("notas") or ""))
            add("work", r["work_id"], r["titulo"], r["papel"] + " · " + r["agente"], "agente da manifestação", r["agente"] + " " + r["papel"])
        for r in lista(c, """SELECT et.entity_tipo,et.entity_id,t.nome FROM entity_tags et JOIN tags t ON t.id=et.tag_id"""):
            if r["entity_tipo"] == "author": n = c.execute("SELECT nome FROM authors WHERE id=?", (r["entity_id"],)).fetchone()
            elif r["entity_tipo"] == "work": n = c.execute("SELECT titulo AS nome FROM works WHERE id=?", (r["entity_id"],)).fetchone()
            elif r["entity_tipo"] == "periodical": n = c.execute("SELECT titulo AS nome FROM periodicals WHERE id=?", (r["entity_id"],)).fetchone()
            elif r["entity_tipo"] == "event": n = c.execute("SELECT nome FROM events WHERE id=?", (r["entity_id"],)).fetchone()
            else: n = c.execute("SELECT nome FROM media WHERE id=?", (r["entity_id"],)).fetchone()
            if n: add(r["entity_tipo"], r["entity_id"], n["nome"], "tag: " + r["nome"], "tag", r["nome"])

        # Lugar é contexto pesquisável; a busca retorna as fichas ligadas a ele
        # e indica o papel geográfico, em vez de tentar abrir uma ficha de lugar
        # que a navegação de entidades ainda não trata como tipo comum.
        for p in lista(c, "SELECT id,nome,tipo,contexto,notas FROM places"):
            valores = [p.get("nome"), p.get("tipo"), p.get("contexto"), p.get("notas")]
            if not any(alvo in normalizar(v) for v in valores if v): continue
            trecho = " · ".join(str(v) for v in valores[:3] if v)
            for ep in lista(c, "SELECT entity_tipo,entity_id,papel FROM entity_places WHERE place_id=?", (p["id"],)):
                try: nome = E.nome_de(c, ep["entity_tipo"], ep["entity_id"])
                except Exception: nome = None
                papel = ep.get("papel") or "associação geográfica"
                add(ep["entity_tipo"], ep["entity_id"], nome, f"lugar: {p['nome']} · {papel}", "lugar / atribuição geográfica", trecho)

        # Fascículos não devem ficar invisíveis só porque ainda não há artigo
        # ligado a eles. Volume, número, título e referência são dados do periódico.
        for i in lista(c, """SELECT i.*,p.titulo AS periodico FROM periodical_issues i
                              JOIN periodicals p ON p.id=i.periodical_id"""):
            valores = [f"v. {i['volume']}" if i.get("volume") else None,
                       f"n. {i['numero']}" if i.get("numero") else None,
                       i.get("data"), i.get("titulo"), i.get("referencia"), i.get("notas")]
            sub = " · ".join(x for x in [i.get("periodico"), *valores[:4]] if x)
            for campo, valor in zip(("volume", "número", "data", "título", "referência", "notas"), valores):
                add("periodical", i["periodical_id"], i["periodico"], sub, f"fascículo / {campo}", valor)
        for r in lista(c, "SELECT * FROM relations"):
            # Ao localizar evidência de relação, retornam-se os dois participantes,
            # independentemente de seu tipo; nomes são resolvidos pelo catálogo comum.
            evid = " ".join(str(r.get(k) or "") for k in ("tipo", "rotulo", "notas", "fonte", "ano"))
            if alvo not in normalizar(evid): continue
            for tipo_ent, eid in ((r["origem_tipo"], r["origem_id"]), (r["destino_tipo"], r["destino_id"])):
                try: nome = E.nome_de(c, tipo_ent, eid)
                except Exception: nome = None
                if tipo_ent in quer and nome:
                    add(tipo_ent, eid, nome, f"relação: {r['tipo']}", "relação / evidência", evid)

    out = []
    for x in candidatos.values():
        ocorrencias = [(f, v) for f, v in x.pop("_campos") if alvo in normalizar(v)]
        if not ocorrencias: continue
        # correspondência literal tem prioridade; a busca aproximada só opera no nome da entidade.
        sc = 1.0 if any(alvo in normalizar(v) for _, v in ocorrencias) else difflib.SequenceMatcher(None, alvo, normalizar(x["nome"])).ratio()
        if sc < .62: continue
        campo, valor = min(ocorrencias, key=lambda pair: (0 if pair[0] == "titulo" or pair[0] == "nome" else 1, len(pair[1])))
        out.append({**x, "score": round(sc, 2), "campo": campo, "trecho": valor[:220]})
    return sorted(out, key=lambda x: (-x["score"], normalizar(x["nome"]), x["tipo"]))[:50]

# ------------------------------------------------------------------ grafo
@router.get("/grafo")
def api_grafo(request: Request, tipos: str = "", familias: str = "", camadas: str = "", projecao: str = "nenhuma",
              foco: str = "", profundidade: int = 2):
    with conn() as c:
        return grafo.construir(c, perfil_ativo(request), tipos=tipos.split(",") if tipos else None,
                               familias=set(familias.split(",")) if familias else None,
                               camadas=set(camadas.split(",")) if camadas else (), projecao=projecao,
                               foco=foco or None, profundidade=profundidade)

# ------------------------------------------------------------------ linha do tempo
@router.get("/timeline")
def timeline(request: Request):
    pid = perfil_ativo(request)
    with conn() as c:
        def filtrar(tipo, rows): ids = E.ids_do_perfil(c, pid, tipo); return [r for r in rows if ids is None or r["id"] in ids]
        autores = filtrar("author", [dict(r, nascimento_epistemico=parse_data_historica(r.get("nascimento")), morte_epistemica=parse_data_historica(r.get("morte"))) for r in lista(c, "SELECT id,nome,nascimento,morte,nasc_num,morte_num FROM authors WHERE nasc_num IS NOT NULL OR morte_num IS NOT NULL")])
        obras = filtrar("work", [dict(r, data_epistemica=parse_data_historica(r.get("ano"))) for r in lista(c, f"""SELECT w.id,w.titulo AS nome,w.ano,w.ano_num AS num,a.nome AS autor FROM works w
                                            LEFT JOIN authors a ON a.id={AUTOR} WHERE w.ano_num IS NOT NULL""")])
        per = filtrar("periodical", [dict(r, inicio_epistemico=parse_data_historica(r.get("ano_inicio")), fim_epistemico=parse_data_historica(r.get("ano_fim"))) for r in lista(c, "SELECT id,titulo AS nome,ano_inicio,ano_fim,ini_num,fim_num FROM periodicals WHERE ini_num IS NOT NULL OR fim_num IS NOT NULL")])
        ev = filtrar("event", [dict(r, data_epistemica=parse_data_historica(r.get("ano"))) for r in lista(c, "SELECT id,nome,ano,ano_num AS num FROM events WHERE ano_num IS NOT NULL")])
        instituicoes = filtrar("institution", [
            {"id": r["id"], "nome": r["nome"], "fundacao": r.get("fundacao"), "extincao": r.get("extincao"),
             "ini_num": ano_num(r.get("fundacao")), "fim_num": ano_num(r.get("extincao")), "inicio_epistemico": parse_data_historica(r.get("fundacao")), "fim_epistemico": parse_data_historica(r.get("extincao"))}
            for r in lista(c, "SELECT id,nome,fundacao,extincao FROM institutions")
            if ano_num(r.get("fundacao")) is not None or ano_num(r.get("extincao")) is not None
        ])
        ids_obras = E.ids_do_perfil(c, pid, "work")
        edicoes = [r for r in lista(c, """SELECT m.id AS manifestation_id,m.work_id,w.titulo AS nome,
                                  COALESCE(i.data,m.ano_edicao) AS ano,COALESCE(i.data_num,m.ed_num) AS num,
                                  m.editora,m.tipo_aparicao,m.referencia,m.fonte,m.periodical_id,p.titulo AS periodico,
                                  m.issue_id,i.volume,i.numero,i.titulo AS fasciculo_titulo,w.ano_num AS ano_obra
                                  FROM manifestations m JOIN works w ON w.id=m.work_id
                                  LEFT JOIN periodicals p ON p.id=m.periodical_id
                                  LEFT JOIN periodical_issues i ON i.id=m.issue_id
                                  WHERE COALESCE(i.data_num,m.ed_num) IS NOT NULL""")
                   if ids_obras is None or r["work_id"] in ids_obras]
        for e in edicoes:
            e["data_epistemica"] = parse_data_historica(e.get("ano"))
        total = {t: c.execute(f"SELECT COUNT(*) FROM {E.ENT[t]['tabela']}").fetchone()[0] for t in ENTIDADES}
    return {"autores": autores, "obras": obras, "periodicos": per, "eventos": ev, "instituicoes": instituicoes, "edicoes": edicoes,
            "com_data": {"author": len(autores), "work": len(obras), "periodical": len(per), "event": len(ev), "institution": len(instituicoes)}, "total": total}

# ------------------------------------------------------------------ mapa
@router.get("/mapa")
def mapa(request: Request, todos: int = 0, papel: str = ""):
    """Mostra lugar principal por padrão; todos=1 expõe atribuições de papéis geográficos distintos."""
    pid = perfil_ativo(request); pontos = {}; sem = defaultdict(int)
    with conn() as c:
        for tipo in ("author", "work", "periodical", "event", "institution"):
            ids = E.ids_do_perfil(c, pid, tipo)
            for r in lista(c, """SELECT ep.entity_id AS id, p.id AS place_id, p.nome AS lugar, p.lat, p.lon, p.tipo, p.contexto, p.parent_id, ep.papel FROM entity_places ep
                                 JOIN places p ON p.id=ep.place_id WHERE ep.entity_tipo=?
                                 AND (?='' OR ep.papel=?)
                                 AND (
                                   ?=1
                                   OR (?='' AND ep.rowid=(SELECT x.rowid FROM entity_places x
                                      WHERE x.entity_tipo=ep.entity_tipo AND x.entity_id=ep.entity_id
                                      ORDER BY x.ordem,x.papel,x.place_id LIMIT 1))
                                   OR (?<>'' AND ep.rowid=(SELECT x.rowid FROM entity_places x
                                      WHERE x.entity_tipo=ep.entity_tipo AND x.entity_id=ep.entity_id AND x.papel=?
                                      ORDER BY x.ordem,x.place_id LIMIT 1))
                                 ) ORDER BY ep.ordem,p.nome""",
                             (tipo, papel, papel, int(bool(todos)), papel, papel, papel)):
                if ids is not None and r["id"] not in ids: continue
                # Se o lugar específico não tiver coordenadas, usar o primeiro
                # ancestral geográfico que as tenha, sem perder o lugar atribuído.
                loc = {"id": r["place_id"], "nome": r["lugar"], "lat": r["lat"], "lon": r["lon"], "tipo": r["tipo"], "contexto": r["contexto"], "parent_id": r["parent_id"]}; atribuido = r["lugar"]; cursor = r["place_id"]; vistos = set()
                while (loc["lat"] is None or loc["lon"] is None) and cursor and cursor not in vistos:
                    vistos.add(cursor)
                    if not loc["parent_id"]: break
                    cursor = loc["parent_id"]
                    anc = c.execute("SELECT id,nome,lat,lon,tipo,contexto,parent_id FROM places WHERE id=?", (cursor,)).fetchone()
                    if anc: loc.update(dict(anc))
                if loc["lat"] is None or loc["lon"] is None:
                    sem[(r["place_id"], r["lugar"])] += 1; continue
                tags = [t["nome"] for t in c.execute("SELECT t.nome FROM tags t JOIN entity_tags et ON et.tag_id=t.id WHERE et.entity_tipo=? AND et.entity_id=?", (tipo, r["id"]))]
                mapa_id = loc["id"]
                pt = pontos.setdefault(mapa_id, {"place_id": mapa_id, "nome": loc["nome"], "tipo": loc["tipo"], "contexto": loc["contexto"], "lat": loc["lat"], "lon": loc["lon"], "itens": [], "lugares_atribuidos": []})
                if not any(x["place_id"] == r["place_id"] for x in pt["lugares_atribuidos"]):
                    pt["lugares_atribuidos"].append({"place_id": r["place_id"], "nome": atribuido, "caminho": _caminho_lugar(c, r["place_id"])})
                pt["itens"].append({"tipo": tipo, "id": r["id"], "nome": E.nome_de(c, tipo, r["id"]), "lugar_atribuido": atribuido, "tags": tags, "papel": r.get("papel") or None})
        for ponto in pontos.values():
            ponto["caminho"] = _caminho_lugar(c, ponto["place_id"])
        # O mapa também é um índice do catálogo geográfico canônico: lugares
        # cadastrados sem entidade associada continuam visíveis e editáveis.
        for loc in lista(c, "SELECT id,nome,lat,lon,tipo,contexto,parent_id FROM places ORDER BY nome"):
            if loc["lat"] is None or loc["lon"] is None: continue
            pt = pontos.setdefault(loc["id"], {"place_id": loc["id"], "nome": loc["nome"], "tipo": loc["tipo"], "contexto": loc["contexto"], "lat": loc["lat"], "lon": loc["lon"], "itens": [], "lugares_atribuidos": []})
            pt["nome"] = loc["nome"]; pt["tipo"] = loc["tipo"] or pt.get("tipo"); pt["contexto"] = loc["contexto"] or pt.get("contexto")
            pt["caminho"] = _caminho_lugar(c, loc["id"])
        todas = [t["nome"] for t in c.execute("SELECT nome FROM tags ORDER BY nome")]
        catalogo_sem_coord = [dict(r) for r in c.execute("SELECT id AS place_id,nome,tipo,contexto FROM places WHERE lat IS NULL OR lon IS NULL ORDER BY nome")]
    return {"pontos": list(pontos.values()), "sem_coordenada": [{"place_id": k[0], "nome": k[1], "n": v} for k, v in sem.items()], "lugares_sem_coordenada": catalogo_sem_coord, "tags": todas}

# ------------------------------------------------------------------ diagnóstico
@router.get("/diagnostico")
def diagnostico():
    with conn() as c:
        cont = {t: c.execute(f"SELECT COUNT(*) FROM {E.ENT[t]['tabela']}").fetchone()[0] for t in ENTIDADES}
        cont["relations"] = c.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        cont["manifestations"] = c.execute("SELECT COUNT(*) FROM manifestations").fetchone()[0]
        cont["profiles"] = c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        # Auditoria documental/temporal. É diagnóstica: nunca altera valores originais.
        alertas_temporais = []
        periodicos = {r["id"]: dict(r) for r in c.execute("SELECT id,titulo,ano_inicio,ano_fim,ini_num,fim_num,notas FROM periodicals")}

        def alerta(nivel, identificador, tipo_ocorrencia, periodico, ano_texto=None, fonte=None, **extra):
            p = periodicos.get(periodico) if periodico is not None else None
            titulo = p["titulo"] if p else None
            alertas_temporais.append({"nivel": nivel, "periodico_id": periodico, "periodico": titulo,
                "identificador": identificador, "ano_ocorrencia": ano_texto,
                "ano_inicio": p.get("ano_inicio") if p else None, "ano_fim": p.get("ano_fim") if p else None,
                "tipo_ocorrencia": tipo_ocorrencia, "fonte": fonte, **extra})

        def auditar_ocorrencia(pt, ano_texto, ano, fonte, identificador, tipo_ocorrencia):
            if pt not in periodicos:
                return
            p = periodicos[pt]
            ano_pontual = ano_preciso(ano_texto) if ano_texto else None
            if ano is None and ano_pontual is not None:
                alerta("data_nao_normalizada", identificador, tipo_ocorrencia, pt, ano_texto, fonte,
                    mensagem=f"A data {ano_texto} é legível, mas seu campo numérico está vazio; a auditoria usou a expressão textual apenas para sinalizar a lacuna.")
            efetivo = ano if ano is not None else ano_pontual
            if efetivo is None:
                if ano_texto and str(ano_texto).strip():
                    alerta("data_imprecisa_ou_nao_interpretada", identificador, tipo_ocorrencia, pt, ano_texto, fonte,
                        mensagem=f"A data '{ano_texto}' não permite comparação pontual segura; requer revisão humana.")
                return
            fora_inicio = p["ini_num"] is not None and efetivo < p["ini_num"]
            fora_fim = p["fim_num"] is not None and efetivo > p["fim_num"]
            if fora_inicio or fora_fim:
                alerta("contradição_potencial", identificador, tipo_ocorrencia, pt, ano_texto, fonte,
                    mensagem=f"A ocorrência datada de {ano_texto or efetivo} está fora do intervalo estruturado de {p['titulo']} ({p['ano_inicio'] or '?'}–{p['ano_fim'] or '?'}). Verifique as fontes; nenhum dado foi alterado.")
            elif not fonte or not str(fonte).strip():
                alerta("proveniencia_insuficiente", identificador, tipo_ocorrencia, pt, ano_texto, fonte,
                    mensagem=f"A data da ocorrência está estruturada, mas não há fonte explícita vinculada a este registro.")

        for r in c.execute("""SELECT id,origem_tipo,origem_id,destino_tipo,destino_id,tipo,ano,ano_num,fonte
                             FROM relations WHERE (origem_tipo='periodical' OR destino_tipo='periodical')"""):
            pt = r["origem_id"] if r["origem_tipo"] == "periodical" else r["destino_id"]
            auditar_ocorrencia(pt, r["ano"], r["ano_num"], r["fonte"], f"relation:{r['id']}", r["tipo"])

        # Datas de manifestações são verificadas contra o periódico da aparição,
        # não contra o ano intelectual da obra. Uma data textual não normalizada
        # também precisa aparecer no diagnóstico.
        for m in c.execute("""SELECT id,periodical_id,ano_edicao,ed_num,fonte,referencia
                              FROM manifestations WHERE periodical_id IS NOT NULL"""):
            auditar_ocorrencia(m["periodical_id"], m["ano_edicao"], m["ed_num"], m["fonte"],
                               f"manifestation:{m['id']}", "manifestação/publicação")

        # Menções em notas são pistas, nunca ocorrências automaticamente afirmadas.
        for p in periodicos.values():
            notas = p.get("notas") or ""
            for match in re.finditer(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", notas):
                ano = int(match.group(1))
                if ((p["ini_num"] is not None and ano < p["ini_num"]) or
                    (p["fim_num"] is not None and ano > p["fim_num"])):
                    ini = max(0, match.start() - 65); fim = min(len(notas), match.end() + 65)
                    alerta("menção_em_notas", f"periodical:{p['id']}:notas:{match.start()}",
                        "menção cronológica em notas", p["id"], match.group(1), None,
                        evidencia_notas=notas[ini:fim], mensagem=f"As notas mencionam {match.group(1)}, fora do intervalo estruturado. A menção pode referir-se a outro acontecimento; confira o contexto.")

        # Alertas sobre o intervalo em si são adicionados após as ocorrências,
        # para que a inspeção abra primeiro a contradição concreta quando existir.
        for p in periodicos.values():
            if p["ini_num"] is None or p["fim_num"] is None:
                alerta("lacuna_intervalo", f"periodical:{p['id']}", "intervalo de circulação",
                    p["id"], mensagem=f"O intervalo de circulação de {p['titulo']} está incompleto. Isso impede uma verificação temporal integral.")
            if p["ini_num"] is not None and p["fim_num"] is not None and p["ini_num"] > p["fim_num"]:
                alerta("contradição_estruturada", f"periodical:{p['id']}", "intervalo de circulação", p["id"],
                    mensagem=f"O início estruturado de {p['titulo']} é posterior ao fim. Verifique os campos; nenhum dado foi alterado.")

        # Proveniência: fontes, evidências e integridade dos alvos.
        cont["sources"] = c.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        cont["evidences"] = c.execute("SELECT COUNT(*) FROM evidences").fetchone()[0]
        orfas = c.execute("""SELECT COUNT(*) FROM evidences e WHERE
            (e.entidade_tipo IN ('author','work','periodical','event','media','institution')
             AND NOT EXISTS (SELECT 1 FROM authors a WHERE e.entidade_tipo='author' AND a.id=e.entidade_id)
             AND NOT EXISTS (SELECT 1 FROM works w WHERE e.entidade_tipo='work' AND w.id=e.entidade_id)
             AND NOT EXISTS (SELECT 1 FROM periodicals p WHERE e.entidade_tipo='periodical' AND p.id=e.entidade_id)
             AND NOT EXISTS (SELECT 1 FROM events ev WHERE e.entidade_tipo='event' AND ev.id=e.entidade_id)
             AND NOT EXISTS (SELECT 1 FROM media m WHERE e.entidade_tipo='media' AND m.id=e.entidade_id)
             AND NOT EXISTS (SELECT 1 FROM institutions i WHERE e.entidade_tipo='institution' AND i.id=e.entidade_id))
            OR (e.entidade_tipo='manifestation' AND NOT EXISTS (SELECT 1 FROM manifestations m WHERE m.id=e.entidade_id))
            OR (e.entidade_tipo='issue' AND NOT EXISTS (SELECT 1 FROM periodical_issues i WHERE i.id=e.entidade_id))""").fetchone()[0]
        retidas = c.execute("SELECT COUNT(*) FROM evidences WHERE estado='revisao_necessaria'").fetchone()[0]
        versao = c.execute("PRAGMA user_version").fetchone()[0]
    lixo = sum(1 for _ in config.TRASH.iterdir()) if config.TRASH.exists() else 0
    mods = {}
    for m in ("fastapi", "pypdf", "docx", "uvicorn"):
        try: __import__(m); mods[m] = True
        except ImportError: mods[m] = False
    return {"contagens": cont, "dados": str(config.DATA), "python": sys.version.split()[0],
            "modulos": mods, "vendor": {n: (config.VENDOR / n).exists() for n in config.VENDOR_ESPERADOS},
            "lixeira_lotes": lixo, "tmp": sum(1 for _ in config.TMP.iterdir()), "online": online.ativo(),
            "alertas_temporais": alertas_temporais,
            "esquema": versao, "evidencias_orfas": orfas, "evidencias_em_revisao": retidas,
            "avisos_migracao": list(AVISOS)}
