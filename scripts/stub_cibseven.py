"""Stub do CIB Seven para testes locais.

Simula o endpoint POST /engine-rest/message que o RPA chama ao terminar
a autorização. Armazena os callbacks em memória e os expõe via GET /callbacks.

Uso (via docker-compose.stub.yml — não execute diretamente):
    uvicorn stub_cibseven:app --host 0.0.0.0 --port 9000
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [STUB-CIB7] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Stub CIB Seven",
    description="Simula o endpoint /engine-rest/message para testes do RPA.",
    version="1.0.0",
)

# Armazena callbacks recebidos em memória
_callbacks: list[dict[str, Any]] = []


@app.post("/engine-rest/message", status_code=200)
async def receber_mensagem(request: Request) -> JSONResponse:
    """Recebe o callback do RPA e registra em memória."""
    body = await request.json()

    entry = {
        "received_at": datetime.now().isoformat(),
        "message_name": body.get("messageName"),
        "process_instance_id": (
            body.get("correlationKeys", {})
            .get("processInstanceId", {})
            .get("value")
        ),
        "variables": {
            k: v.get("value")
            for k, v in body.get("processVariables", {}).items()
        },
        "raw": body,
    }

    _callbacks.append(entry)

    logger.info(
        "✅ Callback recebido | message=%s | instance=%s | resultado=%s | guia=%s",
        entry["message_name"],
        entry["process_instance_id"],
        entry["variables"].get("resultado"),
        entry["variables"].get("cod_guia"),
    )

    return JSONResponse({"status": "ok", "message": "correlacionado"})


@app.get("/callbacks")
def listar_callbacks() -> list[dict[str, Any]]:
    """Lista todos os callbacks recebidos desde que o stub subiu."""
    return _callbacks


@app.get("/callbacks/ultimo")
def ultimo_callback() -> dict[str, Any]:
    """Retorna o callback mais recente."""
    if not _callbacks:
        return {"message": "nenhum callback recebido ainda"}
    return _callbacks[-1]


@app.delete("/callbacks")
def limpar_callbacks() -> dict[str, str]:
    """Limpa a lista de callbacks (útil entre testes)."""
    _callbacks.clear()
    return {"status": "limpo"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
