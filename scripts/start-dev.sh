#!/bin/bash
# Démarrage et arrêt du serveur local de pap (lmelp-pap arbitrer).
#
# Usage : scripts/start-dev.sh [--restart|--stop|--status] [-- options d'arbitrer]
#   (rien)     démarre le serveur au premier plan ; Ctrl+C l'arrête
#   --restart  arrête le serveur précédent, puis démarre
#   --stop     arrête le serveur précédent et quitte
#   --status   décrit le serveur actif (code 1 s'il n'y en a pas)
#   -- …       options passées telles quelles à `lmelp-pap arbitrer`
#
# Port : PAP_PORT s'il est défini (démarrage refusé s'il est pris) ; sinon le
# premier port libre de la plage PAP_PLAGE_PORTS (8765-8799).
#
# Le serveur démarré est décrit dans .dev-ports.json (pid, port, url, commit) :
# --stop, --restart et --status le relisent. Un serveur pap absent du fichier
# (lancé à la main, ou par un second démarrage) est retrouvé par son port.
#
# Variables : PAP_PORT, PAP_PLAGE_PORTS, PAP_HOTE (127.0.0.1), PAP_DEV_PORTS
# (chemin du fichier), et les PAP_* lues par lmelp-pap (PAP_CACHE…).

set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FICHIER="${PAP_DEV_PORTS:-$RACINE/.dev-ports.json}"
HOTE="${PAP_HOTE:-127.0.0.1}"
if [[ -n "${PAP_PORT:-}" ]]; then
    PORTS=("$PAP_PORT")
else
    PLAGE="${PAP_PLAGE_PORTS:-8765-8799}"
    mapfile -t PORTS < <(seq "${PLAGE%-*}" "${PLAGE#*-}")
fi
PORT=""
URL=""
ATTENTE_DEMARRAGE=60

VERT='\033[0;32m'
JAUNE='\033[1;33m'
ROUGE='\033[0;31m'
NC='\033[0m'

log() { echo -e "${VERT}[$(date +'%H:%M:%S')] $1${NC}"; }
warn() { echo -e "${JAUNE}[$(date +'%H:%M:%S')] attention : $1${NC}"; }
erreur() { echo -e "${ROUGE}[$(date +'%H:%M:%S')] erreur : $1${NC}" >&2; }

usage() {
    echo "Usage : $0 [--restart|--stop|--status] [-- options de lmelp-pap arbitrer]"
}

# Un champ de l'entrée « pap » du fichier, vide si absent.
champ() {
    [[ -f "$FICHIER" ]] || return 0
    python3 - "$FICHIER" "$1" <<'EOF' 2>/dev/null || true
import json, sys
print(json.load(open(sys.argv[1])).get("pap", {}).get(sys.argv[2], ""))
EOF
}

ecrire_fichier() {
    local pid="$1"
    python3 - "$FICHIER" "$pid" "$PORT" "$HOTE" "$URL" \
        "$(git -C "$RACINE" rev-parse --short HEAD 2>/dev/null || echo inconnu)" \
        "$(git -C "$RACINE" branch --show-current 2>/dev/null || echo inconnue)" <<'EOF'
import json, sys, time
fichier, pid, port, hote, url, commit, branche = sys.argv[1:]
pap = {"pid": int(pid), "port": int(port), "host": hote, "url": url,
       "started_at": time.time(), "commit": commit, "branche": branche}
with open(fichier, "w") as f:
    json.dump({"pap": pap}, f, indent=2)
EOF
}

vivant() { [[ -n "$1" ]] && kill -0 "$1" 2>/dev/null; }

# Le pid qui écoute sur un port, vide s'il n'y en a pas.
pid_du_port() {
    ss -ltnpH "sport = :$1" 2>/dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2 || true
}

port_occupe() { [[ -n "$(ss -ltnH "sport = :$1" 2>/dev/null)" ]]; }

est_pap() { ps -o args= -p "$1" 2>/dev/null | grep -q "lmelp-pap arbitrer"; }

