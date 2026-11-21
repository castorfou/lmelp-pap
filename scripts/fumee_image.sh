#!/usr/bin/env bash
# Test de fumée d'une image lmelp-pap : démarre l'image telle qu'elle partira en
# production et interroge ses routes.
#
#   scripts/fumee_image.sh <image>      # ex. scripts/fumee_image.sh lmelp-pap:test
#
# Deux conteneurs de l'image tournent sur un réseau Docker dédié :
# - « avec base » : MONGO_URI pointe sur un conteneur mongo à côté ;
#   /health, /, /liste, /api/donnees répondent 200 et /api/donnees porte
#   maturite_active ;
# - « sans base » : sans MONGO_URI, POST /api/verifications répond 503.
#
# Chaque contrôle écrit une ligne « OK|ÉCHEC <conteneur> <méthode> <route> <statut> ».
# Code de sortie 0 si tout passe, 1 sinon (avec les logs des conteneurs).
set -uo pipefail

if [ $# -ne 1 ]; then
    echo "usage : $0 <image>" >&2
    exit 2
fi
IMAGE=$1
MONGO_IMAGE=${MONGO_IMAGE:-mongo:7}
DELAI=${FUMEE_DELAI:-180}   # secondes d'attente de /health
ID="fumee-$$"
RESEAU="$ID"
MONGO="$ID-mongo"
AVEC="$ID-avec-base"
SANS="$ID-sans-base"
echecs=0

nettoyer() {
    docker rm -f "$AVEC" "$SANS" "$MONGO" >/dev/null 2>&1
    docker network rm "$RESEAU" >/dev/null 2>&1
}
trap nettoyer EXIT

# Requête depuis l'intérieur du conteneur (l'image embarque curl) : aucun port
# publié sur l'hôte, pas de conflit entre deux fumées.
requete() {  # conteneur méthode route -> corps puis statut sur la dernière ligne
    docker exec "$1" curl -sS -o - -w '\n%{http_code}' -X "$2" \
        "http://localhost:8090$3" 2>/dev/null
}

controler() {  # conteneur méthode route statut_attendu [motif_du_corps]
    local conteneur=$1 methode=$2 route=$3 attendu=$4 motif=${5:-}
    local reponse statut corps nom=${1#"$ID-"}
    reponse=$(requete "$conteneur" "$methode" "$route")
    statut=$(tail -n1 <<<"$reponse")
    corps=$(sed '$d' <<<"$reponse")
    if [ "$statut" != "$attendu" ]; then
        [ "$statut" = 000 ] && statut="000 pas de réponse"
        echo "ÉCHEC $nom $methode $route $statut (attendu $attendu)"
        echecs=$((echecs + 1))
    elif [ -n "$motif" ] && ! grep -q "$motif" <<<"$corps"; then
        echo "ÉCHEC $nom $methode $route $statut (corps sans $motif)"
        echecs=$((echecs + 1))
    else
        echo "OK    $nom $methode $route $statut${motif:+ ($motif)}"
    fi
}

attendre_sante() {  # conteneur
    local nom=${1#"$ID-"} debut=$SECONDS
    while [ $((SECONDS - debut)) -lt "$DELAI" ]; do
        if [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" != true ]; then
            echo "ÉCHEC $nom s'est arrêté au démarrage"
            return 1
        fi
        if [ "$(requete "$1" GET /health | tail -n1)" = 200 ]; then
            echo "OK    $nom démarré en $((SECONDS - debut)) s"
            return 0
        fi
        sleep 2
    done
    echo "ÉCHEC $nom ne répond pas sur /health après $DELAI s"
    return 1
}

echo "Fumée de l'image $IMAGE"
docker network create "$RESEAU" >/dev/null
docker run -d -q --name "$MONGO" --network "$RESEAU" "$MONGO_IMAGE" >/dev/null
docker run -d --name "$AVEC" --network "$RESEAU" \
    -e MONGO_URI="mongodb://$MONGO:27017" -e MONGO_DB=fumee "$IMAGE" >/dev/null
docker run -d --name "$SANS" --network "$RESEAU" "$IMAGE" >/dev/null

for conteneur in "$AVEC" "$SANS"; do
    attendre_sante "$conteneur" || echecs=$((echecs + 1))
done

if [ "$echecs" -eq 0 ]; then
    controler "$AVEC" GET /health 200 '"status": "ok"'
    controler "$AVEC" GET / 200 '<html'
    controler "$AVEC" GET /liste 200 '<html'
    controler "$AVEC" GET /api/donnees 200 '"maturite_active": true'
    controler "$SANS" GET / 200 '<html'
    controler "$SANS" POST /api/verifications 503 'MONGO_URI'
fi

if [ "$echecs" -ne 0 ]; then
    for conteneur in "$AVEC" "$SANS"; do
        echo "--- logs de ${conteneur#"$ID-"} ---"
        docker logs --tail 50 "$conteneur" 2>&1
    done
    echo "Fumée en échec : $echecs contrôle(s) KO"
    exit 1
fi
echo "Fumée réussie"
