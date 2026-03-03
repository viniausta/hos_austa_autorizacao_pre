"""Notificador Zoho Cliq — implementação concreta de NotificadorPort.

Envia mensagens para canais do Zoho Cliq via webhook.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Union

import requests

logger = logging.getLogger(__name__)


class CliqNotificador:
    """Gerenciador de notificações para o Zoho Cliq via webhook."""

    def __init__(self, webhook_url: str, timeout: int = 10) -> None:
        """
        Args:
            webhook_url: URL do webhook do canal do Cliq.
            timeout: Timeout em segundos para as requisições HTTP.
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
        self._headers = {"Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # NotificadorPort — implementação
    # ------------------------------------------------------------------

    def enviar_mensagem(
        self,
        mensagem: str,
        titulo: Optional[str] = None,
        cor: Optional[str] = None,
    ) -> bool:
        """Envia mensagem genérica para o canal.

        Returns:
            True se enviada com sucesso (HTTP 200), False caso contrário.
        """
        payload: Dict[str, Any] = {"text": mensagem}

        if titulo:
            payload["card"] = {"title": titulo}
            if cor:
                payload["card"]["theme"] = cor

        try:
            response = requests.post(
                self.webhook_url,
                headers=self._headers,
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                logger.debug("Mensagem enviada ao Cliq com sucesso.")
                return True

            logger.error(
                "Erro ao enviar ao Cliq: HTTP %d — %s",
                response.status_code,
                response.text,
            )
            return False

        except requests.RequestException as e:
            logger.exception("Falha na requisição ao Cliq: %s", e)
            return False

    def notificar_erro(
        self,
        erro: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> bool:
        """Envia notificação de erro formatada."""
        mensagem = f"🚨 **ERRO**: {erro}\n\n"
        mensagem += self._formatar_detalhes(detalhes)
        mensagem += f"\n⏰ Ocorrido em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self.enviar_mensagem(mensagem, titulo="❌ Erro Detectado", cor="#ff0000")

    def notificar_sucesso(
        self,
        mensagem: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> bool:
        """Envia notificação de sucesso formatada."""
        texto = f"✅ **SUCESSO**: {mensagem}\n\n"
        texto += self._formatar_detalhes(detalhes)
        texto += f"\n⏰ Concluído em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self.enviar_mensagem(texto, titulo="✅ Operação Concluída", cor="#00ff00")

    def notificar_alerta(
        self,
        mensagem: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> bool:
        """Envia notificação de alerta formatada."""
        texto = f"⚠️ **ALERTA**: {mensagem}\n\n"
        texto += self._formatar_detalhes(detalhes)
        texto += f"\n⏰ Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self.enviar_mensagem(texto, titulo="⚠️ Alerta", cor="#ffa500")

    # ------------------------------------------------------------------
    # Utilitários internos
    # ------------------------------------------------------------------

    @staticmethod
    def _formatar_detalhes(
        detalhes: Optional[Union[str, Dict[str, Any]]]
    ) -> str:
        if not detalhes:
            return ""
        if isinstance(detalhes, dict):
            linhas = "\n".join(f"- {k}: {v}" for k, v in detalhes.items())
            return f"**Detalhes:**\n{linhas}\n"
        return f"**Detalhes:** {detalhes}\n"
