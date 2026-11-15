# LitDex 15

## Escopo da versão

A V15 é uma versão de manutenção sobre o esquema de banco 14. A leitura do relatório técnico da V13, da tabela de referenciais e das seis figuras de arquitetura confirmou que os principais riscos de integridade citados já foram tratados no código da V14. A mudança funcional identificada nesta revisão foi uma divergência visual na cronologia: a instituição continuava usando uma cor antiga, embora o rizoma, o mapa e o vocabulário já usassem a cor canônica.

## Ajustes

- Cronologia: faixas de autores, periódicos, obras, eventos e instituições leem a cor de `/api/vocab`; manifestações/edições mantêm uma cor própria para preservar sua distinção visual.
- Cronologia: inclusão do sufixo `?v=15` no script para evitar que o navegador reutilize a versão anterior em cache após a atualização.
- Versão: aplicação e metadados da API passam a informar `15.0`. O esquema de banco permanece em 14; não há migração nova.
- Rizoma: instituições usam o hexágono customizado compatível com D3 7.9 e a cor `#9b4f78` definida no vocabulário.

## Validação executada

- Suíte `unittest` da V15: 43 testes passaram, cobrindo datas, migração V13→V14, API, ingestão, agentes, relações, proveniência, perfis e respostas das vistas.
- Execução local isolada em `data-ui-test`, sem usar nem modificar o acervo pessoal.
- Navegador real: início e navegação; rizoma completo; projeção entre autores e detalhe da mediação; camadas calculadas de tag e lugar; formas e cores dos nós; linha do tempo, zoom por décadas e filtro de instituições; mapa detalhado com ponto, coordenadas, fichas e papéis; mapa seguro em SVG com 177 caminhos de países.
- Nenhum erro ou aviso de console apareceu nas telas exercitadas.
- Mapa detalhado depende de serviço externo de mapas; o modo SVG offline também foi aberto e conferido.

## Limites da validação

A suíte existente não cobre cada combinação das 73 rotas nem toda interação possível das oito vistas. A validação de navegador foi exploratória, com um acervo sintético pequeno e descartável; não substitui testes de carga ou um ensaio de migração sobre cópia do acervo real.
