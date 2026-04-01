# =============================================================================
# Dockerfile — hos_austa_autorizacaopre  (multi-stage build)
#
# Stage 1 — oracle-base
#   Baixa e instala o Oracle Instant Client UMA única vez.
#   Cacheado pelo Docker: só rebuilda se este stage mudar
#   (ex: atualizar versão do IC). Deploy de código não toca aqui.
#
# Stage 2 — app
#   Herda o IC do stage anterior, instala deps Python e copia o código.
#   É o único stage que rebuilda a cada mudança de código.
# =============================================================================


# -----------------------------------------------------------------------------
# Stage 1 — oracle-base: Python + Oracle Instant Client (layer permanente)
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS oracle-base

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libaio1t64 \
       wget \
       unzip \
    && wget -q \
       "https://download.oracle.com/otn_software/linux/instantclient/2111000/instantclient-basiclite-linux.x64-21.11.0.0.0dbru.zip" \
       -O /tmp/instantclient.zip \
    && unzip /tmp/instantclient.zip -d /opt/oracle \
    && rm /tmp/instantclient.zip \
    && echo /opt/oracle/instantclient_21_11 > /etc/ld.so.conf.d/oracle-instantclient.conf \
    && ldconfig \
    && ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1 \
    && rm -rf /var/lib/apt/lists/*


# -----------------------------------------------------------------------------
# Stage 2 — app: dependências Python + código (rebuilda a cada deploy)
# -----------------------------------------------------------------------------
FROM oracle-base AS app

LABEL maintainer="Austa RPA Team"
LABEL description="Robô RPA de autorização pré-hospitalar — Unimed PA"

ARG APP_DIR=/app
ARG APP_USER=rpauser

WORKDIR ${APP_DIR}

# curl para healthchecks e utilitários
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# requirements separado do código para cache de layer:
# se só o código mudar, pip install é pulado
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY . .

# Cria pasta de storage do Tasy com permissão para escrita
RUN mkdir -p /mnt/tasy-storage/anexo_opme \
    && chmod 777 /mnt/tasy-storage/anexo_opme

# Usuário não-root
RUN useradd --create-home --shell /bin/bash ${APP_USER} \
    && chown -R ${APP_USER}:${APP_USER} ${APP_DIR}

USER ${APP_USER}

CMD ["python", "main.py"]
