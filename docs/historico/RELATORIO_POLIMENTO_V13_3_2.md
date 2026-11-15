# LitDex — Relatório crítico de polimento e validação (V13.3.2)

**Data:** 23/10/2026  
**Base auditada:** pacote V13.3.1 `LitDex_V13_3_1_rizoma_usabilidade.zip`  
**Escopo:** Rizoma, mapa, cronologia, perfis, instituições, integridade do código, pesquisa documental de ponta a ponta.

## 1. Síntese executiva

A base está consideravelmente mais sólida do que uma interface demonstrativa: o backend tem migrações SQLite, separação entre obra e manifestação, fascículos, perfis como recortes, relações tipadas e proveniência de evidências. Mas a auditoria encontrou um problema de maturidade: **o código e os testes estavam parcialmente fora de sincronia**. Alguns testes ainda pressupunham o editor antigo; o teste de mapa não carregava D3 apesar de depender dele no caminho de fallback; a validação visual da cronologia e dos perfis não existia. Isso produzia falsos negativos e deixava regressões de interface passarem sem cobertura.

Também havia redundâncias reais: duas definições idênticas de `editorRelacaoEmConjunto`, duas declarações de tabela `institutions` e entradas duplicadas para a mesma entidade no cadastro. Embora parte delas não quebrasse o runtime por causa da semântica de sobrescrita do JavaScript/Python/SQLite, são sinais de manutenção descuidada e tornam futuras mudanças menos seguras.

Foram removidas as duplicações, corrigidos os testes obsoletos e feitas pequenas alterações funcionais nos controles do Rizoma e na integração geográfica das instituições. Não foi feita uma reescrita ampla: a estratégia foi corrigir falhas localizadas e aumentar a cobertura antes de alterar arquitetura.

## 2. Achados e alterações executadas

### P1 — Edição em conjunto não era autossuficiente

**Problema:** marcar “edição em conjunto” apenas mudava a seleção em lote, mas a seleção de nós dependia de `modoEdicao` estar ativado separadamente. A interface oferecia uma opção que, isoladamente, não permitia executar o fluxo que seu nome prometia.

**Correção:** ativar a edição em conjunto agora ativa também o modo de edição, limpa seleções anteriores, atualiza controles e recarrega o grafo. O aviso explica a ordem: origem primeiro, destinos depois.

**Risco residual:** o lote ainda envia uma requisição por destino. Se a rede ou API falhar no meio, parte do lote pode ter sido gravada. O passo futuro correto é uma rota transacional de lote no backend, não apenas uma promessa visual de atomicidade.

### P1 — Controles de movimento podiam mostrar um estado falso

**Problema:** “agitar” reiniciava a simulação, mas não redesenhava o controle de pausa. Alternar FPS também podia reconstruir a barra com o texto padrão, mesmo se a simulação estivesse pausada. O texto e o estado real podiam divergir.

**Correção:** os rótulos e `aria-pressed` do botão de pausa agora são derivados do estado efetivo; “agitar” e a alternância de FPS redesenham a barra preservando o estado atual. A força orbital foi aumentada de `0,0065` para `0,012`, com piso de atividade ligeiramente maior, para tornar a órbita perceptível sem trocar o algoritmo inteiro.

**Risco residual:** o ritmo ideal da órbita depende da densidade do grafo, do tamanho da janela e do desempenho do computador. Os testes confirmam que o estado e o ciclo de vida funcionam, mas não substituem uma avaliação visual prolongada no Windows com o acervo real.

### P1 — Instituições não participavam do mapa nem da cronologia, apesar de serem entidades canônicas

**Problema:** instituições existiam no Fichário e no Rizoma, mas não podiam receber atribuições de lugar pelo painel geográfico da ficha e não eram consultadas pelo endpoint do mapa. O campo textual `local` não é equivalente a um vínculo geográfico canônico: não permite reutilizar um mesmo lugar, posicioná-lo no mapa ou distinguir homônimos de forma consistente.

**Correção:** fichas de instituição agora exibem o bloco de lugares; o backend do mapa considera instituições; o mapa oferece o filtro “Instituições”. Também foi acrescentada uma faixa institucional à cronologia, com intervalos de fundação/extinção normalizados a partir dos campos textuais já existentes. O campo `local` permanece como texto de contexto, e o vínculo geográfico canônico é cadastrado separadamente.

**Limite:** instituições antigas que só tenham `local="São Paulo"` não são geocodificadas nem associadas automaticamente. Essa conversão automática seria arriscada; elas precisam ser vinculadas a um lugar canônico de forma explícita.

### P2 — Duplicações de código

Removidas:

