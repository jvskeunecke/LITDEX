# LitDex — reestruturação e validação

## Direção conceitual

O Fichário é a fonte de verdade do acervo; biblioteca, busca, rizoma, cronologia e mapa são vistas desse mesmo conjunto. O Scanner propõe metadados que o usuário revisa. Relações e visualizações não devem inventar fatos para compensar ausências: quando faltam evidências, a lacuna deve continuar visível.

## Mudanças incorporadas

### Modelo e migração (esquema v10)

- Criadas tabelas canônicas `work_agents` e `manifestation_agents` para atribuir papéis de pessoas em obras e manifestações. `works.author_id` foi mantido por compatibilidade e sincronizado com o papel `autor_principal` para não quebrar fichas e integrações legadas.
- Acrescentada a entidade `periodical_issues` para fascículos de periódicos. Manifestações podem se ligar ao fascículo, e referências com volume/número explicitamente identificáveis podem gerar esse vínculo. Compartilhar o nome de um periódico ou somente o ano não prova coaparição.
- Manifestação pode apontar para outra manifestação continente. Ao remover uma obra continente, a obra-filho e sua manifestação são preservadas; remove-se a ligação, em vez de apagar a ocorrência filha.
- Ao excluir um periódico, as manifestações continuam no acervo, sem manter vínculos obsoletos ao periódico/fascículo apagado.
- A migração converte relações legadas `publicado_em` em manifestações e sincroniza participações que podem ser inferidas inequivocamente do modelo anterior. Não fabrica um fascículo quando a referência não oferece identificadores suficientes.
- Índices de identidade de fascículos diferenciam volumes/números identificados de fascículos apenas titulados; fascículos distintos com a mesma data não são fundidos silenciosamente.

### Integridade das relações e das vistas

- A participação canônica de autor principal é sincronizada ao criar, editar ou remover essa participação; isso evita deixar `works.author_id` apontando para um autor antigo.
- Participações estruturadas de tradutor/organizador são sincronizadas com os campos textuais legados quando há correspondência inequívoca. Remover a participação também remove somente o texto legado correspondente.
- Deduplicação de relações leva em conta evidências e datas, preservando ocorrências distintas; uma relação sem data/fonte não é automaticamente fundida com uma relação documentada.
- A camada geográfica agrega diferentes papéis do mesmo autor no mesmo lugar numa só aresta direta, preservando os papéis no payload; associações por hierarquia territorial ficam explicitamente marcadas como herdadas.
- O mapa permite consultar todos os papéis geográficos ou filtrar por papel e mantém separada a localização atribuída das coordenadas herdadas de ancestrais.
- A cronologia devolve identificadores e contexto da manifestação (tipo de aparição, periódico e referência) para que a ocorrência possa ser aberta sem perder sua identidade na obra-mãe.
- A ingestão aceita obras sem autoria identificada, sem tentar criar participações com pessoa inexistente.

### Busca e usabilidade investigativa

- A página inicial passou a orientar a entrada pelo Fichário e pela exploração do rizoma, sem esconder o Scanner; a busca anuncia explicitamente que procura referências, fontes e tags, não só nomes de entidades.

- A busca global inclui referências, notas, editoras, fontes, tags, fascículos e evidências de relações, indicando o campo que produziu a correspondência.
- O resultado de ingestão relata participações estruturadas, sem rotulá-las incorretamente como relações documentais.
- A completude leva em conta as participações canônicas de autoria/coautoria, em vez de depender apenas do campo legado.

## Verificações executadas

- `python -m pytest tests -q -rs`: **59 passed, 3 skipped**.
- Os 3 testes ignorados dependem de PDF de exemplo ausente, de uma versão histórica não incluída ou de PDFs de teste que não foram gerados no ambiente.
- `python -m compileall -q core api`: concluído.
- `node --check web/js/*.js`: todos os scripts JavaScript passaram.
- Cópia do banco de demonstração v3 migrada para v10: `PRAGMA integrity_check = ok`, `PRAGMA foreign_key_check = []`; 3 autores e 7 obras preservados; participações e manifestações disponíveis no novo modelo.
- O teste E2E foi tentado, mas não começou: o executável Chromium do Playwright não estava instalado. Não se afirma, portanto, que a navegação visual completa foi validada nesta sessão.

## Limites remanescentes, sem camuflagem

