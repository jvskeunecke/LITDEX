#!/usr/bin/env python3
"""Povoa um acervo NOVO com três romances de domínio público — Dom Casmurro, Iracema e O Cortiço — seguindo o fluxo real:
o scanner lê cada PDF, aceitamos os candidatos certos, corrigimos o que ele não podia saber e completamos as fichas.

Os dados das fichas foram conferidos em fontes (Academia Brasileira de Letras, Câmara dos Deputados, Academia Maranhense de
Letras, UFC/USP, PUC-SP…); a fonte de cada relação vai no campo «fonte». Uso:  python tools/semear_exemplos.py [--recriar]"""
import shutil, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from core import config

if (config.DB.exists() or any(config.LIB.iterdir())):
    if "--recriar" not in sys.argv: sys.exit("data/ já tem dados. Use --recriar para apagar e semear de novo.")
    for p in (config.DB, config.CONFIG): p.unlink(missing_ok=True)
    for d in (config.LIB, config.TMP, config.TRASH): shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True, exist_ok=True)
from api import create_app
cl = TestClient(create_app()); EX = RAIZ / "tools" / "exemplos"

def post(rota, **j):
    r = cl.post(rota, json=j); assert r.status_code == 200, (rota, r.text); return r.json()
def patch(rota, **j):
    r = cl.patch(rota, json=j); assert r.status_code == 200, (rota, r.text); return r.json()
def criar(_t, **c): return post(f"/api/entidades/{_t}", **c)["id"]
def rel(ot, oi, dt, di, tipo, **x): return post("/api/relacoes", origem_tipo=ot, origem_id=oi, destino_tipo=dt, destino_id=di, tipo=tipo, **x)
def lugar(tipo, eid, nome, papel=None): post(f"/api/entidades/{tipo}/{eid}/lugares", nome=nome, papel=papel)
def tags(tipo, eid, *ts): [post(f"/api/entidades/{tipo}/{eid}/tags", nome=t) for t in ts]
def capa(tipo, eid, arq):
    r = cl.post(f"/api/entidades/{tipo}/{eid}/imagem", files={"imagem": (arq.name, arq.read_bytes(), "image/jpeg")}); assert r.status_code == 200, r.text
def escanear(pdf):
    r = cl.post("/api/scan", files={"arquivo": (pdf.name, pdf.read_bytes())}); assert r.status_code == 200, r.text; j = r.json(); assert "erro" not in j, j; return j
def melhor(j, campo, i=0): return (j[campo][i]["valor"] if len(j.get(campo, [])) > i else None)

# ---------------------------------------------------------------- 1) o scanner lê os três PDFs e nós revisamos
print("1) scanner → revisão → ingestão")
livros = {}
# --- Dom Casmurro: o scanner acerta título, autor, editora e local; a folha de rosto não traz ano (a obra é de 1899, Garnier)
j = escanear(EX / "pdfs/dom_casmurro.pdf"); assert melhor(j, "titulo") == "Dom Casmurro" and melhor(j, "autor") == "Machado de Assis" and melhor(j, "editora") == "H. Garnier"
r = post("/api/ingest", arquivo_temporario=j["arquivo_temporario"], titulo=melhor(j, "titulo"), autor_novo=melhor(j, "autor"), ano="1899", genero=melhor(j, "genero"),
         tipo="romance", idioma=melhor(j, "idioma"), editora=melhor(j, "editora"), local=melhor(j, "local"), fonte=melhor(j, "fonte"),
         edicao_nota="folha de rosto sem data (o e-book é de 2017, feito de exemplar digitalizado)", midias=["texto verbal"])
