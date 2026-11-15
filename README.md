# LitDex 15

**LitDex é um ambiente de catalogação e investigação literária.** O Fichário concentra o acervo; as demais vistas — biblioteca, busca, rizoma, cronologia e mapa — exploram os dados que foram construídos nele. O Scanner propõe informações a partir de documentos para revisão humana; não substitui a conferência da fonte.

A versão 15 mantém o esquema de dados 14 e consolida as correções de integridade da V14. As faixas da cronologia agora usam as cores do vocabulário canônico, evitando divergências entre vistas. Ver `CHANGELOG_V14.md` e `CHANGELOG_V15.md`.

## Executar

- **Windows:** abra `rodar.bat`.
- **Linux/macOS:** execute `./rodar.sh`.
- **Manualmente:** `pip install -r requirements.txt` e `python litdex.py`.

A aplicação abre em `http://127.0.0.1:8765/ui/` (ou noutra porta livre próxima). Os dados ficam em `data/`: banco SQLite, biblioteca de arquivos, área de entrada, temporários e lixeira. Para usar outra pasta de dados, defina `LITDEX_DATA` antes de iniciar. Faça uma cópia de `data/` antes de trocar de versão.

O LitDex funciona localmente sem internet para catalogação e consultas. Mapa detalhado e enriquecimento online dependem de conexão e são opcionais.

## Modelo de pesquisa

- **Obra:** unidade intelectual identificada pelo pesquisador.
- **Manifestação:** aparição concreta de uma obra — manuscrito, edição, tradução ou publicação em periódico. Registra data, referência, fonte, notas, local, arquivo e contexto de publicação. Uma publicação em periódico é uma manifestação, não uma relação manual.
- **Fascículo:** número/volume identificado de um periódico. Manifestações podem apontar para ele; o nome do periódico sozinho não prova coaparição.
- **Agente e papel:** a participação de uma pessoa numa obra ou numa edição tem papel próprio (autoria principal, coautoria, tradução, organização, ilustração, prefácio, entrevista). Essas participações vivem em `work_agents` e `manifestation_agents` — **não** existem colunas paralelas de autor, tradutor ou organizador.
- **Relação:** vínculo entre entidades com tipo, direção, rótulo invertido quando pertinente, data, fonte, mediação e estatuto (`documentada` ou `hipotese`).
- **Lugar:** uma ficha pode estar associada a um lugar por papéis diferentes; lugares têm hierarquia. O mapa distingue o lugar atribuído do ancestral usado apenas para posicionar a informação.
- **Perfil:** recorte de fichas do mesmo acervo, não uma cópia isolada dos dados.

Essas camadas permitem que um soneto seja uma obra só, com manifestações em jornal e em livro; que uma tradução tenha seus agentes; e que uma publicação seriada seja ligada a um fascículo específico. Coocorrência no mesmo fascículo ou evento não prova amizade, influência ou contato pessoal. Dados não conhecidos permanecem ausentes, em vez de serem estimados.

## Áreas principais

- **Fichário:** criar, revisar, relacionar e organizar autores, obras, periódicos, eventos, instituições e mídias. A ficha de obra inclui editor de agentes e bloco de evidências.
- **Scanner:** ler metadados extraíveis de PDF/DOCX/TXT/MD e apresentar campos sugeridos com evidências para confirmação.
- **Biblioteca:** navegar por obras e abrir o arquivo associado à manifestação.
- **Busca:** procura nomes e metadados documentais, incluindo referências, notas, tags, fontes, fascículos e relações; cada resultado indica o campo correspondente. Não indexa o texto integral dos PDFs.
- **Rizoma:** exibe relações registradas, ligações estruturais e camadas calculadas (projeções, contemporâneos, tags, lugares). Projeções são atalhos de leitura, não substitutos das mediações.
- **Cronologia:** separa datas de autores, obras, periódicos, eventos e manifestações. Datas aproximadas, inferidas e intervalos têm marcação própria.
- **Mapa:** explora atribuições geográficas; ancestrais com coordenadas posicionam locais específicos sem substituir o lugar atribuído.
- **Diagnóstico:** coerência temporal, proveniência, avisos de migração e ambiente.