- segunda definição idêntica de `editorRelacaoEmConjunto` em `web/js/grafo.js`;
- segunda declaração idêntica da tabela `institutions` em `core/db.py`;
- chave duplicada de `institution` em `_SQL_LISTA` e ramo repetido em `_sub` de `api/cadastros.py`.

Essas duplicações eram redundantes, não funcionalidades distintas.

### P2 — Testes de interface desatualizados ou incompletos

**Rizoma:** o teste ainda tratava o primeiro `<select>` como se fosse o tipo de relação. A interface atual usa dois níveis: modalidade e tipo/direção. Além disso, o mock não respondia ao endpoint de instituições, impedindo a abertura completa do editor estrutural. Atualizei o teste para refletir a interface real e incluí verificações de lote, órbita, pausa, retomada e FPS.

**Mapa:** o harness não carregava o pacote D3, embora o fallback SVG dependa de `d3.geoNaturalEarth1`/`d3.geoPath`, e esperava um marcador de prontidão exclusivo do fallback mesmo quando usava um mapa simulado. Corrigi o harness para carregar D3 e aguardar a fonte cartográfica criada.

**Cobertura nova:** adicionei testes de interface para cronologia e perfis. Isso não substitui o navegador completo contra servidor real, mas cobre mais do que a API isolada.

## 3. Pesquisa simples realizada como teste funcional

Usei um caso documental real para verificar se a arquitetura sustenta uma pesquisa, em vez de apenas criar fichas isoladas: a crítica de Machado de Assis intitulada **“José de Alencar: Iracema”**, publicada na seção “Semana Literária” do *Diário do Rio de Janeiro* em 23/01/1866.

Fontes consultadas:

- Portal de Literatura Brasileira da UFSC: https://literaturabrasileira.ufsc.br/index.php/documentos?id=209741
- Registro alternativo do texto e da referência original: https://pt.wikisource.org/wiki/Jos%C3%A9_de_Alencar%3A_Iracema

O cenário de teste, executado em banco SQLite isolado, cadastra Machado de Assis, José de Alencar, *Iracema*, o texto crítico, o periódico, o fascículo, a manifestação da crítica, a relação `comenta` mediada pelo periódico e uma evidência ligada à fonte. Em seguida, verifica que:

1. a crítica e *Iracema* permanecem obras distintas;
2. a publicação está representada por uma manifestação associada ao fascículo/periódico;
3. a relação entre textos mantém o periódico como mediação explícita;
4. a evidência aponta para uma afirmação relacional específica;
5. os nós chegam ao Rizoma e a manifestação chega à cronologia;
6. a ficha da crítica recupera sua manifestação.

**Resultado:** o fluxo passou. Isso valida a integração entre os componentes no caso de teste; não significa que os mesmos dados tenham sido inseridos no banco pessoal do usuário. Também não prova que toda relação histórica entre dois autores possa ser inferida automaticamente: o sistema deve continuar distinguindo relação documentada, mediação estrutural e hipótese.

## 4. Resultado dos testes

### Testes automatizados de backend e SQLite

`python -m pytest -q` — **79 passed, 4 skipped**.

Inclui CRUD, perfis, relações, fascículos, datas, mapa, migrações, evidências e o cenário documental Machado–*Iracema*.

### Testes de interface com Chromium

| Área | Resultado | O que foi exercitado |
|---|---:|---|
| Rizoma/editor | 30/30 | criação e edição de relações, evidências, direção, mediação, lote, pausa, órbita, FPS e grafo volumoso |
| Mapa/editor | 11/11 | catálogo de lugares, filtro de instituições, cadastro, edição e posicionamento por clique |
| MapLibre/WebGL real | 10/10 | canvas WebGL, fontes/camadas, clique físico e atualização da fonte GeoJSON; API simulada |
| Cronologia | 6/6 | faixas, filtro, escalas e navegação para ano |
| Perfis | 5/5 | Geral vs. recorte, estado ativo, fichas de instituição e ações disponíveis |

Também passaram `python -m compileall -q .` e `node --check` para todos os arquivos `web/js/*.js`.

**Limitação importante:** `tests/e2e_navegador.py` não pôde navegar para o servidor local neste ambiente: Chromium retornou `ERR_BLOCKED_BY_ADMINISTRATOR`. Portanto, não afirmo ter validado uma sessão integral do app servida por HTTP nem ter aberto a base real do usuário. Os testes de interface usam os JavaScripts reais com respostas de API simuladas; a persistência e as regras do backend são testadas separadamente com SQLite.

## 5. Crítica do produto: o que ainda ficou para trás

### 5.1 Proveniência ainda convive com campos legados

