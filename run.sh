#!/usr/bin/env bash
# Lance YT Album (Linux) : http://127.0.0.1:5123
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"
STAMP="$VENV/.last-update"
export PORT="${PORT:-5123}"

# Propose d'installer un paquet systeme via apt (Ubuntu/Debian), sinon explique quoi faire
need_pkg() {  # $1 = paquet(s), $2 = description
    echo "$2 manquant (paquet : $1)."
    if command -v apt-get >/dev/null; then
        read -rp "L'installer maintenant avec sudo apt ? [O/n] " r
        [[ "$r" =~ ^[nN] ]] && exit 1
        sudo apt-get install -y $1
    else
        echo "Installe-le avec le gestionnaire de paquets de ta distribution, puis relance."
        exit 1
    fi
}

command -v python3 >/dev/null || need_pkg "python3 python3-venv" "Python 3"
command -v ffmpeg >/dev/null || need_pkg ffmpeg "ffmpeg"

# === Environnement Python isole (.venv) ===
if [[ ! -x "$VENV/bin/pip" ]]; then
    echo "Premiere installation..."
    rm -rf "$VENV"
    if ! python3 -m venv "$VENV" 2>/dev/null; then
        rm -rf "$VENV"  # venv a moitie cree sans pip
        need_pkg python3-venv "Le module venv de Python"
        python3 -m venv "$VENV"
    fi
fi

# === Mise a jour de l'app depuis GitHub (redemarre sur la nouvelle version) ===
if [[ -z "${YTA_UPDATED:-}" ]]; then
    rc=0; "$VENV/bin/python" "$DIR/update.py" || rc=$?
    [[ $rc -eq 3 ]] && YTA_UPDATED=1 exec "$0" "$@"
fi

# === Bibliotheques : mise a jour au plus une fois par jour (yt-dlp doit suivre les changements de YouTube) ===
libs_ok() { "$VENV/bin/python" -c "import flask, ytmusicapi, yt_dlp, mutagen" 2>/dev/null; }
if [[ ! -f "$STAMP" || -n "$(find "$STAMP" -mmin +1440)" ]] || ! libs_ok; then
    echo "Mise a jour des bibliotheques..."
    if "$VENV/bin/pip" -q install -U --timeout 10 --retries 1 -r "$DIR/requirements.txt"; then
        touch "$STAMP"
    elif libs_ok; then
        echo "ATTENTION : mise a jour impossible (pas d'internet ?), demarrage avec les versions deja installees."
    else
        echo "*** Bibliotheques manquantes et installation impossible : verifie ta connexion internet. ***"
        exit 1
    fi
fi

(sleep 2 && xdg-open "http://127.0.0.1:$PORT" >/dev/null 2>&1) &
exec "$VENV/bin/python" "$DIR/app.py"
