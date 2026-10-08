"""YT Album : interface web locale pour telecharger albums et titres YouTube Music, proprement tagues.

Installation : ./run.sh (Linux) ou run.bat (Windows) ; ensuite le raccourci "YT Album" (launcher.py).
Dossier de sortie : $MUSIC_DIR, sinon le dossier Musique du systeme ; range en Artiste/Album/NN - Titre.mp3
"""
import glob
import logging
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unicodedata
import urllib.request
import uuid
import webbrowser
import zipfile

import yt_dlp
from flask import Flask, jsonify, request, send_from_directory
from ytmusicapi import YTMusic

from launcher import NO_WINDOW, known_folder, xdg_dir
from tag import clean_title, safe_name as safe, tag_album

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, 'bin')
FFMPEG_ZIP = 'https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
FFMPEG_DIR = None  # dossier de ffmpeg/ffprobe ; None = ceux du PATH (fixe au demarrage par ensure_ffmpeg)


def _retry(fn, tries=10):
    """Sous Windows, l'antivirus verrouille un moment les .exe tout juste ecrits."""
    for i in range(tries):
        try:
            return fn()
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(1)


def ensure_ffmpeg():
    """Trouve ffmpeg + ffprobe ; sous Windows, les telecharge dans bin/ s'ils manquent."""
    exe = '.exe' if os.name == 'nt' else ''
    if all(os.path.isfile(os.path.join(BIN, n + exe)) for n in ('ffmpeg', 'ffprobe')):
        return BIN
    if shutil.which('ffmpeg') and shutil.which('ffprobe'):
        return None
    if os.name != 'nt':
        raise RuntimeError('ffmpeg manquant : sudo apt install ffmpeg')
    print('Telechargement de ffmpeg (une seule fois, ~150 Mo)...')
    os.makedirs(BIN, exist_ok=True)
    tmp = os.path.join(BIN, 'ffmpeg.zip.part')
    urllib.request.urlretrieve(FFMPEG_ZIP, tmp)
    with zipfile.ZipFile(tmp) as z:
        for name in z.namelist():
            base = name.rsplit('/', 1)[-1]
            if base in ('ffmpeg.exe', 'ffprobe.exe'):
                part = os.path.join(BIN, base + '.part')
                with z.open(name) as src, open(part, 'wb') as out:
                    shutil.copyfileobj(src, out)
                _retry(lambda: os.replace(part, os.path.join(BIN, base)))
    _retry(lambda: os.remove(tmp))
    if not all(os.path.isfile(os.path.join(BIN, n)) for n in ('ffmpeg.exe', 'ffprobe.exe')):
        raise RuntimeError('ffmpeg introuvable dans le zip telecharge.')
    print('ffmpeg installe dans', BIN)
    return BIN


def ffmpeg_cmd():
    return os.path.join(FFMPEG_DIR, 'ffmpeg') if FFMPEG_DIR else 'ffmpeg'


def system_music_dir():
    """Dossier Musique de l'utilisateur, y compris s'il a ete deplace (OneDrive, autre disque...)."""
    path = None
    try:
        path = known_folder('4BD8D571-6D19-48D3-BE97-422220080E43') if os.name == 'nt' else xdg_dir('MUSIC')
    except Exception:  # noqa: BLE001
        pass
    return path or os.path.join(os.path.expanduser('~'), 'Music')


MUSIC = os.path.expanduser(os.environ.get('MUSIC_DIR') or system_music_dir())
PORT = int(os.environ.get('PORT', 5123))
ATV = 'MUSIC_VIDEO_TYPE_ATV'  # piste audio officielle (OMV = clip)
# Pistes probablement hors album studio : decochees par defaut (sauf si l'album lui-meme est un live, etc.)
SUSPECT = re.compile(r'\b(live|remix|rework|session|instrumental|demo|karaoke)\b', re.I)

yt = YTMusic()
app = Flask(__name__, static_folder='static')
_albums = {}


# ---------- Utilitaires ----------

def norm(s):
    """Normalise un titre pour comparer : sans accents, casse ni ponctuation."""
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', s.lower().replace('&', 'and'))