- As fontes e passagens de evidência ainda não formam um catálogo documental canônico reutilizável por múltiplas afirmações; seguem em campos textuais por relação/manifestação.
- Arquivo digital e exemplar/edição histórica ainda não são entidades independentes em todos os casos.
- O Scanner não executa OCR em PDF escaneado; a busca não indexa o texto integral dos documentos.
- Provedores online não foram verificados ao vivo nesta validação.
- Uma bateria de API não substitui teste manual/visual de cada fluxo no navegador.

Estas limitações são deliberadamente registradas. Não devem ser declaradas resolvidas apenas porque há uma tabela, um cartão ou um teste unitário correspondente.

## Revisão de coerência e rizoma — V10.1

- A relação `publicado_em` agora é tipificada na família **Publicação e suportes** (`obra → periódico`), em vez de cair silenciosamente na família genérica. O vínculo não substitui a manifestação/fascículo quando esses dados existem.
- A projeção de autores continua sendo uma projeção de caminhos, não um cadastro de relações pessoais. Mediações por periódico e evento agora são rotuladas explicitamente como contexto/coocorrência, sem implicar amizade, influência ou contato pessoal.
- O rizoma abrevia adaptativamente títulos longos, preserva o título integral no tooltip, usa halo de contraste nos rótulos e calcula uma distância de colisão proporcional ao comprimento do texto. O raio de colisão é aumentado para reduzir a sobreposição em regiões densas.
- A linha do tempo mantém contraste nas ocorrências não selecionadas; o foco orienta sem apagar o contexto.
- A biblioteca usa “Sem autoria principal registrada”, que não confunde ausência de crédito principal com autoria desconhecida nem promove automaticamente direção/produção audiovisual à categoria de autoria literária.
- O Diagnóstico inclui uma auditoria temporal não destrutiva: quando uma relação datada cai fora do intervalo estruturado de um periódico, o sistema aponta a relação, a fonte e os limites registrados. Nenhuma data é corrigida automaticamente. A ausência de alertas não comprova a exatidão histórica nem resolve datas ausentes.

### Regra de modelagem aplicada

Uma relação explicitamente documentada é diferente de uma relação estrutural derivável e de uma coocorrência projetada. Autoria e manifestação/publicação devem ser reconstruídas a partir dos registros canônicos; o pesquisador não deve precisar cadastrar novamente cada consequência desses vínculos. Relações sociais (amizade, influência, polêmica pessoal) só devem aparecer como fatos se houver evidência própria. A projeção pode sugerir caminhos de investigação, mas deve mostrar a mediação e seu estatuto epistemológico.

### Validação

`pytest -q`: **60 passed, 3 skipped**. Os testes cobrem o novo vocabulário `publicado_em`, a presença do vínculo no grafo e a emissão de alerta temporal sem alteração silenciosa da data. Os testes ignorados dependem de condições opcionais do ambiente; a bateria automatizada não substitui inspeção visual em navegador nem verificação externa das fontes históricas.


## Revisão estrutural V10.2 — projeções e estatuto documental

- A projeção autor↔autor agora deriva caminhos apenas de relações autor↔autor documentadas, relações semânticas entre obras, coautoria canônica, papéis na mesma manifestação e participações explícitas em evento. Relações mistas autor↔obra não geram associações incidentais.
- Relações entre obras preservam nas mediações a direção original, os nós de origem/destino, o tipo, a data e a fonte. A aresta agregada entre autores não apaga o sentido da relação intelectual.
- Um periódico comum, sem fascículo identificado, não gera mais uma aresta entre todos os seus autores/publicadores. Coocorrência editorial exige o mesmo fascículo identificado; a mediação é marcada como coocorrência documental, nunca como vínculo pessoal.
- O vínculo legado `publicado_em` deixou de ser uma opção de cadastro e a API rejeita novas gravações desse tipo. O caminho canônico é a manifestação da obra, ligada ao periódico e, quando identificado, ao fascículo. Dados antigos são migrados e a projeção suprime duplicatas legadas quando a manifestação já existe.
- Arestas do grafo incluem estatuto epistemológico uniforme: documentada, estrutural ou derivada. O painel do rizoma explicita a mediação, o sentido e as obras envolvidas.
- A auditoria temporal cobre relações, manifestações e anos encontrados em notas de periódicos. Menções em notas são alertas de revisão, não contradições confirmadas; lacunas nos intervalos de circulação também são diferenciadas. Nenhuma data é alterada automaticamente.
- A interface distingue cobertura de campos descritivos, enriquecimento opcional e rastreabilidade de fontes. Imagens, tags e relações não reduzem a cobertura descritiva central; a taxa de fontes mede apenas rastreabilidade, não veracidade.
- O rizoma atualiza a descrição dos modos de projeção; a cronologia conserva mais contraste; o mapa omite o rótulo redundante de lugares classificados como países, mantendo seus nomes no painel; fichas de obra recebem navegação local fixa.
- Removida a duplicação visual de participações adicionais na ficha de autor.

