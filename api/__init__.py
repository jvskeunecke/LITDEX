"""Aplicação FastAPI: rotas da API, páginas e arquivos estáticos."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from core import config, files
from core.erros import ErroDominio

# Tipos MIME explícitos: no Windows o registro do sistema às vezes serve .js como text/plain, o que quebra os scripts e o mapa.
MIME = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json", ".geojson": "application/geo+json",
        ".html": "text/html", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".pdf": "application/pdf"}
def _arquivo(arq):
    return FileResponse(arq, media_type=MIME.get(arq.suffix.lower()))

PAGINAS = {"": "index", "biblioteca": "biblioteca", "fichas": "fichas", "grafo": "grafo", "timeline": "timeline",
           "mapa": "mapa", "perfis": "perfis", "diagnostico": "diagnostico"}

def create_app():
    from . import cadastros, catalogo, relacoes, scan, vistas, proveniencia
    app = FastAPI(title="LitDex", version="15.0")

    @app.exception_handler(ErroDominio)
    def _erro_dominio(request: Request, exc: ErroDominio):
        """O domínio não conhece HTTP; a tradução acontece aqui, num lugar só."""
        return JSONResponse(status_code=exc.status, content={"detail": exc.mensagem})

    for m in (cadastros, catalogo, relacoes, scan, vistas, proveniencia):
        app.include_router(m.router)

    @app.get("/")
    def raiz(): return RedirectResponse("/ui/")

    @app.get("/ui/autor")                       # endereços das versões anteriores
    def legado_autor(a: int | None = None):
        return RedirectResponse(f"/ui/fichas?t=author&id={a}" if a else "/ui/fichas?t=author")

    @app.get("/ui/obra")
    def legado_obra(w: int | None = None):
        return RedirectResponse(f"/ui/fichas?t=work&id={w}" if w else "/ui/fichas?t=work")

    def servir(pagina):
        nome = PAGINAS.get(pagina.strip("/"))
        arq = files.seguro_em(config.WEB, f"{nome}.html") if nome else None
        if not arq: raise HTTPException(404, "página não existe")
        return HTMLResponse(arq.read_text(encoding="utf-8"))

    @app.get("/ui/", response_class=HTMLResponse)       # /ui (sem barra) o próprio Starlette redireciona para cá
    def ui_raiz(): return servir("")

    @app.get("/ui/{pagina}", response_class=HTMLResponse)
    def ui(pagina: str): return servir(pagina)

    @app.get("/static/{caminho:path}")
    def estatico(caminho: str):
        arq = files.seguro_em(config.WEB, caminho)
        if not arq: raise HTTPException(404)
        return _arquivo(arq)

    @app.get("/vendor/{nome}")
    def vendor(nome: str):
        arq = files.seguro_em(config.VENDOR, nome)
        if not arq: raise HTTPException(404, "biblioteca não encontrada")
        return _arquivo(arq)

    @app.get("/arq/{caminho:path}")
    def arquivo(caminho: str):
        """Serve só o que está na biblioteca (nunca o banco nem a lixeira)."""
        arq = files.seguro_em(config.DATA, caminho)
        if not arq or config.LIB.resolve() not in arq.parents: raise HTTPException(404)
        return _arquivo(arq)

    return app
