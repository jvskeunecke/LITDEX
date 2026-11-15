"""Erro de domínio — independente de HTTP.

O `core/` decide o que é inválido e com que gravidade; a camada `api/` traduz para
status HTTP. Assim o domínio continua testável sem FastAPI e a mensagem ao usuário
nasce no lugar onde a regra vive.
"""


class ErroDominio(Exception):
    def __init__(self, mensagem, status=400, campo=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.campo = campo

    def __str__(self):
        return self.mensagem
