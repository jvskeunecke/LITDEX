# -*- coding: utf-8 -*-
"""Testes das datas históricas — o ponto mais delicado do modelo."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.datas import analisar, ano_num, ano_preciso, rotulo_ano, parse_data_historica


class TestAnalise(unittest.TestCase):
    def caso(self, texto, ini, fim, precisao):
        r = analisar(texto)
        self.assertEqual((r["ano_inicio"], r["ano_fim"], r["tipo_precisao"]),
                         (ini, fim, precisao), f"entrada: {texto!r} -> {r}")
        if texto is not None:
            self.assertEqual(r["rotulo_original"], str(texto).strip())

    def test_ano_simples(self):
        self.caso("1839", 1839, 1839, "exata")
        self.caso(" 1890 ", 1890, 1890, "exata")

    def test_datas_completas(self):
        self.caso("1524-06-10", 1524, 1524, "exata")
        self.caso("10/06/1524", 1524, 1524, "exata")

    def test_antes_de_cristo(self):
        self.caso("384 a.C.", -384, -384, "exata")
        self.caso("384 ac", -384, -384, "exata")
        self.caso("-384", -384, -384, "exata")
        self.caso("65 d.C.", 65, 65, "exata")
        self.caso("c. 65 a.C.", -65, -65, "aproximada")

    def test_seculos(self):
        self.caso("séc. XIX", 1801, 1900, "intervalo")
        self.caso("século 18", 1701, 1800, "intervalo")
        self.caso("séc. V a.C.", -500, -401, "intervalo")
        self.caso("séc. I", 1, 100, "intervalo")

    def test_intervalos(self):
        self.caso("1850-1900", 1850, 1900, "intervalo")
        self.caso("1850–1900", 1850, 1900, "intervalo")
        self.caso("entre 1850 e 1900", 1850, 1900, "intervalo")
        self.caso("1850-1900?", 1850, 1900, "aproximada")

    def test_intervalo_nao_confunde_era_com_palavra(self):
        # o bug clássico: "Machado" contém "ac" e negativava o intervalo
        self.caso("Machado, 1850-1900", 1850, 1900, "intervalo")
        self.caso("Machado de Assis (1839-1908)", 1839, 1908, "intervalo")

    def test_faixas_abertas(self):
        self.caso("pós-1888", 1888, None, "inferida")
        self.caso("pré-1900", None, 1900, "inferida")

    def test_aproximacao_e_inferencia(self):
        self.caso("c. 1888", 1888, 1888, "aproximada")
        self.caso("ca. 1888", 1888, 1888, "aproximada")
        self.caso("por volta de 1888", 1888, 1888, "aproximada")
        self.caso("1888?", 1888, 1888, "aproximada")
        self.caso("data inferida: 1888", 1888, 1888, "inferida")

    def test_sem_data(self):
        self.caso("", None, None, "desconhecida")
        self.caso(None, None, None, "desconhecida")
        self.caso("s.d.", None, None, "desconhecida")

    def test_ancora(self):
        self.assertEqual(ano_num("1850-1900"), 1850)
        self.assertEqual(ano_num("séc. XIX"), 1850)
        self.assertEqual(ano_num("384 a.C."), -384)
        self.assertEqual(ano_num("c. 800 a.C."), -800)
        self.assertIsNone(ano_num("s.d."))

    def test_ano_preciso(self):
        self.assertEqual(ano_preciso("384 a.C."), -384)
        self.assertEqual(ano_preciso("1839"), 1839)
        self.assertIsNone(ano_preciso("c. 1839"))
        self.assertIsNone(ano_preciso("séc. XIX"))
        self.assertIsNone(ano_preciso("1850-1900"))
        self.assertIsNone(ano_preciso("pós-1888"))

    def test_rotulo(self):
        self.assertEqual(rotulo_ano(-384), "384 a.C.")
        self.assertEqual(rotulo_ano(1839), "1839")
        self.assertEqual(rotulo_ano(None), "")

    def test_alias_compativel(self):
        self.assertEqual(parse_data_historica("1850-1900")["tipo_precisao"], "intervalo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
