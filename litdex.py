#!/usr/bin/env python3
"""LitDex 15 — aplicação local para investigação literária.

Execute `python litdex.py` para iniciar o servidor e abrir a interface.
Os dados ficam em data/ (ou no caminho definido por LITDEX_DATA).
"""
import socket
import sys
import threading
import time
import webbrowser

from core import config, files

VERSAO = "15.0"


def porta_livre(inicio=8765):
    for p in range(inicio, inicio + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return inicio


def abrir_quando_pronto(url, host, porta):
    """Abre o navegador somente depois que o servidor aceitar conexões."""
    limite = time.monotonic() + 20
    while time.monotonic() < limite:
        try:
            with socket.create_connection((host, porta), timeout=0.4):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.2)
    print(f"\\nO servidor não confirmou inicialização em 20 s. Abra manualmente: {url}")


def main():
    import uvicorn
    from api import create_app

    files.limpar_tmp()
    host = "127.0.0.1"
    porta = porta_livre()
    url = f"http://{host}:{porta}/ui/"
    print(f"\\nLitDex {VERSAO} em {url}   (Ctrl+C para sair)\\ndados em {config.DATA}", flush=True)
    threading.Thread(target=abrir_quando_pronto, args=(url, host, porta), daemon=True).start()
    uvicorn.run(create_app(), host=host, port=porta, log_level="info")


if __name__ == "__main__":
    sys.exit(main())
