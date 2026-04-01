"""Endpoint POST /api/v1/authorize — recebe solicitação e dispara processamento em background."""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request

from api.schemas import AutorizacaoFhirRequest, AutorizacaoAceita
from api.services.processador import processar_autorizacao

logger = logging.getLogger(__name__)

router = APIRouter()

# Pool de threads dedicado ao processamento Selenium (operações bloqueantes)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rpa-worker")


@router.post("/authorize", status_code=202, response_model=AutorizacaoAceita)
async def autorizar(payload: AutorizacaoFhirRequest, request: Request) -> AutorizacaoAceita:
    """Aceita a solicitação de autorização imediatamente (202) e processa em background.

    Recebe payload FHIR-inspired com todos os dados do atendimento.
    O RPA usa esses dados para preencher o portal Unimed sem consultar Oracle.
    O resultado é enviado de volta ao CIB Seven via POST /engine-rest/message.
    """
    config = request.app.state.config

    logger.info(
        "API/FHIR: autorização recebida — NrAtend=%s | NrSeq=%s | instance=%s",
        payload.atendimento.nr_atendimento,
        payload.atendimento.nr_sequencia,
        payload.process_instance_id,
    )

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        processar_autorizacao,
        payload,
        config,
    )

    return AutorizacaoAceita(status="accepted", nr_sequencia=payload.atendimento.nr_sequencia)
