"""Entry point do servidor FastAPI para integração com MAEZO (CIB Seven).

Uso:
    python api_server.py
    # ou via uvicorn diretamente:
    uvicorn api.app:app --host 0.0.0.0 --port 8000
"""
import os
import sys

import uvicorn

from monitoring.logger_config import logger


def main() -> None:
    port = int(os.environ.get("API_PORT", "8000"))
    logger.info("Iniciando servidor API na porta %d", port)
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_config=None,  # mantém o logger_config.py do projeto
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