## Datas históricas

`core/datas.py` interpreta o texto livre sem inventar precisão:

| Entrada | Leitura |
|---|---|
| `1839`, `1524-06-10` | ano exato |
| `384 a.C.`, `-384` | ano exato, negativo |
| `c. 800 a.C.` | aproximada |
| `séc. XIX`, `século 18` | intervalo 1801–1900 |
| `1850-1900`, `entre 1850 e 1900` | intervalo |
| `pós-1888`, `pré-1900` | faixa aberta, inferida |
| `Machado, 1850-1900` | intervalo — «Machado» não é uma era |

A era é lida como palavra, nunca como letra solta: era esse o defeito que negativava intervalos e tratava `a.C.` como aproximação.

## Migração (v13 → v14)

Ao abrir um banco antigo, a migração:

1. projeta `works.author_id` em `work_agents` (principal; se já havia outro principal, o autor legado vira coautor);
2. converte `manifestations.tradutor/organizador` em créditos quando há **um único** autor correspondente no catálogo;
3. quando não há correspondência inequívoca, preserva o texto como **evidência em revisão** — nada é descartado;
4. remove as colunas legadas e grava `user_version = 14`;
5. cria os índices de identidade de fascículo; se houver duplicatas no banco antigo, **avisa** no Diagnóstico em vez de bloquear o aplicativo.

Recomenda-se copiar `data/` antes de abrir uma versão nova.

## Relações e proveniência

O vocabulário tem 44 tipos em 9 famílias — ancoradas em Genette (transtextualidade) e Rajewsky (intermidialidade). `publicado_em` não é aceito como aresta manual: a publicação é registrada como manifestação. Uma hipótese de autoria pode existir como relação; ao ser confirmada, é promovida a participação canônica.

Fontes (`sources`) e evidências (`evidences`) ligam uma afirmação a um trecho, um localizador e uma fonte. Editar a fonte, a formulação, o trecho ou o localizador reabre a evidência; só uma confirmação explícita a fecha. Excluir uma ficha **não** apaga as evidências: elas ficam marcadas como `nao_sustenta`, com motivo, e aparecem no Diagnóstico.

## Executar os testes

A suíte usa apenas a biblioteca padrão (`unittest`) e sobe o app de verdade com uvicorn:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

No Windows, `instalar_dependencias_e_testar.bat` faz isso em um ambiente isolado. Os testes cobrem datas, migração v13→v14 e a API (fichário, agentes, relações, proveniência, perfis, vistas e ingestão).

## Limites conhecidos

- Não há OCR para PDFs escaneados nem busca no texto integral dos documentos.
- O mapa detalhado depende de internet; sem ela, há um mapa vetorial simplificado.
- Arquivo digital e exemplar histórico não são entidades separadas: a manifestação guarda a referência e o caminho do arquivo.
- A suíte não exercita navegador (não há teste de interface automatizado nesta versão); a API e a migração são testadas de ponta a ponta.
- Acervos muito grandes: as listagens ainda não são paginadas no cliente; a busca filtra no servidor.


## Se a aplicação não abrir (Windows)

1. Execute `rodar.bat` com duplo clique; mantenha a janela preta aberta.
2. Na primeira execução, o iniciador cria `.venv` e instala `requirements.txt`.
3. Se houver erro, não feche a janela: copie a mensagem completa. Ela identifica se o problema está no Python, nas dependências, no banco ou no servidor.
4. Quando o servidor informar o endereço local, a interface abre no navegador. Se o navegador não abrir automaticamente, copie o endereço `http://127.0.0.1:.../ui/` mostrado no terminal.

A versão 14 usa `unittest` (não exige `pytest`). Para validar a instalação:

```powershell
.venv\\Scripts\\python.exe -m unittest discover -s tests -t . -v
```

Antes de abrir a V15 sobre um acervo existente, faça uma cópia de `data/`. A migração do banco é automática; a cópia é a salvaguarda recomendada.