def big_cover(thumbs, size=1200):
    if not thumbs:
        return ''
    return re.sub(r'=w\d+-h\d+.*$', f'=w{size}-h{size}-l90-rj', thumbs[-1]['url'])


def existing_numbers(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(int(f[:2]) for f in os.listdir(folder) if re.match(r'\d\d - .*\.mp3$', f))


# ---------- Albums et titres ----------

def audio_entries(browse_id):
    """IDs des pistes audio de l'album vus par yt-dlp (ytmusicapi renvoie souvent les clips)."""
    try:
        with yt_dlp.YoutubeDL({'extract_flat': 'in_playlist', 'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(f'https://music.youtube.com/browse/{browse_id}', download=False)
        return [e for e in info.get('entries') or [] if e.get('id')]
    except Exception:
        return []


def get_album(browse_id):
    if browse_id in _albums:
        a = _albums[browse_id]
        a['existing'] = existing_numbers(a['folder'])
        return a
    raw = yt.get_album(browse_id)
    flat = audio_entries(browse_id)
    album_suspect = bool(SUSPECT.search(raw['title']))
    tracks = []
    for i, t in enumerate(raw['tracks']):
        if len(flat) == len(raw['tracks']) and norm(flat[i].get('title')) == norm(t['title']):
            e = flat[i]
        else:
            e = next((x for x in flat if norm(x.get('title')) == norm(t['title'])), None)
        vid = e['id'] if e else t.get('videoId')
        tracks.append({
            'n': t.get('trackNumber') or i + 1,
            'title': t['title'],
            'videoId': vid,
            'duration': t.get('duration') or '',
            'available': bool(vid) and t.get('isAvailable', True),
            'clip': not e and t.get('videoType') != ATV,
            'suspect': bool(SUSPECT.search(t['title'])) and not album_suspect,
        })
    artist = raw['artists'][0]['name'] if raw.get('artists') else 'Inconnu'
    folder = os.path.join(MUSIC, safe(artist), safe(raw['title']))
    a = {
        'browseId': browse_id,
        'title': raw['title'],
        'type': raw.get('type') or 'Album',
        'year': raw.get('year') or '',
        'artist': artist,
        'cover': big_cover(raw.get('thumbnails')),
        'trackCount': len(tracks),
        'tracks': tracks,
        'versions': [{'title': v['title'], 'type': v.get('type'), 'browseId': v['browseId']}
                     for v in raw.get('other_versions') or [] if v.get('browseId')],
        'folder': folder,
        'existing': existing_numbers(folder),
    }
    _albums[browse_id] = a
    return a


def resolve_video(vid):
    """Video YouTube -> {'kind': 'song', album, n, note} ou {'kind': 'video', ...} si hors catalogue."""
    w = yt.get_watch_playlist(vid, limit=1)['tracks'][0]
    artist = w['artists'][0]['name'] if w.get('artists') else ''
    title = clean_title(w.get('title', ''), artist)
    album_id, note = (w.get('album') or {}).get('id'), ''
    if not album_id and artist:
        # Clip ou upload de chaine : on cherche la piste audio officielle du meme titre
        for s in yt.search(f'{artist} {title}', filter='songs')[:10]:
            same_artist = any(norm(x['name']) == norm(artist) for x in s.get('artists') or [])
            if s.get('videoType') == ATV and same_artist and norm(s.get('title')) == norm(title) and s.get('album'):
                album_id, vid = s['album']['id'], s['videoId']
                note = f'Lien vers une vidéo/clip : remplacé par la version de l\'album « {s["album"]["name"]} ».'
                break
    if album_id:
        a = get_album(album_id)
        t = next((t for t in a['tracks'] if t['videoId'] == vid), None) \
            or next((t for t in a['tracks'] if norm(t['title']) == norm(title)), None)
        if t:
            return {'kind': 'song', 'album': a, 'n': t['n'], 'note': note}
    return {'kind': 'video', 'videoId': vid, 'title': title or vid, 'artist': artist,
            'duration': w.get('length') or ''}


def parse_url(url):
    if m := re.search(r'browse/(MPRE[\w-]+)', url):
        return {'album': m.group(1)}
    if m := re.search(r'(?:v=|youtu\.be/|shorts/)([\w-]{11})', url):
        return {'video': m.group(1)}
    if m := re.search(r'list=(OLAK5uy_[\w-]+)', url):
        return {'album': yt.get_album_browse_id(m.group(1))}
    return {}


# ---------- File de telechargement ----------

jobs = []
todo = queue.Queue()


def download(vid, stage, prefix, on_progress):
    def hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            on_progress(d.get('downloaded_bytes', 0) / total if total else 0)
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(stage, f'{prefix} - %(title)s.%(ext)s'),
        'noplaylist': True, 'quiet': True, 'no_warnings': True, 'noprogress': True, 'retries': 5,
        'progress_hooks': [hook],
        **({'ffmpeg_location': FFMPEG_DIR} if FFMPEG_DIR else {}),
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '0'},
                           {'key': 'FFmpegMetadata', 'add_metadata': True}],
    }
    for attempt in range(3):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(f'https://music.youtube.com/watch?v={vid}')
        except yt_dlp.utils.DownloadError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))  # YouTube renvoie parfois 403 quand on enchaine


