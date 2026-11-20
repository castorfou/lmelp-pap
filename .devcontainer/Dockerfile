FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Supprimer la source Yarn cassée héritée de l'image de base
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    /usr/share/keyrings/yarnkey.gpg \
    /etc/apt/sources.list.d/yarn.list.save 2>/dev/null || true

# Bibliothèques système du Chromium de Playwright (captures et tests de pages HTML).
# Liste de `playwright install-deps chromium` pour Debian bookworm ; les binaires du
# navigateur restent dans ~/.cache/ms-playwright (HOME persistant).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcairo2 libcups2 \
    libdbus-1-3 libdrm2 libgbm1 libglib2.0-0 libnspr4 libnss3 libpango-1.0-0 \
    libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 \
    libxrandr2 xvfb fonts-noto-color-emoji fonts-unifont libfontconfig1 libfreetype6 \
    xfonts-scalable fonts-liberation fonts-ipafont-gothic fonts-wqy-zenhei \
    fonts-tlwg-loma-otf fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# Créer le répertoire cache avec les bons droits avant le montage du volume uv
# Sans ça, Docker crée /home/vscode/.cache en root lors du mount, ce qui bloque pre-commit
RUN mkdir -p /home/vscode/.cache && chown vscode:vscode /home/vscode/.cache
