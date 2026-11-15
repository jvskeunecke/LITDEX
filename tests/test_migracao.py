# -*- coding: utf-8 -*-
"""Migração v13 → v14: conversão sem perda de autoria e créditos legados."""
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config, db  # noqa: E402
from tests.support import BaseLitDex  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v13.db"


def semear_v13(caminho):
    """Banco v13 real (vazio) + dados legados que a v14 precisa converter."""
    shutil.copy(FIXTURE, caminho)
    c = sqlite3.connect(caminho)
    c.execute("INSERT INTO authors(nome,nascimento,morte,nasc_num,morte_num) "
              "VALUES('Machado de Assis','1839','1908',1839,1908)")
    c.execute("INSERT INTO works(author_id,titulo,ano,ano_num) VALUES(1,'Dom Casmurro','1899',1899)")
    c.execute("""INSERT INTO manifestations(work_id,caminho,tipo_aparicao,ano_edicao,ed_num,tradutor,organizador)
                 VALUES(1,'','edição','1900',1900,'Machado de Assis','Tradutor Desconhecido')""")
    c.execute("INSERT INTO periodicals(titulo,tipo) VALUES('Revista Brasileira','revista')")
    # dois fascículos idênticos: a migração não pode derrubar o app por causa do índice único
    c.execute("DROP INDEX IF EXISTS i_issue_identity_number")
    c.execute("DROP INDEX IF EXISTS i_issue_identity_title")
    c.execute("INSERT INTO periodical_issues(periodical_id,volume,numero,data,data_num) VALUES(1,'1','2','1900',1900)")
    c.execute("INSERT INTO periodical_issues(periodical_id,volume,numero,data,data_num) VALUES(1,'1','2','1900',1900)")
    c.execute("INSERT INTO evidences(entidade_tipo,entidade_id,afirmacao,alvo_tipo,alvo_id) "
              "VALUES('work',1,'autoria atribuída','work_agent','wa:1')")
    c.commit()
    c.close()


class TestMigracao(BaseLitDex):
    def setUp(self):
        super().setUp()
        semear_v13(config.DB)

    def test_converte_autoria_e_creditos(self):
        ficha = self.ok(self.get("/api/entidades/work/1"))
        self.assertEqual(ficha["author_nome"], "Machado de Assis")
        self.assertEqual(len(ficha["agentes"]), 1)
        self.assertEqual(ficha["agentes"][0]["papel"], "autor_principal")

        c = sqlite3.connect(config.DB)
        c.row_factory = sqlite3.Row
        self.assertNotIn("author_id", [r[1] for r in c.execute("PRAGMA table_info(works)")])
        self.assertNotIn("tradutor", [r[1] for r in c.execute("PRAGMA table_info(manifestations)")])
        self.assertNotIn("organizador", [r[1] for r in c.execute("PRAGMA table_info(manifestations)")])
        self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0], 14)

        papeis = [r["papel"] for r in c.execute("SELECT papel FROM manifestation_agents")]
        self.assertIn("tradutor", papeis)

        # texto sem autor inequívoco vira evidência em revisão, não se perde
        ev = c.execute("SELECT * FROM evidences WHERE entidade_tipo='manifestation'").fetchone()
        self.assertIsNotNone(ev)
        self.assertEqual(ev["trecho"], "Tradutor Desconhecido")
        self.assertEqual(ev["estado"], "revisao_necessaria")

        self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(c.execute("PRAGMA foreign_key_check").fetchall(), [])
        c.close()

    def test_fasciculo_duplicado_nao_derruba_o_app(self):
        diag = self.ok(self.get("/api/diagnostico"))
        c = sqlite3.connect(config.DB)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM periodical_issues").fetchone()[0], 2)
        c.close()
        self.assertTrue(any("duplicados" in a for a in diag["avisos_migracao"]), diag["avisos_migracao"])
        self.ok(self.get("/api/timeline"))
        self.ok(self.get("/api/grafo"))

    def test_migracao_e_idempotente(self):
        self.ok(self.get("/api/catalogo"))
        db._prontos.clear()          # força nova migração sobre banco já convertido
        self.ok(self.get("/api/catalogo"))
        c = sqlite3.connect(config.DB)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM work_agents").fetchone()[0], 1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM manifestation_agents").fetchone()[0], 1)
        c.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
