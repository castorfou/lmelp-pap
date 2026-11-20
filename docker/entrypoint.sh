#!/bin/bash
# Entrypoint de l'image lmelp-pap : remap de l'utilisateur non-root vers
# PUID/PGID, sur le modèle du backend de back-office-lmelp. L'image publiée
# sur ghcr.io sert sur des machines différentes (UID 1000 sur un poste, 1027
# sur le NAS) : le propriétaire des fichiers de /data se règle à l'exécution.
set -e

if [ "$(id -u)" = "0" ]; then
    PUID=${PUID:-1000}
    PGID=${PGID:-1000}
    if [ "$PUID" != "$(id -u appuser)" ] || [ "$PGID" != "$(id -g appuser)" ]; then
        groupmod -o -g "$PGID" appuser
        usermod -o -u "$PUID" appuser
    fi
    # chown -R à chaque démarrage : reprend aussi les fichiers d'un
    # déploiement précédent créés sous un autre propriétaire.
    mkdir -p /data/cache /data/processed /data/audios /data/logs
    chown -R "$PUID:$PGID" /data
    exec gosu appuser "$0" "$@"
fi

exec "$@"
