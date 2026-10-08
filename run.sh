#!/usr/bin/env bash
# Installe / met a jour YT Album (Linux), cree le raccourci, puis le lance en arriere-plan.
# Ensuite, le raccourci "YT Album" du menu des applications suffit.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"

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

# === Mises a jour, bibliotheques, raccourci (code 3 = app mise a jour : on relance ce script) ===
rc=0; "$VENV/bin/python" "$DIR/launcher.py" --setup || rc=$?
[[ $rc -eq 3 ]] && YTA_UPDATED=1 exec "$0" "$@"
[[ $rc -eq 0 ]] || exit $rc

# === Lancement en arriere-plan : le terminal peut etre ferme ===
nohup "$VENV/bin/python" "$DIR/launcher.py" >/dev/null 2>&1 &
echo "YT Album demarre dans le navigateur. Pour l'arreter : bouton Quitter dans l'interface."
