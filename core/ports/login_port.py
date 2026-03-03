"""Porta de login — abstração para a camada de domínio.

Qualquer implementação de tela de login (TASY, outro sistema, mock para testes)
deve satisfazer este Protocol para ser injetada no ProcessarAutorizacaoUseCase.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LoginPort(Protocol):
    """Contrato de autenticação em um sistema web."""

    def realizar_login(self, url: str, usuario: str, senha: str) -> None:
        """Navega até a URL e autentica com as credenciais fornecidas.

        Raises:
            LoginFalhouError: Se a autenticação não puder ser concluída.
        """
        ...
