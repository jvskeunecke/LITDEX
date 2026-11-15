#!/usr/bin/env python3
"""Diagnóstico somente-leitura do banco e do grafo LitDex.

Exemplo: python tools/diagnostico_grafo.py --perfil Wenceslau
Pode apontar --db para o banco da instalação ativa. Não migra nem grava nada.
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import config  # noqa: E402

TABLES = {
    "author": "authors", "work": "works", "event": "events", "media": "media",
    "periodical": "periodicals", "manifestation": "manifestations",
    "issue": "periodical_issues", "tag": "tags", "lugar": "places",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--perfil", default="Wenceslau", help="nome do perfil de pesquisa (padrão: Wenceslau)")
    ap.add_argument("--db", type=Path, default=config.DB, help="caminho de data/litdex.db da instalação ativa")
    args = ap.parse_args()
    db = args.db.expanduser().resolve()
    print(f"LitDex — diagnóstico somente-leitura\nBanco: {db}\nPerfil solicitado: {args.perfil}")
    if not db.is_file():
        print("ERRO: banco não encontrado. Confira --db.")
        return 2
    uri = db.as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as c:
            c.row_factory = sqlite3.Row
            integrity = [r[0] for r in c.execute("PRAGMA integrity_check")]
            fk = [tuple(r) for r in c.execute("PRAGMA foreign_key_check")]
            print(f"\nSQLite integrity_check: {'; '.join(integrity)}")
            print(f"Violações FK: {len(fk)}")
            if fk:
                for row in fk[:20]: print("  FK:", row)

            have = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            profile = None
            if "profiles" in have:
                profiles = [dict(r) for r in c.execute("SELECT id,nome FROM profiles ORDER BY nome")]
                profile = next((p for p in profiles if p["nome"].strip().casefold() == args.perfil.strip().casefold()), None)
                print("Perfis cadastrados:", ", ".join(p["nome"] for p in profiles) if profiles else "nenhum")
            else:
                profiles = []
                print("ERRO: tabela profiles não existe nesta versão do banco.")

            print("\nContagens do banco:")
            for typ, table in TABLES.items():
                if table in have:
                    n = c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                    print(f"  {typ:14s} {n:>7}")
            if "relations" in have:
                print(f"  {'relations':14s} {c.execute('SELECT COUNT(*) FROM relations').fetchone()[0]:>7}")
            if "profile_items" in have and profiles:
                print(f"  {'profile_items':14s} {c.execute('SELECT COUNT(*) FROM profile_items').fetchone()[0]:>7}")

            # Confere IDs de membros apontados pelo perfil sem alterar registros.
            if profile and "profile_items" in have:
                items = [dict(r) for r in c.execute("SELECT entity_tipo,entity_id FROM profile_items WHERE profile_id=?", (profile["id"],))]
                dangling = []
                for item in items:
                    table = TABLES.get(item["entity_tipo"])
                    if not table or table not in have:
                        dangling.append((item["entity_tipo"], item["entity_id"], "tipo/tabela desconhecido")); continue
                    if not c.execute(f'SELECT 1 FROM "{table}" WHERE id=?', (item["entity_id"],)).fetchone():
                        dangling.append((item["entity_tipo"], item["entity_id"], "entidade ausente"))
                print(f"\nPerfil '{profile['nome']}': {len(items)} item(ns), {len(dangling)} referência(s) pendente(s).")
                for d in dangling[:50]: print("  ITEM INVÁLIDO:", d)
            elif not profile:
                print(f"\nPERFIL NÃO ENCONTRADO: '{args.perfil}'. Nenhum dado foi alterado.")

            # Confere os extremos das relações em todas as tabelas conhecidas.
            bad_rel = []
            if "relations" in have:
                for r in c.execute("SELECT id,origem_tipo,origem_id,destino_tipo,destino_id FROM relations"):
                    for side in ("origem", "destino"):
                        typ, eid = r[f"{side}_tipo"], r[f"{side}_id"]
                        table = TABLES.get(typ)
                        if not table or table not in have or not c.execute(f'SELECT 1 FROM "{table}" WHERE id=?', (eid,)).fetchone():
                            bad_rel.append((r["id"], side, typ, eid))
                print(f"Extremos de relações inválidos: {len(bad_rel)}")
                for x in bad_rel[:50]: print("  RELAÇÃO INVÁLIDA:", x)

            if profile:
                try:
                    from core.grafo import construir
                    graph = construir(c, pid=profile["id"])
                    deg = Counter()
                    for edge in graph["arestas"]:
                        deg[edge["origem"]] += 1; deg[edge["destino"]] += 1
                    print(f"\nGrafo de '{profile['nome']}': {len(graph['nos'])} nó(s), {len(graph['arestas'])} aresta(s).")
                    print("Maior grau:", ", ".join(f"{k} ({v})" for k, v in deg.most_common(10)) or "nenhum")
                except Exception as exc:
                    print(f"ERRO construindo grafo do perfil: {type(exc).__name__}: {exc}")
                    return 3

            if integrity != ["ok"] or fk or bad_rel:
                print("\nRESULTADO: encontrado(s) problema(s) de integridade; não foi feita correção automática.")
                return 1
            print("\nRESULTADO: integridade estrutural do banco aprovada. Isso não substitui os logs de tela azul do Windows.")
            return 0 if profile else 4
    except sqlite3.Error as exc:
        print(f"ERRO SQLite: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
