# LitDex V13.3.1 — ajustes de usabilidade do Rizoma

- Removida a duplicação do controle “edição em conjunto” e de seu botão de ação.
- Removido o link “início” redundante da navegação: a marca LitDex no canto superior esquerdo já retorna à página inicial.
- O controle de pausa agora se chama “pausar movimento” / “retomar movimento”, informa seu estado e congela/retoma a simulação. A pausa é distinta de desligar a órbita contínua.
- A órbita contínua recebeu força mais perceptível e mantém a simulação ativa enquanto estiver ligada.
- Instituições são representadas por um hexágono e esse símbolo foi incluído na legenda do Rizoma. A cor própria da instituição já é definida no vocabulário.

Validação local: `python -m compileall -q .`, `node --check` em `grafo.js` e `base.js`; `python -m pytest -q`: 78 aprovados, 4 ignorados.

Pacote de atualização: não inclui `data/litdex.db` nem `data/library`; preserve os dados existentes ao aplicar.
