class DataCheckError(Exception):
    """Erro esperado, com mensagem segura para ser exibida ao usuário."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
