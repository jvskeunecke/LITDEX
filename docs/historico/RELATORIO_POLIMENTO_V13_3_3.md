# Relatório de engenharia — LitDex V13.3.3

## Resumo executivo

O risco P0 de gravação parcial no Rizoma foi fechado para o fluxo de edição em conjunto: a interface envia um único lote e o backend valida e grava tudo numa transação SQLite `BEGIN IMMEDIATE`. Os testes cobrem tanto falha na pré-validação quanto falha de negócio durante a fase de gravação e verificam que a primeira relação não persiste.

A atualização também oferece uma auditoria de passivo documental legado, uma operação assistida e não destrutiva de reconciliação, metadados epistemológicos de datas e mensagens explícitas sobre os limites da busca.

## 1. Operações em lote — P0

**Antes:** o frontend iterava pelos destinos e enviava uma requisição POST por relação. Se uma requisição posterior falhasse, as anteriores já poderiam estar gravadas.

**Agora:** `POST /api/relacoes/lote` aceita `{ "relacoes": [...] }`, limita o lote a 500 itens, verifica formato, tipos, predicados, IDs, existência dos participantes e mediação antes da escrita. A gravação ocorre em transação única com `BEGIN IMMEDIATE`; qualquer exceção escapa do contexto de conexão e aciona rollback. Erros de validação mantêm HTTP 400/404, conflito SQLite vira 409 e falhas inesperadas viram 500.

**Importante:** o endpoint reutiliza `core.relacoes.adicionar`, preservando regras de domínio existentes (incluindo a regra de que publicação em periódico deve ser modelada como manifestação/fascículo). Não foi criado um segundo caminho de persistência que contorne essas regras.

## 2. Reconciliação de proveniência — P1

A auditoria `GET /api/migracao/fontes-legadas` percorre campos textuais legados em obras, autores, periódicos, eventos, mídias, instituições, manifestações, fascículos e relações/participações. É somente leitura e sinaliza que a semelhança textual não prova identidade de fonte.

A operação `POST /api/migracao/fontes-legadas/reconciliar` cria um registro em `sources` e uma `evidence` associada, preservando integralmente os valores antigos. A evidência começa como `revisao_necessaria`: converter um campo em catálogo não pode transformar automaticamente uma nota ambígua numa afirmação historiográfica validada. O marcador nas notas da evidência evita que a mesma operação de reconciliação crie cópias repetidas.

**Débito remanescente:** a migração assistida ainda é API, não um painel visual completo; e caminhos legados continuam por compatibilidade. Proibir todo campo legado agora exigiria mapear todos os formulários e importadores para evitar regressões.

## 3. Datas historiográficas — P1

`core.datas.parse_data_historica()` separa o rótulo documental da âncora numérica e retorna `ano_inicio`, `ano_fim`, `tipo_precisao` e `rotulo_original`. Reconhece datas completas ISO/brasileiras, marcadores de aproximação, expressões inferidas, intervalos explícitos e séculos. Séculos retornam seus limites numéricos, não um ano pontual artificial.

A API `/api/timeline` transporta essa classificação para as entidades com data. `web/js/timeline.js` usa traço distinto e opacidade para pontos/barras aproximados, inferidos ou intervalares. A linha continua usando a escala numérica para manter ordenação e zoom; o rótulo original fica disponível no detalhe/tooltip da ocorrência.

**Limite:** os metadados são derivados do texto existente em tempo de leitura; não houve migração de banco nem colunas obrigatórias novas. Expressões ambíguas não reconhecidas devem ser revistas pelo pesquisador.

## 4. Busca, texto integral e OCR — P2

A rota `GET /api/busca/estado-indexacao` declara explicitamente que a busca atual trabalha com fichas, metadados, relações e proveniência, não com o texto integral dos anexos, e que OCR automático não está ativo. A página inicial apresenta essa ressalva quando não encontra correspondências.

O Scanner já devolvia mensagem específica para PDF sem camada textual; a alteração não promete OCR que o sistema não executa.

## 5. Resultados de teste

- Suíte Python: **84 passed, 4 skipped**.
- Compilação Python e validação sintática de JavaScript: aprovadas.
- Playwright: 59 verificações de interface aprovadas em Rizoma, perfis, cronologia, fallback SVG do mapa e editor de mapa.
- Navegação integral por servidor local não foi validada porque o Chromium deste ambiente bloqueou `127.0.0.1` (`ERR_BLOCKED_BY_ADMINISTRATOR`). O teste de mapa executou o fallback SVG; isso não comprova funcionamento do MapLibre/WebGL real.
- Não houve acesso ao banco pessoal nem alteração de dados do usuário.

## 6. Riscos ainda abertos e ordem recomendada

1. Executar smoke test no Windows com cópia do banco real e verificar `PRAGMA integrity_check` / `foreign_key_check`.
2. Criar painel de reconciliação visual com comparação lado a lado, seleção de fonte existente ou criação de nova, prévia e confirmação explícita.
3. Migrar os caminhos de escrita legados gradualmente para `sources/evidences`; só depois desativar a escrita antiga.
4. Acrescentar uma matriz de testes de integração real para API + SQLite + interface, incluindo falha simulada no meio de um lote e concorrência.
5. Representar intervalos temporais incertos com bandas ou extensões visuais em vez de somente estilo tracejado.
