# Relatório técnico — LitDex 14

## Resumo

A v14 fecha os treze riscos apontados no relatório da v13 e remove as duas colunas que mantinham
dois caminhos de leitura para o mesmo dado (`works.author_id`, `manifestations.tradutor/.organizador`).
O esquema sobe para a versão 14 com migração automática, não destrutiva e tolerante a bases antigas.
A suíte foi reescrita para rodar sem dependências extras: **43 testes**, executados com o app real.

## O que mudou, risco por risco

| # | Risco na v13 | Situação na v14 | Onde |
|---|---|---|---|
| 1 | Datas a.C. e intervalos mal interpretados | reescrito; era é token, século é faixa, intervalo não negativa | `core/datas.py`, `tests/test_datas.py` |
| 2 | Créditos de edição apagados em massa | sincronização não destrutiva; endpoints por participação | `api/cadastros.py`, `core/relacoes.py` |
| 3 | PATCH de obra apagava o autor principal e perdia metadados | atualização no lugar; antigo rebaixado a coautor com `ano`/`fonte`/`notas` | `core/entidades.definir_autor_principal` |
| 4 | Índices únicos podiam bloquear todas as requisições | criação em `try/except`, aviso no Diagnóstico | `core/db._criar_indices_unicos` |
| 5 | Mediação sem `via_id` gerava 500 | 400 com mensagem | `core/relacoes.adicionar` |
| 6 | Evidência reabria sem mudança real | comparação tipada (int continua int) | `api/proveniencia._clean_evidencia` |
| 7 | Exclusão deixava evidências órfãs vigentes | marcas `nao_sustenta` + motivo; contagem no Diagnóstico | `core/entidades.limpar` |
| 8 | Arquivo movido antes do INSERT podia ficar órfão | `estacionar` → commit → `promover` | `core/files.py`, `api/scan.py`, `api/cadastros.py` |
| 9 | Listagens sem paginação | pendente (ver «Riscos remanescentes») | — |
| 10 | DELETE de relação não aceitava `r12` | aceita `12`, `r12`, `r:12` | `api/relacoes._id` |
| 11 | PATCH de edição quebrava com valor não textual | coerção explícita (`_texto`) | `api/cadastros._texto` |
| 12 | Mapa não mostrava o lugar atribuído | exibe lugar atribuído e papel por ficha | `web/js/mapa.js` |
| 13 | Instituição sem marcador visual | `.dot.institution` e `.dot.manifestation` | `web/base.css` |

Além desses, três defeitos encontrados durante a implementação:

- **Prefixo errado ao marcar revisão** (`work:5` em vez de `wa:5`) — centralizado em
  `core/evidencias.marcar_revisao`, que aceita as formas `12`, `r12`, `r:12`, `wa:12`, `ma:12`.
- **Hipótese de autoria sem saída** — ao ser confirmada, a relação é convertida em participação
  canônica e deixa de ser aresta (`PATCH /api/relacoes/{id}` com `estatuto=documentada`).
- **Duplicação silenciosa na ingestão** — o servidor passou a recusar (409) obra de mesmo título e
  autor, com instrução para anexar como edição; `criar_mesmo_assim=true` confirma a exceção.

## Esquema v14 e migração

Mudanças: remoção de `works.author_id`, `manifestations.tradutor` e `manifestations.organizador`;
`user_version = 14`; nenhuma tabela nova.

A migração executa, nesta ordem: alinhamento de colunas → sincronização de papéis legados →
conversão de `publicado_em` em manifestação → inferência conservadora de fascículo → **conversão de
autoria e créditos** → remoção das colunas → índices (com tolerância a duplicatas) → gêneros base.

Regras de conversão:

- `works.author_id` → `work_agents` como `autor_principal`; se já havia outro principal, o autor
  legado vira `coautor` (o vínculo não se perde).
- `manifestations.tradutor/.organizador` → `manifestation_agents` **somente** quando há exatamente
  um autor com o mesmo nome normalizado. Caso contrário, o texto vira `evidences` da manifestação,
  com `estado='revisao_necessaria'` e o trecho original — nada é descartado.

## Verificação executada

Ambiente: Python 3.13.17, FastAPI 0.162, Starlette 1.10, SQLite 3.50.4, uvicorn 0.54.

```
python -m unittest discover -s tests -t . -v
Ran 43 tests in 3.8s
OK
```

- `tests/test_datas.py` — 13 casos (a.C., séculos romanos e arábicos, intervalos, faixas abertas,
  aproximação, inferência, ausência de data, âncora e `ano_preciso`).
- `tests/test_migracao.py` — 3 casos sobre uma base **v13 real**: conversão de autoria e créditos,
  preservação de texto sem autor, `integrity_check = ok`, `foreign_key_check` vazio, idempotência e
  fascículos duplicados sem derrubar o app.
- `tests/test_api.py` — 27 casos: fichário, autor principal (inclusive troca sem perda), agentes de
  obra e de edição, relações (duplicata, `publicado_em`, mediação inválida, lote atômico, prefixo),
  hipótese promovida, proveniência (reabertura por mudança real, fonte removida, ficha excluída),
  perfis, vistas, páginas e ingestão (scan, criação, deduplicação, anexação e movimentação do arquivo).

Complementos: `node --check` nos seis arquivos JavaScript; inspeção do banco migrado
(`PRAGMA table_info`, `user_version`, contagens).

**Não verificado:** interface em navegador. Não há Chromium no ambiente; os testes cobrem HTML
servido (200) e a API que a interface consome, mas não o comportamento visual em tela.

## Riscos remanescentes (conscientes)

1. **Sem paginação** em `/api/fichas`, `/api/fontes` e `/api/evidencias`. Para acervos pessoais é
   aceitável; acima de alguns milhares de fichas a resposta fica pesada. A busca já filtra no servidor.
2. **Sem autenticação**: a API escuta em `127.0.0.1` e não tem CSRF. Decisão de projeto para uso
   individual; uma máquina compartilhada exige cautela.
3. **`api/cadastros.py` concentra SQL direto** (55 KB). É o ponto onde a fronteira entre camadas mais
   se borra; dividir por recurso seria o próximo passo estrutural.
4. **Sem OCR e sem índice de texto integral** — declarado na interface e no `/api/busca/estado-indexacao`.
5. **SQLite < 3.35**: a remoção de coluna cai no modo tolerante (mantém a coluna e avisa). O app
   funciona; a limpeza completa exige SQLite atualizado (o Python 3.11+ já traz).

## Como reproduzir a verificação

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Para conferir a migração sobre uma cópia do seu acervo:

```powershell
copy data\litdex.db data\litdex-backup.db
python litdex.py          # abre, migra e mostra avisos no Diagnóstico
```

Se algo não converter como esperado, o Diagnóstico lista os avisos e as evidências em revisão; o
banco original permanece intacto em `litdex-backup.db`.
