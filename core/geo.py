"""Catálogo de lugares EMBUTIDO (funciona sem internet): países (nomes em português, dados de mledoze/countries, ODbL),
estados brasileiros, cidades de edição e de nascimento comuns na literatura e lugares históricos.
Serve para o mapa: escolher um lugar nunca exige digitar coordenadas. O módulo online (Nominatim) completa o que faltar."""
import json
from pathlib import Path
from .texto import normalizar

_REGIAO = {"Americas": "Américas", "Europe": "Europa", "Asia": "Ásia", "Africa": "África", "Oceania": "Oceania", "Antarctic": "Antártida"}

def _carregar_paises():
    arq = Path(__file__).parent / "data" / "paises.json"
    return [{"nome": n, "tipo": "pais", "contexto": _REGIAO.get(reg, reg), "lat": la, "lon": lo, "cca2": cc} for n, _en, cc, la, lo, reg, _cap in json.loads(arq.read_text(encoding="utf-8"))]

# (estado, UF, capital, lat, lon da capital)
_UF = [("Acre", "AC", "Rio Branco", -9.97, -67.81), ("Alagoas", "AL", "Maceió", -9.67, -35.74), ("Amapá", "AP", "Macapá", 0.03, -51.07),
       ("Amazonas", "AM", "Manaus", -3.12, -60.02), ("Bahia", "BA", "Salvador", -12.97, -38.50), ("Ceará", "CE", "Fortaleza", -3.73, -38.52),
       ("Distrito Federal", "DF", "Brasília", -15.79, -47.88), ("Espírito Santo", "ES", "Vitória", -20.32, -40.34), ("Goiás", "GO", "Goiânia", -16.68, -49.25),
       ("Maranhão", "MA", "São Luís", -2.53, -44.30), ("Mato Grosso", "MT", "Cuiabá", -15.60, -56.10), ("Mato Grosso do Sul", "MS", "Campo Grande", -20.47, -54.62),
       ("Minas Gerais", "MG", "Belo Horizonte", -19.92, -43.94), ("Pará", "PA", "Belém", -1.46, -48.50), ("Paraíba", "PB", "João Pessoa", -7.12, -34.86),
       ("Paraná", "PR", "Curitiba", -25.43, -49.27), ("Pernambuco", "PE", "Recife", -8.05, -34.88), ("Piauí", "PI", "Teresina", -5.09, -42.80),
       ("Rio de Janeiro", "RJ", "Rio de Janeiro", -22.91, -43.17), ("Rio Grande do Norte", "RN", "Natal", -5.79, -35.21),
       ("Rio Grande do Sul", "RS", "Porto Alegre", -30.03, -51.23), ("Rondônia", "RO", "Porto Velho", -8.76, -63.90), ("Roraima", "RR", "Boa Vista", 2.82, -60.67),
       ("Santa Catarina", "SC", "Florianópolis", -27.60, -48.55), ("São Paulo", "SP", "São Paulo", -23.55, -46.63), ("Sergipe", "SE", "Aracaju", -10.91, -37.07),
       ("Tocantins", "TO", "Palmas", -10.18, -48.33)]

