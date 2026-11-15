from fastapi import Request

def perfil_ativo(request: Request):
    """Perfil escolhido na interface (cabeçalho X-Perfil) ou ?perfil=. None = Geral."""
    v = request.headers.get("x-perfil") or request.query_params.get("perfil")
    try:
        n = int(v)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None
