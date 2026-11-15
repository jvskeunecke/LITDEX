# V13.3.2 — Polimento e cobertura

- Removidas duplicações de função e registro de instituição.
- Edição em conjunto ativa o modo de edição automaticamente.
- Controles de pausa, retomada, agitação e FPS mantêm rótulos sincronizados com o estado.
- Órbita do Rizoma mais perceptível.
- Instituições podem receber atribuições geográficas canônicas e aparecem como filtro no mapa.
- Corrigidos harnesses de teste do Rizoma e mapa para refletirem a interface atual.
- Adicionados smoke tests de cronologia e perfis. A cronologia agora inclui faixa institucional de fundação/extinção.
- Adicionado cenário documental de pesquisa com Machado de Assis, *Iracema*, o *Diário do Rio de Janeiro*, fascículo, manifestação e evidência de fonte.
- Relatório crítico completo em `RELATORIO_POLIMENTO_V13_3_2.md`.

## Validação

- `pytest`: 79 passed, 4 skipped.
- Rizoma: 30/30 verificações.
- Mapa/editor: 11/11.
- MapLibre/WebGL real: 10/10.
- Cronologia: 6/6.
- Perfis: 5/5.
- Compilação Python e sintaxe JavaScript aprovadas.

O teste HTTP integral via Chromium continua bloqueado neste ambiente (`ERR_BLOCKED_BY_ADMINISTRATOR`). Os testes interativos usam APIs simuladas; regras de persistência e migração são testadas separadamente em SQLite.