livros["dc"] = (r["work_id"], r["author_id"]); print("   Dom Casmurro  → scanner:", melhor(j, "autor"), "|", melhor(j, "editora"), "|", melhor(j, "local"))
# --- Iracema: a edição é PORTUGUESA de 1890 (Companhia Nacional Editora, Lisboa); a obra é de 1865 — obra ≠ edição
j = escanear(EX / "pdfs/iracema.pdf"); assert melhor(j, "titulo") == "Iracema" and melhor(j, "autor") == "José de Alencar" and melhor(j, "ano_edicao") == "1890"
r = post("/api/ingest", arquivo_temporario=j["arquivo_temporario"], titulo="Iracema", autor_novo=melhor(j, "autor"), ano="1865", genero=melhor(j, "genero"), tipo="romance",
         idioma=melhor(j, "idioma"), editora=melhor(j, "editora"), local=melhor(j, "local"), ano_edicao=melhor(j, "ano_edicao"), fonte=melhor(j, "fonte"),
         edicao_nota="Bibliotheca Universal Antiga e Moderna, 13ª série, nº 49 — com uma notícia biográfica do autor", midias=["texto verbal"])
livros["ir"] = (r["work_id"], r["author_id"]); print("   Iracema       → scanner:", melhor(j, "autor"), "|", melhor(j, "editora"), "|", melhor(j, "local"), "| ed.", melhor(j, "ano_edicao"))
# --- O Cortiço: o scanner acha «Aluizio Azevedo» (grafia da folha de rosto); corrigimos para a forma atual e ensinamos as variantes
j = escanear(EX / "pdfs/o_cortico.pdf"); assert melhor(j, "titulo") == "O Cortiço" and "azevedo" in melhor(j, "autor").lower() and melhor(j, "editora") == "H. Garnier"
r = post("/api/ingest", arquivo_temporario=j["arquivo_temporario"], titulo=melhor(j, "titulo"), autor_novo="Aluísio Azevedo", ano="1890", genero=melhor(j, "genero"), tipo="romance",
         idioma=melhor(j, "idioma"), editora=melhor(j, "editora"), local=melhor(j, "local"), ano_edicao="1897", fonte="Projeto Gutenberg #69187 (registro: H. Garnier, 1897)",
         edicao_nota=melhor(j, "edicao_nota"), midias=["texto verbal"])
livros["oc"] = (r["work_id"], r["author_id"]); print("   O Cortiço     → scanner:", melhor(j, "autor"), "→ corrigido para Aluísio Azevedo |", melhor(j, "editora"), "|", melhor(j, "edicao_nota"))
(dc, machado), (ir, alencar), (oc, aluisio) = livros["dc"], livros["ir"], livros["oc"]

# ---------------------------------------------------------------- 2) fichas dos autores
print("2) fichas dos autores")
patch(f"/api/entidades/author/{machado}", nascimento="1839-06-21", morte="1908-09-29", variantes=["Joaquim Maria Machado de Assis", "Assis, Machado de"],
      bio="Joaquim Maria Machado de Assis nasceu no Rio de Janeiro e morreu na mesma cidade. Romancista, contista, cronista, poeta, crítico e dramaturgo, é a figura central do **realismo** brasileiro.\n\n"
          "Foi fundador da **Academia Brasileira de Letras** — ocupou a cadeira 23, escolhendo José de Alencar como patrono — e seu primeiro presidente. "
          "Em 1866 publicou, na seção *Semana Literária* do *Diário do Rio de Janeiro*, um artigo sobre *Iracema*.")
patch(f"/api/entidades/author/{alencar}", nascimento="1829-05-01", morte="1877-12-12", variantes=["José Martiniano de Alencar", "Alencar, José de"],
      bio="José Martiniano de Alencar nasceu em Messejana, hoje parte de Fortaleza (Ceará), e morreu no Rio de Janeiro. Advogado, jornalista, político e escritor, "
          "foi redator-chefe do *Diário do Rio de Janeiro*, onde publicou *O Guarani* em folhetim (1857).\n\nPrincipal nome do **romantismo** brasileiro e do indianismo, "
          "é o patrono da cadeira 23 da Academia Brasileira de Letras, escolhido por Machado de Assis.")
