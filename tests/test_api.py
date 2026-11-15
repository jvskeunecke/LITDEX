# -*- coding: utf-8 -*-
"""API v14: fichário, agentes, relações, proveniência, perfis, vistas e ingestão."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.support import BaseLitDex  # noqa: E402


class TestFichario(BaseLitDex):
    def test_obra_com_autor_usa_work_agents(self):
        a = self.criar("author", nome="Machado de Assis")
        w = self.criar("work", titulo="Dom Casmurro", ano="1899", author_id=a)
        ficha = self.ok(self.get(f"/api/entidades/work/{w}"))
        self.assertEqual(ficha["author_nome"], "Machado de Assis")
        self.assertEqual([x["papel"] for x in ficha["agentes"]], ["autor_principal"])

    def test_editar_obra_nao_perde_participacao(self):
        a = self.criar("author", nome="Autor A")
        w = self.criar("work", titulo="Obra", author_id=a)
        self.ok(self.post(f"/api/obras/{w}/agentes",
                          corpo={"author_id": a, "papel": "coautor", "fonte": "capa", "ano": "1900"}))
        self.ok(self.patch(f"/api/entidades/work/{w}", corpo={"titulo": "Obra revisada", "ano": "1901"}))
        ficha = self.ok(self.get(f"/api/entidades/work/{w}"))
        self.assertEqual(ficha["titulo"], "Obra revisada")
        papeis = {x["papel"] for x in ficha["agentes"]}
        self.assertEqual(papeis, {"autor_principal", "coautor"})
        coautor = [x for x in ficha["agentes"] if x["papel"] == "coautor"][0]
        self.assertEqual(coautor["fonte"], "capa")
        self.assertEqual(coautor["ano"], "1900")

    def test_trocar_autor_principal_rebaixa_o_anterior(self):
        a1 = self.criar("author", nome="Autor Um")
        a2 = self.criar("author", nome="Autor Dois")
        w = self.criar("work", titulo="Obra", author_id=a1)
        self.ok(self.patch(f"/api/entidades/work/{w}", corpo={"author_id": a2}))
        ficha = self.ok(self.get(f"/api/entidades/work/{w}"))
        self.assertEqual(ficha["author_nome"], "Autor Dois")
        papeis = {x["nome"]: x["papel"] for x in ficha["agentes"]}
        self.assertEqual(papeis["Autor Dois"], "autor_principal")
        self.assertEqual(papeis["Autor Um"], "coautor")

    def test_excluir_autor_informa_obras_sem_autor(self):
        a = self.criar("author", nome="Autor")
        for t in ("Um", "Dois"):
            self.criar("work", titulo=t, author_id=a)
        corpo = self.ok(self.delete(f"/api/entidades/author/{a}"))
        self.assertEqual(corpo["obras_sem_autor"], 2)
        obras = self.ok(self.get("/api/entidades/work"))
        self.assertEqual(len(obras), 2)

    def test_media_deduplica_por_nome(self):
        a = self.ok(self.post("/api/entidades/media", corpo={"nome": "Cinema"}))
        b = self.ok(self.post("/api/entidades/media", corpo={"nome": "cinema"}))
        self.assertEqual(a["id"], b["id"])
        self.assertTrue(b.get("existente"))

    def test_nome_vazio_e_rejeitado(self):
        status, corpo = self.post("/api/entidades/author", corpo={"nome": "   "})
        self.assertEqual(status, 400, corpo)


class TestAgentes(BaseLitDex):
    def test_credito_de_edicao(self):
        a = self.criar("author", nome="Tradutor")
        w = self.criar("work", titulo="Livro")
        m = self.ok(self.post(f"/api/works/{w}/edicoes", form={"editora": "Garnier"}))
        self.ok(self.post(f"/api/manifestacoes/{m['id']}/agentes",
                          corpo={"author_id": a, "papel": "tradutor", "fonte": "folha de rosto"}))
        ficha = self.ok(self.get(f"/api/entidades/work/{w}"))
        creditos = ficha["agentes_manifestacao"]
        self.assertEqual(len(creditos), 1)
        self.assertEqual(creditos[0]["papel"], "tradutor")

    def test_papel_invalido(self):
        a = self.criar("author", nome="Alguém")
        w = self.criar("work", titulo="Livro")
        status, _ = self.post(f"/api/obras/{w}/agentes", corpo={"author_id": a, "papel": "ilustradorchefe"})
        self.assertEqual(status, 400)

    def test_remover_participacao_reabre_evidencia(self):
        a = self.criar("author", nome="Autor")
        w = self.criar("work", titulo="Livro", author_id=a)
        ficha = self.ok(self.get(f"/api/entidades/work/{w}"))
        wa = ficha["agentes"][0]["id"]
        ev = self.ok(self.post("/api/evidencias", corpo={
            "entidade_tipo": "work", "entidade_id": w, "afirmacao": "autoria",
            "alvo_tipo": "work_agent", "alvo_id": f"wa:{wa}", "trecho": "capa"}))
        self.assertEqual(ev["estado"], "vigente")
        self.ok(self.delete(f"/api/relacoes/wa:{wa}"))
        lista = self.ok(self.get(f"/api/evidencias?entidade_tipo=work&entidade_id={w}"))
        self.assertEqual(lista[0]["estado"], "revisao_necessaria")


class TestRelacoes(BaseLitDex):
    def setUp(self):
        super().setUp()
        self.a = self.criar("author", nome="Autor")
        self.b = self.criar("author", nome="Outro")
        self.w = self.criar("work", titulo="Obra")

    def test_relacao_simples_e_duplicata(self):
        corpo = {"origem_tipo": "author", "origem_id": self.a, "destino_tipo": "author",
                 "destino_id": self.b, "tipo": "amizade"}
        r1 = self.ok(self.post("/api/relacoes", corpo=corpo))
        r2 = self.ok(self.post("/api/relacoes", corpo=corpo))
        self.assertEqual(r1["id"], r2["id"])
        self.assertTrue(r2["duplicado"])

    def test_publicado_em_recusado(self):
        p = self.criar("periodical", titulo="Revista")
        status, corpo = self.post("/api/relacoes", corpo={
            "origem_tipo": "work", "origem_id": self.w,
            "destino_tipo": "periodical", "destino_id": p, "tipo": "publicado_em"})
        self.assertEqual(status, 400, corpo)
        self.assertIn("manifesta", corpo["detail"])

    def test_mediacao_sem_id_vira_400(self):
        status, corpo = self.post("/api/relacoes", corpo={
            "origem_tipo": "author", "origem_id": self.a, "destino_tipo": "work",
            "destino_id": self.w, "tipo": "influencia", "via_tipo": "work"})
        self.assertEqual(status, 400, corpo)

    def test_lote_atomico(self):
        itens = [
            {"origem_tipo": "author", "origem_id": self.a, "destino_tipo": "author",
             "destino_id": self.b, "tipo": "amizade"},
            {"origem_tipo": "author", "origem_id": self.a, "destino_tipo": "work",
             "destino_id": self.w, "tipo": "inexistente"},
        ]
        status, corpo = self.post("/api/relacoes/lote", corpo={"relacoes": itens})
        self.assertEqual(status, 400, corpo)
        rels = self.ok(self.get(f"/api/entidades/author/{self.a}/relacoes"))
        self.assertEqual(rels, [])

    def test_remover_com_prefixo_r(self):
        r = self.ok(self.post("/api/relacoes", corpo={
            "origem_tipo": "author", "origem_id": self.a, "destino_tipo": "author",
            "destino_id": self.b, "tipo": "amizade"}))
        self.ok(self.delete(f"/api/relacoes/{r['id']}"))
        self.assertEqual(self.ok(self.get(f"/api/entidades/author/{self.a}/relacoes")), [])

    def test_hipotese_confirmada_vira_participacao(self):
        r = self.ok(self.post("/api/relacoes", corpo={
            "origem_tipo": "author", "origem_id": self.a, "destino_tipo": "work",
            "destino_id": self.w, "tipo": "autor_de", "estatuto": "hipotese"}))
        self.assertTrue(r["id"].startswith("r:"))
        convertida = self.ok(self.patch(f"/api/relacoes/{r['id']}", corpo={"estatuto": "documentada"}))
        self.assertIn("convertida", convertida)
        ficha = self.ok(self.get(f"/api/entidades/work/{self.w}"))
        self.assertEqual(ficha["author_nome"], "Autor")


class TestProveniencia(BaseLitDex):
    def test_editar_com_mesmo_source_id_nao_reabre(self):
        w = self.criar("work", titulo="Obra")
        fonte = self.ok(self.post("/api/fontes", corpo={"titulo": "Biblioteca Nacional", "url": "https://bn.br"}))
        ev = self.ok(self.post("/api/evidencias", corpo={
            "entidade_tipo": "work", "entidade_id": w, "afirmacao": "data",
            "source_id": fonte["id"], "trecho": "1899"}))
        atualizada = self.ok(self.patch(f"/api/evidencias/{ev['id']}",
                                        corpo={"source_id": fonte["id"], "notas": "conferido"}))
        self.assertEqual(atualizada["estado"], "vigente")
        self.assertIsNone(atualizada.get("motivo_revisao"))

    def test_mudar_trecho_reabre(self):
        w = self.criar("work", titulo="Obra")
        ev = self.ok(self.post("/api/evidencias", corpo={
            "entidade_tipo": "work", "entidade_id": w, "afirmacao": "data", "trecho": "1899"}))
        atualizada = self.ok(self.patch(f"/api/evidencias/{ev['id']}", corpo={"trecho": "1900"}))
        self.assertEqual(atualizada["estado"], "revisao_necessaria")

    def test_apagar_fonte_preserva_evidencia(self):
        w = self.criar("work", titulo="Obra")
        fonte = self.ok(self.post("/api/fontes", corpo={"titulo": "Fonte"}))
        ev = self.ok(self.post("/api/evidencias", corpo={
            "entidade_tipo": "work", "entidade_id": w, "afirmacao": "x", "source_id": fonte["id"]}))
        self.ok(self.delete(f"/api/fontes/{fonte['id']}"))
        depois = self.ok(self.get(f"/api/evidencias?entidade_tipo=work&entidade_id={w}"))
        self.assertEqual(depois[0]["id"], ev["id"])
        self.assertEqual(depois[0]["estado"], "revisao_necessaria")
        self.assertIsNone(depois[0]["source_id"])

    def test_apagar_obra_marca_evidencia_nao_sustenta(self):
        w = self.criar("work", titulo="Obra")
        self.ok(self.post("/api/evidencias", corpo={
            "entidade_tipo": "work", "entidade_id": w, "afirmacao": "x"}))
        self.ok(self.delete(f"/api/entidades/work/{w}"))
        todas = self.ok(self.get("/api/evidencias"))
        self.assertEqual(todas[0]["estado"], "nao_sustenta")
        self.assertIn("excluída", todas[0]["motivo_revisao"])


class TestPerfisEVistas(BaseLitDex):
    def test_perfil_recorta_sem_copiar(self):
        a = self.criar("author", nome="Dentro")
        self.criar("author", nome="Fora")
        p = self.ok(self.post("/api/perfis", corpo={"nome": "Recorte"}))
        self.ok(self.post(f"/api/perfis/{p['id']}/itens", corpo={"tipo": "author", "id": a}))
        autores = self.ok(self.get("/api/fichas", headers={"X-Perfil": str(p["id"])}))
        self.assertEqual([x["nome"] for x in autores], ["Dentro"])
        self.assertEqual(len(self.ok(self.get("/api/fichas"))), 2)

    def test_perfil_inexistente_ao_anexar(self):
        status, _ = self.post("/api/perfis/999/itens", corpo={"tipo": "author", "id": 1})
        self.assertEqual(status, 404)

    def test_vistas_respondem(self):
        a = self.criar("author", nome="Machado", nascimento="1839", morte="1908")
        w = self.criar("work", titulo="Memórias Póstumas", ano="1881", author_id=a)
        self.ok(self.get(f"/api/entidades/work/{w}"))
        for rota in ("/api/grafo", "/api/timeline", "/api/mapa", "/api/catalogo", "/api/biblioteca"):
            self.ok(self.get(rota))
        achados = self.ok(self.get("/api/busca?q=machado"))
        self.assertTrue(any(x["tipo"] == "author" for x in achados))
        self.assertTrue(all(x.get("campo") for x in achados))

    def test_paginas_servidas(self):
        for pagina in ("", "fichas", "biblioteca", "grafo", "timeline", "mapa", "perfis", "diagnostico"):
            status, corpo = self.get(f"/ui/{pagina}")
            self.assertEqual(status, 200, pagina)
            self.assertIn("LitDex", corpo)


class TestIngestao(BaseLitDex):
    TEXTO = ("DOM CASMURRO\n\nMachado de Assis\n\n1899\n\nLivraria Garnier\n\n"
             "CAPÍTULO PRIMEIRO\n\nUma noite destas, vindo da cidade para o Engenho Novo...\n")

    def enviar(self):
        return self.post("/api/scan", arquivo=("dom_casmurro.txt", self.TEXTO.encode("utf-8")))

    def test_scan_devolve_candidatos_com_origem(self):
        corpo = self.ok(self.enviar())
        self.assertTrue(corpo["titulo"])
        self.assertTrue(any("origens" in c for c in corpo["titulo"]))
        self.assertTrue(corpo["arquivo_temporario"])

    def test_ingest_cria_e_move_arquivo(self):
        scan = self.ok(self.enviar())
        corpo = self.ok(self.post("/api/ingest", corpo={
            "arquivo_temporario": scan["arquivo_temporario"],
            "titulo": "Dom Casmurro", "ano": "1899", "autor_novo": "Machado de Assis"}))
        ficha = self.ok(self.get(f"/api/entidades/work/{corpo['work_id']}"))
        caminho = ficha["edicoes"][0]["caminho"]
        self.assertTrue(caminho.startswith("library/"), caminho)
        self.assertTrue((self.dir / caminho).is_file())
        self.assertEqual(list((self.dir / "_tmp").iterdir()), [])

    def test_ingest_recusa_duplicata_por_padrao(self):
        s1 = self.ok(self.enviar())
        self.ok(self.post("/api/ingest", corpo={"arquivo_temporario": s1["arquivo_temporario"],
                                                "titulo": "Dom Casmurro", "autor_novo": "Machado"}))
        s2 = self.ok(self.enviar())
        status, corpo = self.post("/api/ingest", corpo={"arquivo_temporario": s2["arquivo_temporario"],
                                                        "titulo": "Dom Casmurro", "autor_novo": "Machado"})
        self.assertEqual(status, 409, corpo)
        self.assertIn("Já existe", corpo["detail"])

    def test_ingest_anexa_a_obra_existente(self):
        a = self.criar("author", nome="Machado")
        w = self.criar("work", titulo="Dom Casmurro", ano="1899", author_id=a)
        s = self.ok(self.enviar())
        corpo = self.ok(self.post("/api/ingest", corpo={
            "arquivo_temporario": s["arquivo_temporario"], "work_id_existente": w,
            "editora": "Garnier", "ano_edicao": "1900"}))
        self.assertTrue(corpo["anexado"])
        ficha = self.ok(self.get(f"/api/entidades/work/{w}"))
        self.assertEqual(len(ficha["edicoes"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
