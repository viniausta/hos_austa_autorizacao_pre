"""Hierarquia de exceções do domínio RPA.

Todas as exceções lançadas pelo robô devem herdar de RPAException,
permitindo captura granular ou genérica conforme necessário.
"""


class RPAException(Exception):
    """Base para todas as exceções do RPA."""


class ConfiguracaoError(RPAException):
    """Variável de ambiente obrigatória ausente ou inválida."""


class BancoDadosError(RPAException):
    """Falha na comunicação com o banco de dados."""


class NavegadorError(RPAException):
    """Falha ao inicializar ou operar o navegador."""


class ElementoNaoEncontradoError(NavegadorError):
    """Elemento web não localizado dentro do timeout especificado."""


class LoginFalhouError(RPAException):
    """Falha na autenticação no sistema alvo."""


class SpsadtFalhouError(RPAException):
    """Falha ao processar um SPSADT no portal web."""


class ParametroNaoEncontradoError(RPAException):
    """Parâmetro solicitado não existe no banco de parâmetros."""


class RegistroJaProcessadoError(RPAException):
    """Tentativa de reprocessar um registro já concluído."""