def fetch_cover(url, dest):
    urllib.request.urlretrieve(url, dest)
    # Les miniatures video sont en 16:9 : recadrage carre au centre
    subprocess.run([ffmpeg_cmd(), '-loglevel', 'error', '-y', '-i', dest, '-vf',
                    "crop='min(iw,ih)':'min(iw,ih)'", '-q:v', '2', dest + '.jpg'], check=True, **NO_WINDOW)
    os.replace(dest + '.jpg', dest)


def run_job(job):
    os.makedirs(MUSIC, exist_ok=True)
    stage = tempfile.mkdtemp(prefix='.ytalbum-', dir=MUSIC)
    try:
        if job['kind'] == 'album':
            a = get_album(job['browseId'])
            chosen = [t for t in a['tracks'] if t['n'] in job['numbers']]
            for k, t in enumerate(chosen):
                job['current'] = t['title']
                download(t['videoId'], stage, f'{t["n"]:02d}',
                         lambda f, k=k: job.update(progress=round((k + f) / len(chosen) * 95)))
                time.sleep(2)
            job['current'] = 'Pochette et tags'
            cover = os.path.join(stage, 'cover.jpg')
            fetch_cover(a['cover'], cover)
            rows = tag_album(stage, a['artist'], a['title'], cover, job.get('genre', ''),
                             default_date=str(a['year']), total=a['trackCount'])
            folder = a['folder']
            os.makedirs(folder, exist_ok=True)
            for f in os.listdir(stage):
                if f.endswith('.mp3'):  # remplace une eventuelle version precedente de la meme piste
                    for old in os.listdir(folder):
                        if old[:5] == f[:5] and old.endswith('.mp3'):
                            os.remove(os.path.join(folder, old))
                shutil.move(os.path.join(stage, f), os.path.join(folder, f))
            job['result'] = f'{len(rows)} titre(s) dans {folder}'
        else:
            job['current'] = job['title']
            info = download(job['videoId'], stage, '01', lambda f: job.update(progress=round(f * 95)))
            cover = os.path.join(stage, 'cover.jpg')
            fetch_cover(info.get('thumbnail'), cover)
            artist = job['artist'] or info.get('artist') or info.get('channel') or 'Inconnu'
            title = clean_title(job['title'], artist)
            tag_album(stage, artist, title, cover, job.get('genre', ''),
                      default_date=(info.get('upload_date') or '')[:4], total=1)
            folder = os.path.join(MUSIC, safe(artist), 'Singles')
            os.makedirs(folder, exist_ok=True)
            mp3 = next(f for f in os.listdir(stage) if f.endswith('.mp3'))
            shutil.move(os.path.join(stage, mp3), os.path.join(folder, safe(title) + '.mp3'))
            job['result'] = f'Dans {folder}'
        job.update(status='terminé', progress=100, current='')
    except Exception as e:  # noqa: BLE001 - on affiche l'erreur dans l'interface
        job.update(status='erreur', current='', result=str(e)[:300])
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def worker():
    while True:
        job = todo.get()
        job['status'] = 'en cours'
        run_job(job)


