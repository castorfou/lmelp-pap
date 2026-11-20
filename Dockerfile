# Image de l'appli lmelp-pap : ghcr.io/castorfou/lmelp-pap
#
# Sert l'appli web (lmelp-pap arbitrer) sur le port PAP_PORT. Les données
# vivent dans le volume /data : cache/ (cache des sources), processed/ (CSV de
# la liste et arbitrages), audios/, logs/. Sur le NAS :
# /volume1/docker/lmelp/pap → /data. Les fichiers créés appartiennent à
# PUID:PGID (défaut 1000:1000, 1027:1027 sur le NAS), comme dans le reste de la
# stack lmelp.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
# Paquet installé dans le venv (gabarits HTML compris), sans dépendances de dev.
RUN uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gosu \
    && rm -rf /var/lib/apt/lists/*

ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd -g "$APP_GID" appuser \
    && useradd -u "$APP_UID" -g appuser -m -d /home/appuser -s /bin/bash appuser

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Chromium de Playwright, pour la collecte du catalogue INA.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /var/lib/apt/lists/*

ENV PAP_HOTE=0.0.0.0 \
    PAP_PORT=8090 \
    PAP_CACHE=/data/cache \
    PAP_DONNEES=/data/processed \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data/cache /data/processed /data/audios /data/logs \
    && chown -R appuser:appuser /data
VOLUME ["/data"]

# Le conteneur démarre en root : l'entrypoint remappe appuser sur PUID/PGID
# (1027 sur le NAS), reprend la propriété de /data, puis passe en appuser.
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f "http://localhost:${PAP_PORT}/health" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["lmelp-pap", "arbitrer", "--sans-navigateur"]
