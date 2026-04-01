"""Notificador Zoho Cliq — implementação concreta de NotificadorPort.

Autentica via OAuth2 (refresh token → access token) e envia mensagens
para canais do Zoho Cliq usando a API REST oficial.

Comportamento alinhado ao IBM RPA Funcao_EnviarMensagemCliq:
- Erros são roteados para canal dedicado (canal_erro).
- Demais notificações vão para o canal normal (canal_normal).
- Em DEV mode, o envio é suprimido completamente.
- Implementa backoff exponencial para evitar rate limiting.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Union

import requests

logger = logging.getLogger(__name__)

_ZOHO_ACCOUNTS_URL = "https://accounts.zoho.com"
_CLIQ_API_URL = "https://cliq.zoho.com/api/v2"


class CliqNotificador:
    """Gerenciador de notificações para o Zoho Cliq via API OAuth2."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        canal_normal: str,
        canal_erro: str,
        dev_mode: bool = False,
        timeout: int = 10,
    ) -> None:
        """
        Args:
            client_id: Client ID do app Zoho OAuth2.
            client_secret: Client Secret do app Zoho OAuth2.
            refresh_token: Refresh Token OAuth2 (longa duração).
            canal_normal: Chat ID do Cliq para mensagens normais/alertas/sucesso.
            canal_erro: Chat ID do Cliq para mensagens de erro.
            dev_mode: Se True, suprime todos os envios (sem notificação).
            timeout: Timeout em segundos para as requisições HTTP.
        """
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._canal_normal = canal_normal
        self._canal_erro = canal_erro
        self._dev_mode = dev_mode
        self._timeout = timeout
        self._access_token: Optional[str] = None

    # ------------------------------------------------------------------
    # NotificadorPort — implementação
    # ------------------------------------------------------------------

    def enviar_mensagem(
        self,
        mensagem: str,
        titulo: Optional[str] = None,
        cor: Optional[str] = None,
    ) -> bool:
        """Envia mensagem genérica para o canal normal."""
        return self._enviar_para_canal(self._canal_normal, mensagem)

    def notificar_erro(
        self,
        erro: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> bool:
        """Envia notificação de erro para o canal de erros."""
        mensagem = f"🚨 *ERRO*: {erro}\n\n"
        mensagem += self._formatar_detalhes(detalhes)
        mensagem += f"\n⏰ Ocorrido em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self._enviar_para_canal(self._canal_erro, mensagem)

    def notificar_sucesso(
        self,
        mensagem: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> bool:
        """Envia notificação de sucesso para o canal normal."""
        texto = f"✅ *SUCESSO*: {mensagem}\n\n"
        texto += self._formatar_detalhes(detalhes)
        texto += f"\n⏰ Concluído em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self._enviar_para_canal(self._canal_normal, texto)

    def notificar_alerta(
        self,
        mensagem: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> bool:
        """Envia notificação de alerta para o canal normal."""
        texto = f"⚠️ *ALERTA*: {mensagem}\n\n"
        texto += self._formatar_detalhes(detalhes)
        texto += f"\n⏰ Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self._enviar_para_canal(self._canal_normal, texto)

    # ------------------------------------------------------------------
    # Autenticação OAuth2 (Refresh Token → Access Token)
    # ------------------------------------------------------------------

    def _refresh_access_token(self) -> bool:
        """Obtém novo access token usando o refresh token com backoff exponencial.

        Implementa retry automático com backoff para evitar rate limiting (HTTP 400).
        """
        url = f"{_ZOHO_ACCOUNTS_URL}/oauth/v2/token"
        data = {
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "refresh_token",
        }
        max_retry = 3
        delay = 1  # Início em 1 segundo

        for tentativa in range(1, max_retry + 1):
            try:
                response = requests.post(url, data=data, timeout=self._timeout)
                if response.status_code == 200:
                    token = response.json().get("access_token")
                    if token:
                        self._access_token = token
                        logger.debug("Access token Zoho atualizado com sucesso.")
                        return True
                    logger.error("Resposta OAuth sem access_token: %s", response.text)
                elif response.status_code == 400 and tentativa < max_retry:
                    # Rate limiting — espera e tenta novamente
                    logger.warning(
                        "Rate limit Zoho (HTTP 400) — tentativa %d/%d, aguardando %ds...",
                        tentativa,
                        max_retry,
                        delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, 30)  # Exponencial, máximo 30s
                    continue
                else:
                    logger.error(
                        "Erro ao obter access token: HTTP %d — %s (tentativa %d/%d)",
                        response.status_code,
                        response.text[:100],
                        tentativa,
                        max_retry,
                    )
            except requests.RequestException as e:
                logger.warning(
                    "Falha na requisição de refresh token (tentativa %d/%d): %s",
                    tentativa,
                    max_retry,
                    str(e)[:100],
                )
                if tentativa < max_retry:
                    time.sleep(delay)
                    delay = min(delay * 2, 30)

        self._access_token = None
        return False

    # ------------------------------------------------------------------
    # Envio para canal (equivale ao sub EnviarMensagem do IBM RPA)
    # ------------------------------------------------------------------

    def _enviar_para_canal(self, canal_id: str, mensagem: str) -> bool:
        """Autentica via OAuth2 e envia mensagem para o canal especificado.

        Em DEV mode, suprime o envio e retorna True silenciosamente
        (comportamento idêntico ao IBM RPA: 'Parâmetro DEV - Não notifica Cliq').
        """
        if self._dev_mode:
            logger.info("DEV mode ativo — notificação ao Cliq suprimida.")
            return True

        if not self._refresh_access_token():
            logger.error(
                "Não foi possível obter o access token. Notificação cancelada."
            )
            return False

        url = f"{_CLIQ_API_URL}/chats/{canal_id}/message"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self._access_token}",
        }
        payload = {"text": mensagem}

        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=self._timeout
            )
            if response.status_code in (200, 204):
                logger.debug(
                    "Mensagem enviada ao Cliq (canal %s) com sucesso.", canal_id
                )
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
            return f"*Detalhes:*\n{linhas}\n"
        return f"*Detalhes:* {detalhes}\n"