## Validação V10.2

- `python -m pytest tests -q -rs`: **66 passed, 3 skipped**.
- `python -m compileall -q core api`: concluído.
- `node --check` para todos os scripts JavaScript: concluído.
- O teste E2E com Chromium deve ser executado separadamente; os testes unitários não substituem essa inspeção visual.
- Tentativa de E2E com Chromium do sistema: o navegador bloqueou a navegação local antes de carregar a interface (`net::ERR_BLOCKED_BY_ADMINISTRATOR` em `127.0.0.1`), inclusive com `--no-proxy-server` e `--no-sandbox`. Portanto, não foi possível certificar visualmente as telas nesta execução; não se declara E2E aprovado.


## Consolidação V11 — proveniência e auditoria não destrutiva

- Criado o catálogo reutilizável `sources` e a tabela `evidences`, que vincula uma afirmação a uma entidade, fonte, trecho e localizador. A API oferece operações de leitura/criação/edição/remoção; excluir uma fonte preserva as evidências, apenas desvinculando a fonte.
- A completude documental passa a considerar evidências canônicas, sem confundir rastreabilidade com verdade ou qualidade da fonte.
- A auditoria temporal sinaliza datas textuais legíveis sem campo numérico, datas imprecisas não comparáveis, ocorrências sem fonte, intervalos ausentes/invertidos e contradições potenciais. Menções em notas continuam sendo pistas de revisão, não fatos afirmados. Nenhuma data é corrigida automaticamente.
- Esquema SQLite elevado para v11. Tabelas novas são adicionadas de modo compatível; registros legados não são reescritos para fontes/evidências sem identidade documental segura.
- Testes de regressão incluem preservação de evidência após remoção da fonte e data textual não normalizada.

## Validação V11

- `pytest -q`: **68 passed, 3 skipped**.
- `python -m compileall -q core api`: concluído.
- Checagem de sintaxe JavaScript e inspeção visual E2E permanecem itens distintos; o E2E depende de Chromium funcional e não é declarado aprovado nesta entrega.

## Consolidação V12 — edição pelo Rizoma e lugares canônicos

- O Rizoma ganhou modo de edição: a seleção ordenada de dois nós abre o formulário de criação de relação, com vocabulário tipado, direção explícita, data, fonte, mediação, notas e estatuto `documentada`/`hipotese`. Hipóteses são desenhadas com traço distinto e não são tratadas como fatos confirmados.
- A partir do grafo é possível criar fichas de autor, obra, periódico, evento e mídia. O cadastro passa a usar os mesmos endpoints e tabelas canônicas do Fichário; relações de autoria documentadas atualizam `work_agents` e a autoria principal compatível, evitando um vínculo paralelo invisível na ficha.
- A proveniência pode ser vinculada ao alvo específico da afirmação: relação genérica, participação autor–obra ou papel numa manifestação. O painel de relação permite cadastrar fonte, URL, afirmação, trecho e localizador. Evidência vinculada a uma entidade e evidência vinculada à afirmação passam a ser métricas distintas.
- O catálogo geográfico aceita lugares canônicos sem associação imediata a uma ficha. O mapa passa a exibir lugares georreferenciados mesmo quando não têm entidade associada; oferece edição do nome, tipo, contexto, coordenadas, notas e hierarquia, posicionamento por clique e associação do lugar selecionado a uma ficha.
- A criação de lugar reutiliza registros compatíveis por nome/contexto e retorna ambiguidade quando um nome homônimo não tem contexto suficiente para decidir com segurança.
- Esquema SQLite elevado a v12; a migração adiciona os campos de estatuto das relações e alvo da evidência sem reescrever os registros existentes.
- Testes novos cobrem estatuto epistemológico, evidência vinculada à relação, autoria criada pelo grafo atualizando o Fichário e lugar canônico independente.

## Validação V12

- `python -m pytest -q`: **71 passed, 3 skipped**.
- `python -m compileall -q .`: concluído.
- `node --check web/js/grafo.js` e `node --check web/js/mapa.js`: concluídos.
- A inspeção visual E2E ainda depende de Chromium funcional; não se declara a interface visual integralmente validada nesta execução.

