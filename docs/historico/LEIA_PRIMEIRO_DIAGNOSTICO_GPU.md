# LitDex V13.2 — correção de desempenho do Rizoma

## Instalação sem sobrescrever seus dados

Este ZIP é uma **atualização para uma instalação existente**. Extraia a pasta `LitDex_K` sobre a pasta `LitDex_K` que você já usa, permitindo substituir os arquivos do programa. O pacote **não contém `data/litdex.db`, `data/library/`, lixeira ou temporários**; assim, não substitui o banco, os PDFs ou as capas da sua instalação.

## O que foi ajustado

- O Rizoma interrompe a simulação, transições e enquadramentos da visualização anterior antes de redesenhar.
- Respostas antigas da API deixam de substituir o grafo mais recente quando filtros/cliques acontecem rapidamente.
- Grafos com 80+ nós ou 160+ arestas entram automaticamente em modo leve: sem animação de entrada, menos iterações de colisão e atualização visual limitada a aproximadamente 30 fps.
- A simulação esfria mais depressa; a aba oculta pausa o cálculo e retoma quando volta a ficar visível.
- O enquadramento calcula limites sem espalhar todos os nós como argumentos de função, evitando `RangeError` em grafos muito grandes.
- O mapa agora tem um renderizador alternativo SVG/D3, sem WebGL. Se MapLibre não conseguir criar o contexto gráfico, a aplicação troca para o mapa SVG em vez de deixar a tela de mapa inutilizável. Também é possível ativar manualmente **“usar modo seguro SVG (sem WebGL)”** no painel do mapa; a escolha fica lembrada na sessão. A volta ao MapLibre exige clicar em “voltar ao mapa WebGL”.
- Adicionado `tools/diagnostico_grafo.py`, leitura somente do banco, para conferir um perfil na instalação ativa.

## Diagnóstico do arquivo RAR recebido

O SQLite retorna `integrity_check = ok` e zero violações de chave estrangeira; não foram encontrados extremos de relação inválidos nas nove relações cadastradas. **O banco do RAR não contém o perfil Wenceslau**: a tabela `profiles` está vazia. O banco incluído tem 3 autores, 7 obras, 4 manifestações e 9 relações. Portanto, não há dados de Wenceslau nesse arquivo para corrigir, e nenhum dado dele foi inventado ou apagado.

Para verificar o banco real da sua instalação, execute na pasta do programa:

```powershell
py tools\diagnostico_grafo.py --perfil Wenceslau
```

O comando é somente leitura. Se o banco estiver em outro caminho, acrescente `--db "CAMINHO\litdex.db"`.

## Tela azul `nvlddmkm.sys / VIDEO_TDR_FAILURE`

Isso é uma falha/recuperação do driver gráfico no Windows, não um erro Python recuperável pela aplicação. O Rizoma usa SVG/D3, não WebGL diretamente; o mapa usa MapLibre/WebGL. Os ajustes reduzem o trabalho de renderização e permitem evitar WebGL no mapa, mas não comprovam a causa do TDR nem substituem a análise dos eventos e minidumps do Windows. O script `diagnostico_windows.ps1` só coleta informações; não altera drivers nem o registro.
