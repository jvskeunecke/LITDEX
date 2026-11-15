# LitDex V13.3 — relações, instituições e grafo

Atualização incremental sobre a V13.2 corrigida. O pacote não inclui `data/litdex.db`, arquivos de biblioteca ou acervo de demonstração: aplique sobre a instalação existente para preservar seus dados.

## Alterações
- Novo tipo canônico **Instituição**, com tabela migrada automaticamente, campos de tipo, fundação, extinção, local e notas; disponível no Fichário, busca, catálogo e grafo.
- Relações ampliadas: `cita` pode apontar de uma obra para obra, autor, periódico, mídia ou instituição; `menciona` registra referência neutra; `elogia` e `critica` aceitam entidades discursivas mais variadas.
- Seletor de relações em duas etapas: modalidade e tipo específico/direção.
- Cores semânticas de arestas: menção neutra (cinza), elogio (verde), crítica (vermelho) e citação (ocre). Outras relações conservam a cor de sua família. A seta continua representando direção.
- Edição em conjunto no grafo: selecionar origem e múltiplos destinos, revisar uma prévia/legenda e gravar a relação em lote; pares incompatíveis não entram no lote.
- Controles de movimento orbital contínuo e FPS reduzido/normal.
- Gaveta recolhível para obras integrantes (`parte_de`) na ficha da obra, sem confundir contenção intelectual com manifestação editorial.
- Testes de regressão para instituição, grafo e relações de menção/citação.

## Validação local
- `python -m compileall -q .` — aprovado.
- `node --check` para todos os scripts JS — aprovado.
- `python -m pytest -q` — 78 aprovados, 4 ignorados.

Os testes não substituem uma validação visual completa no Windows com o banco real do usuário. Faça cópia de segurança da pasta `data` antes de aplicar qualquer atualização.
