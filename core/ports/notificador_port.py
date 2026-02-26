"""Porta de notificação — abstração para a camada de domínio.

Qualquer canal de notificação (Cliq, Teams, Slack, mock para testes)
deve satisfazer este Protocol para ser injetado no sistema.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, Union, runtime_checkable


@runtime_checkable
class NotificadorPort(Protocol):
    """Contrato de envio de notificações."""

    def enviar_mensagem(
        self,
        mensagem: str,
        titulo: Optional[str] = None,
        cor: Optional[str] = None,
    ) -> bool:
        """Envia mensagem genérica. Retorna True se enviada com sucesso."""
        ...

    def notificar_erro(
        self,
        erro: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> bool:
        """Envia notificação de erro formatada."""
        ...

    def notificar_sucesso(
        self,
        mensagem: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> bool:
        """Envia notificação de sucesso formatada."""
        ...

    def notificar_alerta(
        self,
        mensagem: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> bool:
        """Envia notificação de alerta formatada."""
        ...