patch(f"/api/entidades/author/{aluisio}", nascimento="1857-04-14", morte="1913-01-21",
      variantes=["Aluízio Azevedo", "Aluizio Azevedo", "Aluísio Tancredo Gonçalves de Azevedo", "Azevedo, Aluísio"],
      bio="Aluísio Tancredo Gonçalves de Azevedo nasceu em São Luís (Maranhão) e morreu em Buenos Aires, na Argentina, onde servia como diplomata. Romancista, caricaturista e diplomata, "
          "foi o principal nome do **naturalismo** brasileiro, com *O Mulato* (1881) e *O Cortiço* (1890).\n\nIrmão do dramaturgo Artur Azevedo, foi fundador da Academia Brasileira de Letras "
          "(cadeira 4, patrono Basílio da Gama).")
for a, nac, extra, ts in ((machado, "Brasil", ("Rio de Janeiro", "nascimento e morte"), ("realismo", "romance", "academia brasileira de letras")),
                          (alencar, "Brasil", ("Messejana", "nascimento"), ("romantismo", "indianismo", "romance")),
                          (aluisio, "Brasil", ("São Luís", "nascimento"), ("naturalismo", "romance", "academia brasileira de letras"))):
    lugar("author", a, nac, "nacionalidade"); lugar("author", a, *extra); tags("author", a, *ts)
lugar("author", alencar, "Rio de Janeiro", "morte"); lugar("author", aluisio, "Buenos Aires", "morte")

# ---------------------------------------------------------------- 3) fichas das obras (+ capas reais das edições)
print("3) fichas das obras")
patch(f"/api/entidades/work/{dc}", notas="Romance narrado em primeira pessoa por Bento Santiago, o «Dom Casmurro»; a dúvida sobre a fidelidade de Capitu é o centro do livro. Publicado em 1899 pela H. Garnier.")
patch(f"/api/entidades/work/{ir}", notas="Subtítulo: *lenda do Ceará*. Romance indianista sobre o amor de Iracema, a «virgem dos lábios de mel», e do português Martim. O prefácio (carta) é datado de maio de 1865. Saudado por Machado de Assis em artigo de 1866.")
patch(f"/api/entidades/work/{oc}", notas="Romance naturalista ambientado no cortiço de São Romão, no Rio de Janeiro. Publicado em 1890 (13 de maio).")
for w, c, ts in ((dc, "dom_casmurro", ("realismo", "romance")), (ir, "iracema", ("romantismo", "indianismo", "romance")), (oc, "o_cortico", ("naturalismo", "romance"))):
    capa("work", w, EX / f"capas/{c}.jpg"); tags("work", w, *ts)

# ---------------------------------------------------------------- 4) o que liga tudo: periódico, evento, artigo, adaptações
print("4) periódico, evento, artigo de Machado sobre Iracema e adaptações de Dom Casmurro")
diario = criar("periodical", titulo="Diário do Rio de Janeiro", tipo="jornal",
               notas="Jornal carioca do século XIX. Alencar foi seu redator-chefe e publicou nele *O Guarani* em folhetim (1857); Machado de Assis manteve aqui a seção *Semana Literária* (jan–jul de 1866).")
lugar("periodical", diario, "Rio de Janeiro", "publicação")
rel("author", alencar, "periodical", diario, "editou", notas="redator-chefe", fonte="Câmara dos Deputados / Academia Brasileira de Letras")
rel("author", machado, "periodical", diario, "colaborou_em", ano="1866", notas="seção Semana Literária", fonte="UFC / USP (estudos sobre a crítica de Machado de Assis)")
artigo = criar("work", titulo="Iracema, por José de Alencar", author_id=machado, ano="1866", genero="prosa", tipo="crítica",
               notas="Artigo de Machado de Assis sobre o romance de Alencar, na seção *Semana Literária* do *Diário do Rio de Janeiro*, em 23 de janeiro de 1866.")