# ---------- API ----------

@app.get('/')
def index():
    return send_from_directory(os.path.join(HERE, 'static'), 'index.html')


@app.get('/api/info')
def info():
    return jsonify({'app': 'yt-album', 'music': MUSIC})


@app.get('/api/search')
def search():
    q, kind = request.args.get('q', '').strip(), request.args.get('kind', 'albums')
    if not q:
        return jsonify([])
    if kind == 'songs':
        return jsonify([{
            'videoId': s['videoId'], 'title': s['title'],
            'artist': ', '.join(a['name'] for a in s.get('artists') or []),
            'album': (s.get('album') or {}).get('name', ''), 'duration': s.get('duration', ''),
            'cover': big_cover(s.get('thumbnails'), 226),
        } for s in yt.search(q, filter='songs') if s.get('videoId')])
    return jsonify([{
        'browseId': a['browseId'], 'title': a['title'], 'type': a.get('type', ''), 'year': a.get('year', ''),
        'artist': ', '.join(x['name'] for x in a.get('artists') or []),
        'cover': big_cover(a.get('thumbnails'), 300),
    } for a in yt.search(q, filter='albums') if a.get('browseId')])


@app.get('/api/album/<browse_id>')
def album(browse_id):
    return jsonify(get_album(browse_id))


@app.get('/api/song/<vid>')
def song(vid):
    return jsonify(resolve_video(vid))


@app.get('/api/resolve')
def resolve():
    p = parse_url(request.args.get('url', ''))
    if 'album' in p and p['album']:
        return jsonify({'kind': 'album', 'album': get_album(p['album'])})
    if 'video' in p:
        return jsonify(resolve_video(p['video']))
    return jsonify({'error': 'Lien non reconnu (vidéo, album YouTube Music ou lien OLAK5uy…).'}), 400


@app.post('/api/jobs')
def add_job():
    d = request.get_json()
    job = {'id': uuid.uuid4().hex[:8], 'status': 'en attente', 'progress': 0, 'current': '', 'result': '',
           'genre': (d.get('genre') or '').strip()}
    if d.get('browseId'):
        a = get_album(d['browseId'])
        numbers = [int(n) for n in d.get('numbers') or []]
        label = f'{a["artist"]} — {a["title"]}'
        if len(numbers) == 1:
            label += ' : ' + next(t['title'] for t in a['tracks'] if t['n'] == numbers[0])
        job.update(kind='album', browseId=a['browseId'], numbers=numbers, label=label, cover=a['cover'])
    else:
        job.update(kind='video', videoId=d['videoId'], title=d.get('title', ''), artist=d.get('artist', ''),
                   label=f'{d.get("artist") or "?"} — {d.get("title") or d["videoId"]}', cover='')
    jobs.append(job)
    todo.put(job)
    return jsonify(job)


@app.get('/api/jobs')
def list_jobs():
    return jsonify(jobs[::-1])


@app.post('/api/jobs/clear')
def clear_jobs():
    jobs[:] = [j for j in jobs if j['status'] in ('en attente', 'en cours')]
    return jsonify(jobs[::-1])


@app.post('/api/quit')
def quit_app():
    threading.Timer(0.5, lambda: os._exit(0)).start()  # laisse le temps de repondre a la page
    return jsonify({'ok': True})


def serve(open_browser=False):
    global FFMPEG_DIR
    FFMPEG_DIR = ensure_ffmpeg()
    # Dossiers temporaires d'un telechargement interrompu (app quittee en cours de route)
    for stage in glob.glob(os.path.join(MUSIC, '.ytalbum-*')):
        shutil.rmtree(stage, ignore_errors=True)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # pas une ligne par rafraichissement de la file
    threading.Thread(target=worker, daemon=True).start()
    print(f'YT Album : http://127.0.0.1:{PORT}  (musique dans {MUSIC})')
    if open_browser:
        threading.Timer(1, webbrowser.open, [f'http://127.0.0.1:{PORT}']).start()
    app.run(host='127.0.0.1', port=PORT, threaded=True)


if __name__ == '__main__':
    serve()