# Les serveurs pap qui écoutent sur un port de PORTS : « port pid » par ligne.
paps_actifs() {
    local port pid
    for port in "${PORTS[@]}"; do
        pid=$(pid_du_port "$port")
        if [[ -n "$pid" ]] && est_pap "$pid"; then
            echo "$port $pid"
        fi
    done
}

# Arrête un serveur et tout son groupe de processus (uv run et python) :
# SIGTERM, puis SIGKILL s'il ne répond pas. Pas de SIGINT : bash fait ignorer
# SIGINT aux processus qu'un script lance en fond.
arreter_groupe() {
    local pid="$1" nom="$2" groupe signal attente
    groupe=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
    for signal in TERM KILL; do
        vivant "$pid" || break
        if [[ -n "$groupe" && "$groupe" != "$(ps -o pgid= -p $$ | tr -d ' ')" ]]; then
            kill -"$signal" -- -"$groupe" 2>/dev/null || true
        else
            kill -"$signal" "$pid" 2>/dev/null || true
        fi
        if [[ "$signal" == TERM ]]; then
            log "arrêt de $nom (pid $pid, groupe ${groupe:-?})"
        else
            warn "$nom ne répond pas, SIG$signal"
        fi
        for attente in $(seq 20); do
            vivant "$pid" || break
            sleep 0.5
        done
    done
}

arreter_precedent() {
    local pid
    pid=$(champ pid)
    if vivant "$pid"; then
        arreter_groupe "$pid" "pap"
    fi
    # Les serveurs pap absents du fichier, retrouvés par leur port.
    local port
    while read -r port pid; do
        warn "serveur pap absent de $(basename "$FICHIER") sur le port $port (pid $pid)"
        arreter_groupe "$pid" "pap du port $port"
    done < <(paps_actifs)
    rm -f "$FICHIER"
}

statut() {
    local pid
    pid=$(champ pid)
    local autres
    autres=$(paps_actifs | awk -v p="$(champ port)" -v f="$pid" '$1 != p || $2 != f')
    if [[ -n "$autres" ]]; then
        while read -r port_autre pid_autre; do
            echo "pap sur le port $port_autre (pid $pid_autre), absent de $(basename "$FICHIER")"
        done <<<"$autres"
    fi
    if ! vivant "$pid"; then
        if [[ -z "$autres" ]]; then
            echo "aucun serveur pap actif (voir $0)"
            return 1
        fi
        return 0
    fi
    local commit depuis sante
    commit=$(champ commit)
    depuis=$(python3 -c "import time; print(int(time.time() - $(champ started_at)) // 60)")
    sante=$(curl -s -o /dev/null -w '%{http_code}' "$(champ url)/health" || true)
    echo "pap actif : $(champ url)"
    echo "  pid $pid, démarré il y a $depuis min, /health : $sante"
    echo "  code : $(champ branche) @ $commit"
    local tete
    tete=$(git -C "$RACINE" rev-parse --short HEAD 2>/dev/null || true)
    if [[ -n "$tete" && "$tete" != "$commit" ]]; then
        echo "  le dépôt est maintenant à $tete : $0 --restart pour servir ce code"
    fi
    if [[ -n "$(git -C "$RACINE" status --porcelain -- src 2>/dev/null)" ]]; then
        echo "  src/ a des modifications non commitées : le serveur les a peut-être ou pas"
    fi
}

# Les adresses du serveur : locale, puis réseau quand il écoute sur toutes
# les interfaces (PAP_HOTE=0.0.0.0).
liens() {
    echo
    echo "  ➜  Accueil : $URL/"
    echo "  ➜  Liste :   $URL/liste"
    echo "  ➜  Santé :   $URL/health"
    if [[ "$HOTE" == 0.0.0.0 ]]; then
        local ip
        for ip in $(hostname -I 2>/dev/null); do
            [[ "$ip" == *:* ]] && continue  # IPv6
            echo "  ➜  Réseau :  http://$ip:$PORT/"
        done
    else
        echo "  ➜  Réseau :  PAP_HOTE=0.0.0.0 pour exposer pap au-delà de $HOTE"
    fi
    echo
}

