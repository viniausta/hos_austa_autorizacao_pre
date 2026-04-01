"""Cliente de callback para o CIB Seven (Camunda engine-rest)."""
import logging

import httpx

logger = logging.getLogger(__name__)


def enviar_callback(
    engine_rest_url: str,
    message_name: str,
    process_instance_id: str,
    resultado: dict,
) -> None:
    """Correlaciona mensagem no CIB Seven via POST /engine-rest/message.

    Args:
        engine_rest_url:     URL base do CIB Seven (ex: http://maezo:8080).
        message_name:        Nome da mensagem Camunda configurada no processo.
        process_instance_id: ID da instância para correlação.
        resultado:           Dicionário com status_retorno_tasy, mensagem, cod_guia, cod_requisicao.
    """
    # O BPMN do CIB Seven espera "AuthorizationCompleted" como messageName
    # (receiveTask com messageRef="Message_AuthCompleted")
    camunda_message_name = "AuthorizationCompleted"

    payload = {
        "messageName": camunda_message_name,
        "processInstanceId": process_instance_id,
        "processVariables": {
            "rpaStatus": {
                "value": str(resultado.get("status_retorno_tasy", "FALHA")),
                "type": "String",
            },
            "rpaProtocol": {
                "value": resultado.get("cod_requisicao", "") or resultado.get("cod_guia", ""),
                "type": "String",
            },
            "rpaMensagem": {
                "value": resultado.get("mensagem", ""),
                "type": "String",
            },
            "rpaCodGuia": {
                "value": resultado.get("cod_guia", ""),
                "type": "String",
            },
        },
    }

    url = f"{engine_rest_url.rstrip('/')}/engine-rest/message"
    logger.info("Callback CIB Seven — URL=%s | payload=%s", url, payload)

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=payload)
        if resp.status_code >= 400:
            logger.error(
                "Callback CIB Seven rejeitado — status=%s | body=%s",
                resp.status_code, resp.text,
            )
        resp.raise_for_status()

    logger.info(
        "Callback CIB Seven enviado — instance=%s | message=%s | status_http=%s",
        process_instance_id,
        message_name,
        resp.status_code,
    )