## Revisão V12.1 — navegação e verificação de interação

- A marca `LitDex`, no canto superior esquerdo, é um link explícito para `/ui/` (Início), em todas as páginas que usam a navegação compartilhada.
- O editor do Rizoma só oferece tipos de relação compatíveis com os tipos das duas entidades selecionadas; quando o tipo requer sentido inverso, a gravação inverte os extremos para que o rótulo e a seta não se contradigam.
- A aresta manual `publicado_em` permanece indisponível: publicação deve ser modelada pela manifestação/fascículo e suas relações canônicas. A opção de ligação livre exige rótulo específico.
- Adicionados testes de interação dos scripts reais do grafo e do mapa com APIs simuladas. O teste do grafo cobre navegação pelo logotipo, seleção de duas obras, criação e edição da aresta e evidência vinculada à relação. O teste do mapa cobre catálogo canônico, cadastro, edição de coordenadas/notas e posicionamento por clique.
- Os testes de interação usam Chromium e scripts reais da interface, mas simulam APIs; no teste do mapa, MapLibre também é simulado para inspecionar a lógica de interação. Eles não certificam a renderização WebGL nem a cartografia real. A navegação E2E por URL local continuou indisponível porque a política administrativa do Chromium bloqueia todas as URLs (`URLBlocklist: ["*"]`).

## Validação V12.1

- `python -m pytest -q -rs`: **71 passed, 3 skipped**.
- `python tests/e2e_editor_grafo.py`: **12 controles aprovados**; sem exceções JavaScript.
- `python tests/e2e_editor_mapa.py`: **10 verificações aprovadas**; sem exceções JavaScript. O MapLibre é simulado neste teste.
- `node --check web/base.js`, `web/js/grafo.js` e `web/js/mapa.js`: concluídos.
- Não se declara a navegação real do servidor ou a renderização cartográfica WebGL integralmente validadas nesta execução.


## Consolidação V13 — edição estrutural e validação cartográfica real

- A edição de relações no Rizoma agora altera participantes, predicado, direção, rótulo e mediação de relações genéricas. Papéis canônicos pessoa–obra e pessoa–manifestação são atualizados nas tabelas próprias, sem produzir arestas paralelas. Vínculos inválidos são recusados antes de persistir mudanças.
- Quando muda a formulação relacional, as evidências vinculadas passam a `revisao_necessaria`. O pesquisador precisa confirmar explicitamente a pertinência ou marcar que a fonte não sustenta mais a afirmação. Alterar fonte, afirmação, trecho ou localizador de uma evidência também exige revisão.
- A edição de papéis em manifestações mantém sincronização conservadora com os campos legados `tradutor` e `organizador`: o campo só é limpo quando coincide exatamente com o crédito anterior; texto divergente é preservado e sinalizado, em vez de apagado.
- O editor estrutural só apresenta entidades compatíveis com o esquema. O estatuto epistemológico não é apresentado como editável em créditos canônicos quando a API não permitiria persistir essa alteração.
- O mapa foi executado com o pacote MapLibre real, canvas WebGL funcional por renderização de software, GeoJSON local e JavaScript da aplicação. O teste inclui editar coordenadas por clique e cadastrar/posicionar um lugar sem ficha associada; não usa `FakeMap`. As respostas da API desse teste visual são simuladas, enquanto API e SQLite são testados separadamente.
- O logotipo `LitDex` tem `href="/ui/"`; a rota HTTP `/ui/` é testada pela suíte FastAPI. A navegação completa do browser contra o servidor local permanece sem certificação porque a política administrativa de rede do Chromium bloqueia URLs locais neste ambiente.

### Validação V13

- `python -m pytest -q -rs`: **77 passed, 3 skipped**. Os skips são fixtures opcionais ausentes (PDFs ou versão anterior do banco).
- `python tests/e2e_editor_grafo.py`: **21 controles aprovados**, incluindo troca de participante, mediação, direção inversa e revisão de evidências; sem exceções JavaScript. As respostas da API no ensaio de interface são simuladas.
- `LIBGL_ALWAYS_SOFTWARE=1 LITDEX_MAP_HEADFUL=1 LITDEX_CHROMIUM=/usr/bin/chromium xvfb-run -a python tests/e2e_mapa_maplibre_real.py`: **10/10 verificações aprovadas**, com MapLibre e WebGL reais; API simulada para isolar a interface.
- `python -m compileall -q core api tests` e `node --check` em todos os scripts JavaScript: aprovados.
