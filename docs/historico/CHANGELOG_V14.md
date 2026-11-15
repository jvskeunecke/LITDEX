# LitDex 14 — o que mudou

Esta versão parte da v13.3.3 e responde ponto a ponto ao relatório técnico da v13. O objetivo foi
fechar os riscos que podiam produzir **afirmação errada** ou **perda de dado**, eliminar as duas
fontes de redundância do banco e deixar a interface dizer o que o backend já sabia.

## Correções que mudam o resultado, não só o código

**1. Datas históricas (`core/datas.py`).** O módulo foi reescrito em torno de um único analisador.
A era passou a ser um token (`a.C.`, `ac`, `aec`, `bc`, `bce`, `d.C.`…), nunca uma letra solta.

| Antes | Agora |
|---|---|
| `384 a.C.` virava *aproximada* | exata, `-384` |
| `Machado, 1850-1900` podia virar intervalo **negativo** (o `ac` de «Machado») | intervalo `1850–1900` |
| `-384` perdia o sinal em `parse_data_historica` | `-384` |
| século virava ponto | faixa (`1801–1900`) |
| `pós-`/`pré-` viravam ano pontual | faixa aberta, inferida |

Cobertura: 13 testes em `tests/test_datas.py`.

**2. Autoria com uma única fonte.** `works.author_id` deixou de existir. `work_agents` é a fonte
canônica; a leitura do autor principal é uma subconsulta única no SQL (`api/cadastros.AUTOR`).

- `PATCH /api/entidades/work` **não apaga mais** a participação para recriá-la: `E.definir_autor_principal`
  rebaixa o principal anterior a coautor preservando `ano`, `fonte` e `notas`, e reaproveita a linha
  se a pessoa já era coautora.
- Trocar a autoria marca as evidências ligadas à participação para revisão.
- `DELETE /api/entidades/author` informa quantas obras ficaram sem autor principal.

**3. Créditos de edição sem sincronização destrutiva.** `manifestations.tradutor` e `.organizador`
deixaram de existir; o crédito vive em `manifestation_agents`.

- A rotina antiga apagava **todos** os créditos de um papel e recriava só quando havia um único autor
  com o mesmo nome — com dois tradutores, o segundo desaparecia. Agora há endpoints explícitos
  (`POST/DELETE /api/obras/{id}/agentes` e `/api/manifestacoes/{id}/agentes`) que criam, atualizam e
  removem **uma** participação por vez.
- Texto legado sem autor identificável é preservado como evidência em revisão, não descartado.

**4. Migração tolerante a duplicatas.** Os índices únicos de fascículo são criados dentro de
`try/except`; se o banco antigo tiver duplicatas, o app continua abrindo e o Diagnóstico mostra o aviso
para o pesquisador resolver. Antes, uma duplicata derrubava **todas** as requisições.

**5. Mediação inválida não é mais 500.** `via_tipo` sem `via_id` (ou o contrário) devolve 400 com
mensagem clara.

**6. Evidências.** A comparação deixou de converter tudo para texto: reenviar o mesmo `source_id` não
reabre mais a evidência. Excluir uma ficha marca suas evidências como `nao_sustenta`, com motivo;
excluir uma relação faz o mesmo e mantém a trilha.

**7. Arquivo e transação.** Ingestão e novas edições passam a usar `files.estacionar` → INSERT →
commit → `files.promover`. Se a promoção falhar, a linha continua apontando para o arquivo na área de
entrada (`library/_incoming/`) — o documento não se perde. Antes, o arquivo era movido antes do INSERT
e podia ficar órfão.

**8. Deduplicação no servidor.** `POST /api/ingest` recusa (409) criar uma obra com o mesmo título e o
mesmo autor, explicando como anexar como edição; `criar_mesmo_assim=true` confirma a intenção. O
cliente já sugeria obras parecidas, mas a API criava duplicatas em silêncio.

**9. DOI de citação não classifica o documento.** O DOI passou a ser procurado só no início do corpo
(60 linhas). Um romance que cita um artigo nas referências não vira «artigo».

**10. Pequenos, mas reais.** `DELETE /api/relacoes/r12` funciona (antes só o PATCH aceitava o prefixo);
`PATCH /api/edicoes` aceita valores não textuais sem 500; `PATCH` de fascículo idem.

## Arquitetura e redundância

- **`core/erros.py`**: o domínio não importa mais FastAPI. `ErroDominio(mensagem, status)` é traduzido
  para HTTP num único handler em `api/__init__.py`. Isso tornou o domínio testável e eliminou
  `HTTPException` de `core/`.
- **`core/evidencias.py`**: a marcação de revisão passou a ter um só lugar e um só formato de id
  (`12`, `r12`, `r:12`, `wa:12`, `ma:12`). O código antigo montava `work:5` em vez de `wa:5`, e a
  evidência nunca era reencontrada.
- **Removidos**: `_sincronizar_campos_legados_manifestacao`, `_sincronizar_agente_manifestacao`,
  `trocarFicha`, `sleep`, o filtro morto `f.chave !== "livre" || true`.
- **Grafo**: o resumo agora distingue fichas, nós e ligações (antes contava manifestações como fichas).
- **Testes**: a suíte foi reescrita em `unittest` (sem pytest nem httpx), sobe o app real em uvicorn e
  isola os dados por teste. Os testes antigos de interface (Playwright) foram removidos por não serem
  executáveis no ambiente e dependerem de contratos que mudaram.

## Interface

- **Editor de agentes** na ficha da obra e em cada edição: escolher pessoa, papel, ano e fonte;
  remover com confirmação. Substitui os campos de texto livre «Tradução» e «Organização».
- **Bloco de evidências** em todas as fichas: estado (vigente / revisar / não sustenta), fonte, trecho,
  motivo da revisão, e ações de registrar, confirmar e excluir.
- **Estatuto no Fichário**: o painel de relações agora permite criar hipóteses, que aparecem com o
  selo «hipótese».
- **Mapa**: mostra o lugar atribuído e o papel geográfico de cada ficha, além do ponto canônico.
- **Diagnóstico**: mapeia os sete níveis de alerta (antes três apareciam como texto cru), exibe avisos
  de migração, evidências em revisão e órfãs, e a versão do esquema.
- **CSS**: marcadores de instituição e manifestação, estilos de agentes e evidências.

## Compatibilidade

- Bancos v13 (e anteriores) migram automaticamente na primeira abertura, sem perda.
- A API mantém os caminhos e o formato `{"detail": ...}` nos erros.
- `author_id` continua aceito como campo de entrada ao criar/editar obra, mas é traduzido para
  `work_agents`; não é mais devolvido como coluna da tabela.
- Clientes que enviavam `tradutor`/`organizador` no ingest continuam funcionando: o texto é convertido
  em crédito quando há autor único.

## Verificação

- **43 testes** passando (`python -m unittest discover -s tests -t .`), em Python 3.13 / FastAPI 0.162 /
  SQLite 3.50: 13 de datas, 3 de migração, 27 de API.
- Migração exercitada sobre uma base **v13 real** (fixture do acervo) com dados legados e fascículos
  duplicados: `integrity_check = ok`, `foreign_key_check` vazio, idempotente em segunda abertura.
- JavaScript validado com `node --check` nos seis arquivos.
- **Não executado**: navegador (sem Chromium no ambiente). A interface foi revista por leitura e por
  verificação de sintaxe; não houve teste de tela.