post(f"/api/works/{artigo}/midias", nome="texto verbal"); tags("work", artigo, "crítica literária")
rel("work", artigo, "work", ir, "comenta", ano="1866", fonte="Machado de Assis, «Iracema, por José de Alencar», Diário do Rio de Janeiro, 23/01/1866")
cl.post(f"/api/works/{artigo}/edicoes", data={"tipo_aparicao": "publicação em periódico", "periodical_id": str(diario),
    "ano_edicao": "1866", "referencia": "Semana Literária, 23/01/1866",
    "fonte": "Diário do Rio de Janeiro, 23/01/1866"})
abl = criar("event", nome="Fundação da Academia Brasileira de Letras", tipo="encontro", ano="1897",
            notas="Machado de Assis foi eleito presidente em 28 de janeiro de 1897; a sessão inaugural foi em 20 de julho de 1897. Cada fundador escolheu um patrono para a sua cadeira — Machado, José de Alencar (cadeira 23); Aluísio Azevedo, Basílio da Gama (cadeira 4).")
lugar("event", abl, "Rio de Janeiro", "ocorrência")
rel("author", machado, "event", abl, "participou", ano="1897", notas="fundador (cadeira 23) e primeiro presidente", fonte="Academia Brasileira de Letras")
rel("author", aluisio, "event", abl, "participou", ano="1897", notas="fundador (cadeira 4)", fonte="Academia Brasileira de Letras")
rel("author", machado, "author", alencar, "homenageia", ano="1897", via_tipo="event", via_id=abl, notas="escolheu-o como patrono da cadeira 23", fonte="Academia Brasileira de Letras")
adaptacoes = [("Capitu", "1968", "cinema", "Filme dirigido por Paulo César Saraceni.", "filme", "Capitu (filme, 1968)"),
              ("Dom", "2003", "cinema", "Filme dirigido por Moacyr Góes; adaptação livre, com a história transposta para o Rio de Janeiro contemporâneo.", "filme", "Dom (filme, 2003)"),
              ("Capitu", "2008", "televisão", "Minissérie da TV Globo dirigida por Luiz Fernando Carvalho, exibida em dezembro de 2008.", "minissérie", "Capitu (minissérie, 2008)")]
for titulo, ano, midia, notas, tipo, rotulo in adaptacoes:
    w = criar("work", titulo=f"{titulo} ({tipo}, {ano})", ano=ano, tipo=tipo, notas=notas)
    post(f"/api/works/{w}/midias", nome=midia); tags("work", w, "adaptação")
    rel("work", w, "work", dc, "transposicao", ano=ano, fonte="PUC-SP e outras fontes sobre as adaptações de Dom Casmurro")

# ---------------------------------------------------------------- 5) conferência
print("\n5) conferência")
c = cl.get("/api/catalogo").json(); print("   contagem:", c["contagem"], "| arquivos:", c["arquivos"], "| relações:", c["relacoes"], "| dex:", c["media"], "%")
for w, nome in ((dc, "Dom Casmurro"), (ir, "Iracema"), (oc, "O Cortiço")):
    e = cl.get(f"/api/entidades/work/{w}").json()["edicoes"][0]
    print(f"   {nome:13} obra {cl.get(f'/api/entidades/work/{w}').json()['ano']} · edição {e['ano_edicao'] or '(sem ano)'} · {e['editora']} · {e['local']} · {e['paginas']} p. · {e['fonte']}")
# o scanner agora RECONHECE os autores pelas fichas: reenviar os PDFs aponta para as fichas existentes
for pdf in ("dom_casmurro", "iracema", "o_cortico"):
    j = escanear(EX / f"pdfs/{pdf}.pdf"); a = j["autor"][0]; print(f"   releitura {pdf:13} → autor «{a['valor']}» já na ficha #{a['author_id']}" if a.get("author_id") else f"   releitura {pdf}: AUTOR NÃO RECONHECIDO ({a['valor']})")
    cl.post("/api/descartar", json={"arquivo_temporario": j["arquivo_temporario"]})
print("\npronto: dados em", config.DATA)
