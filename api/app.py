"""FastAPI application — integração RPA com MAEZO (CIB Seven)."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from config.settings import Settings
from infrastructure.database.oracle_client import OracleClient
from infrastructure.notifications.cliq_notificador import CliqNotificador
from api.routes import autorizacao as rota_autorizacao

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Inicializa recursos compartilhados na subida e libera no encerramento."""
    config = Settings.from_env()
    db = OracleClient(config)

    notificador = None
    if all([
        config.zoho_client_id,
        config.zoho_client_secret,
        config.zoho_refresh_token,
        config.cliq_canal_normal,
        config.cliq_canal_erro,
    ]):
        notificador = CliqNotificador(
            client_id=config.zoho_client_id,
            client_secret=config.zoho_client_secret,
            refresh_token=config.zoho_refresh_token,
            canal_normal=config.cliq_canal_normal,
            canal_erro=config.cliq_canal_erro,
            dev_mode=config.dev_mode,
        )
        logger.info("Notificador Cliq ativo.")

    app.state.config = config
    app.state.db = db
    app.state.notificador = notificador

    logger.info(
        "API RPA iniciada — MAEZO_ENGINE_REST_URL=%s | DEV=%s",
        config.maezo_engine_rest_url,
        config.dev_mode,
    )
    yield

    db.close()
    logger.info("API RPA encerrada.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="RPA Autorizações PA — API",
        description="Integração com orquestrador MAEZO (CIB Seven). "
                    "Recebe solicitações de autorização, processa via Selenium no portal TASY "
                    "e retorna o resultado via callback Camunda.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(rota_autorizacao.router, prefix="/api/v1")

    @app.get("/health", tags=["infra"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
