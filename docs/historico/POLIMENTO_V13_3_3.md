# LitDex V13.3.3 — Confiabilidade transacional e transparência documental

Esta atualização parte da V13.3.2 e concentra-se em integridade, proveniência e datas historiográficas, sem remover campos ou reescrever dados antigos.

## Mudanças

- `POST /api/relacoes/lote`: valida a lista e os participantes, inicia `BEGIN IMMEDIATE`, grava o lote numa única transação e devolve `ROLLBACK` integral se algum item falhar. Limite de 500 relações por pedido.
- Rizoma: a edição em conjunto envia uma única requisição de lote, em vez de emitir uma chamada de gravação por destino.
- `GET /api/migracao/fontes-legadas`: auditoria somente de leitura de texto legado sem reconciliação formal.
- `POST /api/migracao/fontes-legadas/reconciliar`: promove campos legados para `sources` e `evidences`; mantém os campos originais e marca a nova evidência `revisao_necessaria`, porque a conversão técnica não prova relevância documental.
- `parse_data_historica`: preserva rótulo original e distingue data exata, aproximada, inferida, intervalo e desconhecida. Reconhece datas brasileiras/ISO, `c. 1865`, `pós-1888`, intervalos explícitos e séculos.
- Linha do tempo: recebe metadados epistemológicos e apresenta marcadores/linhas tracejados para datas não exatas.
- Busca: `GET /api/busca/estado-indexacao` expõe que a busca consulta metadados, não o texto integral dos anexos, e que não há OCR automático. Busca vazia na página inicial exibe esse limite.
- Compatibilidade: não são adicionadas colunas obrigatórias nem alteradas tabelas antigas. Os campos legados não são apagados automaticamente.

## Testes

- `python -m pytest -q`: 84 aprovados, 4 ignorados.
- `python -m compileall -q .`: aprovado.
- `node --check` em todos os `web/js/*.js`: aprovado.
- Playwright com Chromium do sistema: Rizoma 30/30, perfis 5/5, cronologia 6/6, mapa em fallback SVG 7/7 e editor do mapa 11/11.
- `tests/e2e_navegador.py` não pôde completar navegação por servidor local: Chromium retornou `ERR_BLOCKED_BY_ADMINISTRATOR` para `127.0.0.1`. O teste MapLibre com WebGL real não foi certificado; o teste de mapa exercitou o fallback SVG.

## Limites conhecidos

- O modo de edição em lote do frontend agora usa a rota atômica; outras ações de múltiplas requisições fora desse fluxo não se tornam transacionais por consequência.
- A reconciliação é assistida e não destrutiva, mas não é ainda um painel visual completo. O usuário aciona a API e precisa revisar as evidências antes de validá-las.
- A camada de proveniência legada continua disponível para compatibilidade. Esta atualização fornece auditoria e reconciliação, mas não proíbe universalmente todos os caminhos antigos de escrita; fazê-lo sem inventariar todos os formulários e importadores seria uma quebra arriscada.
- Datas aproximadas/inferidas continuam posicionadas usando uma âncora numérica na escala; a visualização sinaliza incerteza, mas não representa intervalos de incerteza como bandas quantitativas para todos os tipos de entidade.
- Não houve teste com o banco pessoal do usuário. A atualização não inclui `data/litdex.db` nem arquivos da biblioteca.
