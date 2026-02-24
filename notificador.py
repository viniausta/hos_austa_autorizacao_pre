"""
Módulo para envio de notificações.
Este módulo fornece uma interface simples para enviar mensagens e notificações.
"""

import json
import logging
import requests
from typing import Optional, Dict, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class CliqNotificador:
    """Gerenciador de notificações para o Zoho Cliq."""

    def __init__(self, webhook_url: str):
        """
        Inicializa o notificador do Cliq.

        Args:
            webhook_url (str): URL do webhook do canal do Cliq
                             Ex: https://cliq.zoho.com/api/v2/channelsbyname/{channel}/message
        """
        self.webhook_url = webhook_url
        self.headers = {
            "Content-Type": "application/json",
        }

    def enviar_mensagem(
        self,
        mensagem: str,
        titulo: Optional[str] = None,
        cor: Optional[str] = None
    ) -> bool:
        """
        Envia uma mensagem para o canal do Cliq.

        Args:
            mensagem (str): Texto da mensagem a ser enviada
            titulo (Optional[str], optional): Título da mensagem. Defaults to None.
            cor (Optional[str], optional): Cor da barra lateral da mensagem (hex ou nome da cor). 
                                        Defaults to None.

        Returns:
            bool: True se a mensagem foi enviada com sucesso, False caso contrário.

        Example:
            >>> notificador = CliqNotificador(webhook_url)
            >>> notificador.enviar_mensagem(
            ...     mensagem="Processamento concluído com sucesso!",
            ...     titulo="✅ Sucesso",
            ...     cor="#00ff00"
            ... )
        """
        try:
            payload = {
                "text": mensagem
            }

            if titulo:
                payload["card"] = {
                    "title": titulo,
                }
                if cor:
                    payload["card"]["theme"] = cor

            response = requests.post(
                self.webhook_url,
                headers=self.headers,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                logger.info("Mensagem enviada com sucesso para o Cliq")
                return True
            else:
                logger.error(
                    "Erro ao enviar mensagem para o Cliq. Status: %d, Resposta: %s",
                    response.status_code,
                    response.text
                )
                return False

        except Exception as e:
            logger.exception(
                "Erro ao enviar notificação para o Cliq: %s", str(e))
            return False

    def notificar_erro(
        self,
        erro: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None
    ) -> bool:
        """
        Envia uma notificação de erro formatada para o canal.

        Args:
            erro (str): Mensagem principal do erro
            detalhes (Optional[Union[str, Dict[str, Any]]], optional): Detalhes adicionais do erro. 
                                                                      Defaults to None.

        Returns:
            bool: True se a notificação foi enviada com sucesso, False caso contrário.

        Example:
            >>> notificador.notificar_erro(
            ...     erro="Falha no processamento do arquivo",
            ...     detalhes={"arquivo": "dados.csv", "linha": 42}
            ... )
        """
        mensagem = f"🚨 **ERRO**: {erro}\n\n"

        if detalhes:
            if isinstance(detalhes, dict):
                mensagem += "**Detalhes:**\n"
                for chave, valor in detalhes.items():
                    mensagem += f"- {chave}: {valor}\n"
            else:
                mensagem += f"**Detalhes:** {detalhes}"

        mensagem += f"\n⏰ Ocorrido em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return self.enviar_mensagem(
            mensagem=mensagem,
            titulo="❌ Erro Detectado",
            cor="#ff0000"
        )

    def notificar_sucesso(
        self,
        mensagem: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None
    ) -> bool:
        """
        Envia uma notificação de sucesso formatada para o canal.

        Args:
            mensagem (str): Mensagem principal de sucesso
            detalhes (Optional[Union[str, Dict[str, Any]]], optional): Detalhes adicionais. 
                                                                      Defaults to None.

        Returns:
            bool: True se a notificação foi enviada com sucesso, False caso contrário.

        Example:
            >>> notificador.notificar_sucesso(
            ...     mensagem="Processamento finalizado",
            ...     detalhes={"arquivos": 10, "tempo": "2min"}
            ... )
        """
        texto = f"✅ **SUCESSO**: {mensagem}\n\n"

        if detalhes:
            if isinstance(detalhes, dict):
                texto += "**Detalhes:**\n"
                for chave, valor in detalhes.items():
                    texto += f"- {chave}: {valor}\n"
            else:
                texto += f"**Detalhes:** {detalhes}"

        texto += f"\n⏰ Concluído em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return self.enviar_mensagem(
            mensagem=texto,
            titulo="✅ Operação Concluída",
            cor="#00ff00"
        )

    def notificar_alerta(
        self,
        mensagem: str,
        detalhes: Optional[Union[str, Dict[str, Any]]] = None
    ) -> bool:
        """
        Envia uma notificação de alerta formatada para o canal.

        Args:
            mensagem (str): Mensagem principal do alerta
            detalhes (Optional[Union[str, Dict[str, Any]]], optional): Detalhes adicionais. 
                                                                      Defaults to None.

        Returns:
            bool: True se a notificação foi enviada com sucesso, False caso contrário.

        Example:
            >>> notificador.notificar_alerta(
            ...     mensagem="Arquivos pendentes detectados",
            ...     detalhes="3 arquivos aguardando processamento"
            ... )
        """
        texto = f"⚠️ **ALERTA**: {mensagem}\n\n"

        if detalhes:
            if isinstance(detalhes, dict):
                texto += "**Detalhes:**\n"
                for chave, valor in detalhes.items():
                    texto += f"- {chave}: {valor}\n"
            else:
                texto += f"**Detalhes:** {detalhes}"

        texto += f"\n⏰ Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        return self.enviar_mensagem(
            mensagem=texto,
            titulo="⚠️ Alerta",
            cor="#ffa500"
        )