# (cidade, contexto, lat, lon)
_CIDADES = [("Messejana", "Fortaleza, Ceará, Brasil", -3.83, -38.49), ("Santos", "São Paulo, Brasil", -23.96, -46.33), ("Petrópolis", "Rio de Janeiro, Brasil", -22.51, -43.18),
            ("Ouro Preto", "Minas Gerais, Brasil", -20.39, -43.50), ("Campinas", "São Paulo, Brasil", -22.91, -47.06),
            ("Lisboa", "Portugal", 38.72, -9.14), ("Porto", "Portugal", 41.15, -8.61), ("Coimbra", "Portugal", 40.21, -8.43), ("Paris", "França", 48.86, 2.35),
            ("Londres", "Reino Unido", 51.51, -0.13), ("Edimburgo", "Reino Unido", 55.95, -3.19), ("Dublin", "Irlanda", 53.35, -6.26), ("Madri", "Espanha", 40.42, -3.70),
            ("Barcelona", "Espanha", 41.39, 2.17), ("Roma", "Itália", 41.90, 12.50), ("Milão", "Itália", 45.46, 9.19), ("Florença", "Itália", 43.77, 11.26),
            ("Berlim", "Alemanha", 52.52, 13.40), ("Viena", "Áustria", 48.21, 16.37), ("Praga", "Tchéquia", 50.08, 14.44), ("Moscou", "Rússia", 55.76, 37.62),
            ("São Petersburgo", "Rússia", 59.93, 30.34), ("Atenas", "Grécia", 37.98, 23.73), ("Istambul", "Turquia", 41.01, 28.98), ("Cairo", "Egito", 30.04, 31.24),
            ("Nova York", "Estados Unidos", 40.71, -74.01), ("Buenos Aires", "Argentina", -34.60, -58.38), ("Montevidéu", "Uruguai", -34.90, -56.16),
            ("Santiago", "Chile", -33.45, -70.67), ("Lima", "Peru", -12.05, -77.04), ("Cidade do México", "México", 19.43, -99.13), ("Havana", "Cuba", 23.11, -82.37),
            ("Luanda", "Angola", -8.84, 13.23), ("Maputo", "Moçambique", -25.97, 32.57), ("Praia", "Cabo Verde", 14.93, -23.51), ("Bissau", "Guiné-Bissau", 11.86, -15.60),
            ("Macau", "China", 22.20, 113.55), ("Goa", "Índia", 15.30, 74.00)]

_HISTORICOS = [("Roma Antiga", 41.90, 12.50), ("Império Romano", 41.90, 12.50), ("Grécia Antiga", 38.00, 23.70), ("Egito Antigo", 26.00, 32.00),
               ("Mesopotâmia", 33.30, 44.40), ("Pérsia", 32.40, 53.70), ("Bizâncio", 41.00, 29.00), ("Império Austro-Húngaro", 47.50, 19.00),
               ("União Soviética", 55.70, 37.60), ("Prússia", 52.50, 13.40)]

def _montar():
    L = _carregar_paises()
    for est, uf, cap, la, lo in _UF:
        L.append({"nome": est, "tipo": "estado", "contexto": f"Brasil · {uf}", "lat": la, "lon": lo})
        if cap != est: L.append({"nome": cap, "tipo": "cidade", "contexto": f"{est}, Brasil", "lat": la, "lon": lo})
    for n, ctx, la, lo in _CIDADES: L.append({"nome": n, "tipo": "cidade", "contexto": ctx, "lat": la, "lon": lo})
    for n, la, lo in _HISTORICOS: L.append({"nome": n, "tipo": "historico", "contexto": "lugar histórico", "lat": la, "lon": lo})
    for x in L: x["_n"] = normalizar(x["nome"]); x["fonte"] = "catálogo embutido"
    return L

_LUGARES = _montar()
_ALIAS = {"eua": "estados unidos", "usa": "estados unidos", "urss": "uniao sovietica", "brazil": "brasil", "pariz": "paris", "madrid": "madri"}
_ORDEM = {"pais": 0, "estado": 1, "cidade": 2, "historico": 3}

def buscar(q, limite=8):
    """Lugares do catálogo que combinam com o texto (prefixo antes de trecho; país antes de estado antes de cidade)."""
    n = normalizar(q); n = _ALIAS.get(n, n)
    if len(n) < 2: return []
    achados = []
    for x in _LUGARES:
        if x["_n"] == n: pont = 0
        elif x["_n"].startswith(n): pont = 1
        elif n in x["_n"]: pont = 2
        else: continue
        achados.append((pont, _ORDEM[x["tipo"]], x["_n"], x))
    achados.sort(key=lambda t: t[:3])
    return [{k: v for k, v in x.items() if not k.startswith("_")} for *_, x in achados[:limite]]

def coordenadas(nome):
    """(lat, lon) do melhor casamento EXATO, ou None."""
    r = buscar(nome, 1)
    return (r[0]["lat"], r[0]["lon"]) if r and normalizar(r[0]["nome"]) == _ALIAS.get(normalizar(nome), normalizar(nome)) else None
