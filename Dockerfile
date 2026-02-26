# =============================================================================
# Dockerfile — hos_austa_autorizacaopre
#
# Imagem baseada em Python slim (Linux).
# O navegador NÃO roda aqui — o projeto conecta ao container Selenium via
# Remote WebDriver (veja docker-compose.yml).
# =============================================================================

FROM python:3.13-slim

# ---------------------------------------------------------------------------
# Metadados
# ---------------------------------------------------------------------------
LABEL maintainer="Austa RPA Team"
LABEL description="Robô RPA de autorização pré-hospitalar — Unimed PA"

# ---------------------------------------------------------------------------
# Variáveis de build
# ---------------------------------------------------------------------------
ARG APP_DIR=/app
ARG APP_USER=rpauser

WORKDIR ${APP_DIR}

# ---------------------------------------------------------------------------
# Dependências do sistema operacional
#   libaio1  → necessário para Oracle Client em modo thick (fallback)
#   curl     → healthcheck e utilitários
# ---------------------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libaio1 \
       curl \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Dependências Python
# Copiado separado do código para aproveitar cache de layers do Docker.
# Rebuilds por mudança de código não reinstalam dependências.
# ---------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Código da aplicação
# ---------------------------------------------------------------------------
COPY . .

# ---------------------------------------------------------------------------
# Usuário não-root (boas práticas de segurança em containers)
# ---------------------------------------------------------------------------
RUN useradd --create-home --shell /bin/bash ${APP_USER} \
    && chown -R ${APP_USER}:${APP_USER} ${APP_DIR}

USER ${APP_USER}

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
CMD ["python", "main.py"]