ACTION=demarrer
OPTIONS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --restart) ACTION=redemarrer ;;
        --stop) ACTION=arreter ;;
        --status) ACTION=statut ;;
        --) shift; OPTIONS=("$@"); break ;;
        -h|--help) usage; exit 0 ;;
        *) erreur "argument inconnu : $1"; usage; exit 1 ;;
    esac
    shift
done

case "$ACTION" in
    arreter) arreter_precedent; log "serveur pap arrêté"; exit 0 ;;
    statut) statut; exit $? ;;
    redemarrer) arreter_precedent ;;
esac

for candidat in "${PORTS[@]}"; do
    if ! port_occupe "$candidat"; then
        PORT="$candidat"
        break
    fi
done
if [[ -z "$PORT" ]]; then
    if [[ ${#PORTS[@]} -eq 1 ]]; then
        erreur "le port ${PORTS[0]} est déjà pris (pid $(pid_du_port "${PORTS[0]}")) : $0 --restart pour remplacer le serveur"
    else
        erreur "aucun port libre de ${PORTS[0]} à ${PORTS[-1]} : $0 --restart pour remplacer le serveur"
    fi
    exit 1
fi
URL="http://localhost:$PORT"
deja=$(paps_actifs | awk '{printf "%s port %s (pid %s)", (NR > 1 ? "," : ""), $1, $2}')
if [[ -n "$deja" ]]; then
    warn "un autre serveur pap tourne déjà :$deja. Les deux écrivent les mêmes CSV et la même base Mongo ; $0 --restart pour le remplacer"
fi

SERVEUR=""
nettoyer() {
    trap - INT TERM HUP
    if vivant "$SERVEUR"; then
        arreter_groupe "$SERVEUR" "pap"
    fi
    # Le fichier n'est retiré que s'il décrit encore ce serveur (un --restart
    # lancé ailleurs a pu le réécrire) et que celui-ci est bien mort.
    if [[ "$(champ pid)" == "$SERVEUR" ]] && ! vivant "$SERVEUR"; then
        rm -f "$FICHIER"
    fi
    log "terminé"
    exit 0
}
# SIGHUP aussi : sans lui, un script lancé en fond par un shell qui se ferme
# mourrait sans arrêter le serveur.
trap nettoyer INT TERM HUP

cd "$RACINE"
log "démarrage de pap sur $HOTE:$PORT…"
# setsid : le serveur a son propre groupe de processus, qu'arreter_groupe
# arrête d'un coup sans toucher au shell appelant.
PAP_PORT="$PORT" PAP_HOTE="$HOTE" setsid uv run --active lmelp-pap arbitrer \
    --sans-navigateur "${OPTIONS[@]}" &
SERVEUR=$!

for _ in $(seq $((ATTENTE_DEMARRAGE * 2))); do
    vivant "$SERVEUR" || break
    [[ "$(curl -s -o /dev/null -w '%{http_code}' "$URL/health" || true)" == 200 ]] && break
    sleep 0.5
done
if ! vivant "$SERVEUR"; then
    erreur "le serveur s'est arrêté au démarrage (voir ses logs ci-dessus)"
    exit 1
fi
ecrire_fichier "$SERVEUR"
log "pap prêt (pid $SERVEUR, décrit dans $FICHIER)"
liens
log "Ctrl+C ou $0 --stop pour l'arrêter"

set +e
wait "$SERVEUR"
code=$?
# Arrêté de l'extérieur (--stop, --restart) ou de lui-même : le fichier n'est
# retiré que s'il le décrit encore.
[[ "$(champ pid)" == "$SERVEUR" ]] && rm -f "$FICHIER"
log "le serveur s'est arrêté (code $code)"
# 143 : arrêté par SIGTERM (--stop, --restart), un arrêt normal.
[[ "$code" == 143 ]] && code=0
exit "$code"
