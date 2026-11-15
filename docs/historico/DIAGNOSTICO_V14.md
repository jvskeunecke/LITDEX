# Diagnóstico e correção de inicialização — LitDex V14

## O que foi verificado
- 43 testes `unittest`: todos passaram (1,8 s).
- `py_compile litdex.py`: passou.
- `node --check`: passou nos cinco módulos JavaScript da interface.
- Os testes incluem servidor Uvicorn real em thread, endpoints de páginas e API, ingestão, relações, proveniência e migração de banco V13.
- O teste de migração verifica idempotência e integridade referencial.
- Não foi possível validar a abertura gráfica do navegador neste ambiente; o relatório original da V14 também declara que não executou testes de navegador.

## Ajustes desta revisão
1. `litdex.py` agora aguarda o servidor aceitar conexões antes de abrir o navegador. O temporizador fixo anterior podia abrir a página antes de o servidor estar pronto em máquinas mais lentas.
2. `rodar.bat` verifica a existência do Python Launcher, cria `.venv`, instala as dependências e interrompe a inicialização com mensagem explícita se a instalação falhar.
3. `rodar.bat` inicia Python em modo não-bufferizado e mantém a janela aberta para que a mensagem de erro não desapareça.
4. `README.md` recebeu instruções para Windows e esclarece que a suíte usa `unittest`, não `pytest`.

## Limites
- Não recebi a mensagem exata de erro do computador do usuário; portanto, não posso afirmar que o defeito original foi reproduzido na mesma máquina.
- A execução de navegador/Chromium não foi validada nesta sessão.
- O pacote não contém banco pessoal; a V14 migra automaticamente o banco ao abrir. Faça cópia da pasta `data/` antes da primeira abertura.

## Como iniciar
No Windows, extraia o ZIP e execute `rodar.bat`. Não execute `pytest`. Para testes, use `instalar_dependencias_e_testar.bat` ou:
` .venv\\Scripts\\python.exe -m unittest discover -s tests -t . -v `