O catálogo `sources`/`evidences` já existe, mas `fonte`, `referencia` e `notas` ainda coexistem com ele. O pesquisador pode registrar a mesma referência em mais de um lugar e produzir duplicação semântica. Não é seguro migrar tudo automaticamente, porque textos idênticos podem representar fontes diferentes; é necessária uma ferramenta de reconciliação e migração assistida.

### 5.2 Lote precisa de transação real

A edição em conjunto já tem fluxo visual e teste de múltiplos destinos, mas grava relações em série. A próxima melhoria de engenharia deve criar `POST /api/relacoes/lote` com validação integral antes de qualquer escrita e transação única, retorno de erros por destino e prevenção de duplicatas. Sem isso, uma falha intermediária pode deixar um lote incompleto.

### 5.3 Mapa ainda depende de georreferenciamento explícito

Agora instituições podem receber lugares canônicos, mas a aplicação não deve transformar texto livre em coordenadas sem confirmação. O fluxo de atribuição geográfica poderia melhorar com sugestão de lugares já cadastrados e um estado claro “local textual não georreferenciado”. O mapa também precisa de teste manual com uma base densa e hierarquias geográficas reais, inclusive com homônimos e múltiplos papéis.

### 5.4 Cronologia ainda não é uma ferramenta historiográfica completa

A faixa de instituições foi adicionada, mas a cronologia ainda não comunica de forma suficientemente rica a precisão da data, sua fonte e a diferença entre data inferida, aproximada e documental. Datas como `c. 800 a.C.` são normalizadas para posicionamento; o rótulo e a origem epistemológica precisam continuar visíveis no detalhe. A faixa institucional usa fundação/extinção textuais e normaliza seus anos para posicionamento, mas a interface ainda não marca explicitamente quando a data é aproximada ou incerta.

### 5.5 Pesquisa e Scanner: limites devem ficar explícitos na experiência

A busca não indexa o texto integral de PDFs e o Scanner não faz OCR de digitalizações sem camada de texto. Esses limites estão documentados, mas a interface deveria distinguir com mais clareza “não encontrado no índice” de “não existe na fonte”, e apresentar o motivo de uma extração vazia. O enriquecimento online continua opcional e requer teste de integração real com provedores, além dos mocks.

### 5.6 Biblioteca de arquivos, manifestação e objeto físico ainda não são entidades totalmente independentes

A manifestação reúne metadados bibliográficos e caminho de arquivo. Isso é funcional para o uso corrente, mas não modela completamente exemplar, arquivo digital, fac-símile, cópia de consulta e proveniência arquivística como objetos distintos. A separação deve ser desenhada antes de ampliar anexos e digitalizações para evitar migração cara.

### 5.7 O teste de fumaça não substitui o uso diário

Ainda falta uma sessão manual, no Windows do usuário, com a base real: abrir fichas antigas, navegar entre manifestação e periódico, editar instituições, conferir mapa com locais reais, testar cronologia com datas incompletas e operar o Rizoma com muitas arestas. Esse é o próximo teste de aceitação, sobretudo porque o ambiente atual não permite o navegador HTTP integral.

## 6. Plano de continuidade recomendado

1. **P0 — Transação de relações em lote:** validação integral e gravação atômica; testes de falha intermediária e duplicidade.
2. **P0 — Teste de aceitação na base real:** cópia de segurança, migração em cópia, `integrity_check`, `foreign_key_check` e roteiro de navegação Windows.
3. **P1 — Reconciliação de fontes legadas:** detectar candidatos duplicados e permitir confirmar/migrar para `sources`/`evidences` sem apagar texto original.
4. **P1 — Cronologia historiográfica:** precisão e proveniência das datas; indicar visualmente datas aproximadas, incertas ou inferidas.
5. **P1 — Mapa:** estado de georreferenciamento, associação guiada a lugar canônico e cenários com homônimos/hierarquia/múltiplos papéis.
6. **P2 — Scanner e busca:** explicar resultados vazios, indexar texto integral quando viável e planejar OCR como módulo explícito.
7. **P2 — Arquivos e objetos:** desenho de modelo antes de separar arquivo digital, manifestação e exemplar físico.

## 7. Veredito

A atualização é uma correção de manutenção e cobertura, não uma declaração de que o LitDex está concluído. A base de relações e manifestações já sustenta um caso real de pesquisa, e as vistas principais passaram testes de componente; contudo, a diferença entre “tem uma tela” e “é confiável para investigação cotidiana” continua relevante. A prioridade agora não é acrescentar mais visualizações: é garantir atomicidade nas operações em lote, proveniência consistente, datas epistemicamente transparentes e validação na base real.
