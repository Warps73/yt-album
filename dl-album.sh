#!/usr/bin/env bash
# Telecharge un album YouTube (playlist) en MP3 avec des tags propres et une pochette carree.
# Usage : ./dl-album.sh "<Artiste>" "<Album>" "<URL playlist>" [ITEMS]
#   ITEMS (optionnel) : pistes a garder, ex "1-6,8-13,15-" pour sauter la 7 et la 14
#   DATE=AAAA-MM-JJ devant la commande force la date de sortie (sinon lue dans la description)
set -euo pipefail

if [[ $# -lt 3 ]]; then
    echo "Usage : $0 \"<Artiste>\" \"<Album>\" \"<URL playlist>\" [ITEMS]"
    exit 1
fi
ARTIST="$1"
ALBUM="$2"
URL="$3"
ITEMS=()
[[ $# -ge 4 ]] && ITEMS=(--playlist-items "$4")

DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$DIR/bin"
VENV="$DIR/.venv"
OUT="$HOME/Music/$ARTIST/$ALBUM"
mkdir -p "$BIN" "$OUT"
export PATH="$BIN:$PATH"

# === Installation / mise a jour de yt-dlp ===
if ! command -v yt-dlp >/dev/null; then
    echo "Telechargement de yt-dlp..."
    curl -L --fail -o "$BIN/yt-dlp" "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
    chmod +x "$BIN/yt-dlp"
elif [[ -x "$BIN/yt-dlp" ]]; then
    "$BIN/yt-dlp" -U >/dev/null 2>&1 || true
fi

command -v ffmpeg >/dev/null || { echo "ffmpeg manquant : sudo apt install ffmpeg"; exit 1; }

# === mutagen (pour les tags) dans un venv local ===
if [[ ! -x "$VENV/bin/python" ]]; then
    echo "Installation de mutagen..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" -q install mutagen
fi

# === Telechargement (numerotation continue, les pistes sautees ne laissent pas de trou) ===
yt-dlp -x --audio-format mp3 --audio-quality 0 \
    --embed-thumbnail --convert-thumbnails jpg --embed-metadata \
    --yes-playlist "${ITEMS[@]}" \
    -P "$OUT" -o "%(playlist_autonumber)02d - %(title)s.%(ext)s" "$URL"

# === Pochette carree (les miniatures YouTube sont en 16:9 avec bandes) ===
first="$(ls "$OUT"/[0-9][0-9]\ -\ *.mp3 | head -1)"
ffmpeg -loglevel error -y -i "$first" -an -c:v copy "$OUT/.thumb.jpg"
ffmpeg -loglevel error -y -i "$OUT/.thumb.jpg" -vf "crop='min(iw,ih)':'min(iw,ih)'" -q:v 2 "$OUT/cover.jpg"
rm -f "$OUT/.thumb.jpg"

# === Tags propres ===
"$VENV/bin/python" "$DIR/tag.py" "$OUT" "$ARTIST" "$ALBUM" "$OUT/cover.jpg"

echo -e "\nTermine ! Fichiers dans : $OUT"
