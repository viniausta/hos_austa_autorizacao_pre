"""Porta de SPSADT — abstração para a camada de domínio.

Qualquer implementação de tela de SPSADT (TASY, mock para testes)
deve satisfazer este Protocol para ser injetada no ProcessarAutorizacaoUseCase.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.entities.autorizacao import Autorizacao


@runtime_checkable
class SpsadtPort(Protocol):
    """Contrato de processamento de um SPSADT no portal web."""

    def processar(self, autorizacao: Autorizacao) -> None:
        """Navega até a tela de SPSADT e executa o fluxo completo.

        Raises:
            SpsadtFalhouError: Se não for possível concluir o SPSADT.
        """
        ...

    def manter_sessao(self) -> None:
        """Executa ação de keep-alive para manter a sessão do portal ativa."""
        ...
