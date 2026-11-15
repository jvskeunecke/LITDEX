"""Apoio aos testes: sobe o app de verdade (uvicorn em thread) e isola os dados por teste.

Não usa `TestClient` porque o ambiente do projeto não tem httpx; assim a suíte roda
com o que está instalado (fastapi + uvicorn) e exercita a pilha HTTP real.
"""
import json
import shutil
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlencode

import uvicorn

from api import create_app
from core import config, db


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Servidor:
    _instancia = None

    @classmethod
    def obter(cls):
        if cls._instancia is None:
            cls._instancia = Servidor()
        return cls._instancia

    def __init__(self):
        self.porta = _porta_livre()
        cfg = uvicorn.Config(create_app(), host="127.0.0.1", port=self.porta, log_level="error")
        self.servidor = uvicorn.Server(cfg)
        self.thread = threading.Thread(target=self.servidor.run, daemon=True)
        self.thread.start()
        for _ in range(200):
            if getattr(self.servidor, "started", False):
                return
            time.sleep(0.05)
        raise RuntimeError("o servidor de teste não subiu")

    def pedir(self, metodo, caminho, corpo=None, form=None, arquivo=None, headers=None):
        url = f"http://127.0.0.1:{self.porta}{caminho}"
        dados, h = None, dict(headers or {})
        if corpo is not None:
            dados = json.dumps(corpo).encode("utf-8")
            h["Content-Type"] = "application/json"
        elif form is not None or arquivo is not None:
            dados, h["Content-Type"] = _multipart(form or {}, arquivo)
        req = urllib.request.Request(url, data=dados, method=metodo, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                bruto = r.read()
                return r.status, _decodificar(bruto, r.headers.get("content-type", ""))
        except urllib.error.HTTPError as e:
            bruto = e.read()
            return e.code, _decodificar(bruto, e.headers.get("content-type", ""))


def _decodificar(bruto, content_type):
    if "json" in content_type:
        try:
            return json.loads(bruto.decode("utf-8"))
        except ValueError:
            return bruto.decode("utf-8", "replace")
    return bruto.decode("utf-8", "replace")


def _multipart(campos, arquivo):
    fronteira = uuid.uuid4().hex
    partes = []
    for k, v in campos.items():
        partes.append(f"--{fronteira}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    if arquivo:
        nome, conteudo = arquivo
        partes.append(
            f"--{fronteira}\r\nContent-Disposition: form-data; name=\"arquivo\"; filename=\"{nome}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n".encode() + conteudo + b"\r\n")
    partes.append(f"--{fronteira}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={fronteira}"


class BaseLitDex(unittest.TestCase):
    """Cada teste ganha um diretório de dados próprio; o servidor é compartilhado."""

    @classmethod
    def setUpClass(cls):
        cls.http = Servidor.obter()

    def setUp(self):
        base = Path(__file__).resolve().parent.parent / ".testes"
        base.mkdir(exist_ok=True)
        self.dir = base / uuid.uuid4().hex[:10]
        for nome, sub in (("DATA", ""), ("LIB", "library"), ("TMP", "_tmp"), ("TRASH", "_trash")):
            p = self.dir / sub if sub else self.dir
            p.mkdir(parents=True, exist_ok=True)
            setattr(config, nome, p)
        config.DB = self.dir / "litdex.db"
        config.CONFIG = self.dir / "config.json"
        db._prontos.clear()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    # ---- atalhos
    def get(self, caminho, **kw):
        return self.http.pedir("GET", caminho, **kw)

    def post(self, caminho, corpo=None, **kw):
        return self.http.pedir("POST", caminho, corpo=corpo, **kw)

    def patch(self, caminho, corpo=None, **kw):
        return self.http.pedir("PATCH", caminho, corpo=corpo, **kw)

    def delete(self, caminho, **kw):
        return self.http.pedir("DELETE", caminho, **kw)

    def criar(self, tipo, **campos):
        status, corpo = self.post(f"/api/entidades/{tipo}", corpo=campos)
        self.assertEqual(status, 200, corpo)
        return corpo["id"]

    def ok(self, resposta):
        status, corpo = resposta
        self.assertEqual(status, 200, corpo)
        return corpo
