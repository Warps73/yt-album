"""Point d'entree de YT Album (bibliotheque standard uniquement, avant d'importer l'app).

python launcher.py          -> demarrage normal, sans console (raccourci) : maj eventuelles, serveur, navigateur
python launcher.py --setup  -> installation / mises a jour en console (run.sh, run.bat) + raccourcis, puis quitte
                               code 3 = l'app vient d'etre mise a jour : le lanceur doit se relancer
"""
import ctypes
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import urllib.request
import uuid
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HERE, '.venv')
STAMP = os.path.join(VENV, '.last-update')
LOG = os.path.join(HERE, 'yt-album.log')
PORT = int(os.environ.get('PORT', 5123))
URL = f'http://127.0.0.1:{PORT}'
LIBS = ['flask', 'ytmusicapi', 'yt_dlp', 'mutagen']
NO_WINDOW = {'creationflags': 0x08000000} if os.name == 'nt' else {}  # pas de fenetre noire sous Windows


# ---------- Dossiers systeme ----------

def known_folder(guid):
    """Dossier Windows connu (Musique, Bureau...), y compris s'il a ete deplace (OneDrive, autre disque)."""
    class GUID(ctypes.Structure):
        _fields_ = [('d1', ctypes.c_uint32), ('d2', ctypes.c_uint16), ('d3', ctypes.c_uint16),
                    ('d4', ctypes.c_ubyte * 8)]
    u = uuid.UUID(guid)
    g = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8).from_buffer_copy(u.bytes[8:]))
    p = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(p)) != 0:
        return None
    path = p.value
    ctypes.windll.ole32.CoTaskMemFree(p)
    return path


def xdg_dir(name):
    """Dossier utilisateur Linux (MUSIC, DESKTOP...), None s'il n'est pas defini."""
    try:
        path = subprocess.run(['xdg-user-dir', name], capture_output=True, text=True).stdout.strip()
    except OSError:
        return None
    return path if path and path != os.path.expanduser('~') else None


# ---------- Etapes ----------

def already_running():
    try:
        return json.load(urllib.request.urlopen(URL + '/api/info', timeout=1)).get('app') == 'yt-album'
    except Exception:  # noqa: BLE001
        return False


def libs_ok():
    return all(importlib.util.find_spec(m) for m in LIBS)


def update_libs():
    """Bibliotheques a jour au plus une fois par jour (yt-dlp doit suivre les changements de YouTube)."""
    today = datetime.date.today().isoformat()
    last = open(STAMP).read().strip() if os.path.exists(STAMP) else ''
    if last == today and libs_ok():
        return
    print('Mise a jour des bibliotheques...')
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', '--timeout', '10', '--retries', '1',
                        '-r', os.path.join(HERE, 'requirements.txt')], capture_output=True, text=True, **NO_WINDOW)
    if r.returncode == 0:
        with open(STAMP, 'w') as f:
            f.write(today)
    elif not libs_ok():
        raise RuntimeError('Bibliotheques manquantes et installation impossible : '
                           'verifie ta connexion internet.\n\n' + r.stderr[-800:])
    else:
        print('ATTENTION : mise a jour impossible, demarrage avec les versions deja installees.')


def make_shortcuts():
    icon = os.path.join(HERE, 'static', 'icon.ico' if os.name == 'nt' else 'icon.png')
    launcher = os.path.join(HERE, 'launcher.py')
    if os.name == 'nt':
        pythonw = os.path.join(VENV, 'Scripts', 'pythonw.exe')
        places = [known_folder('B4BFCC3A-DB2C-424C-B029-7FE99A87C641'),  # Bureau
                  known_folder('A77F5D77-2E2B-44C3-A6A2-ABA601054A51')]  # Menu Demarrer > Programmes
        ps = ('$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:YTA_LNK);'
              '$s.TargetPath=$env:YTA_TGT;$s.Arguments=$env:YTA_ARGS;$s.WorkingDirectory=$env:YTA_WD;'
              '$s.IconLocation=$env:YTA_ICO;$s.Description="YT Album";$s.Save()')
        for place in filter(None, places):
            env = dict(os.environ, YTA_LNK=os.path.join(place, 'YT Album.lnk'), YTA_TGT=pythonw,
                       YTA_ARGS=f'"{launcher}"', YTA_WD=HERE, YTA_ICO=icon)
            subprocess.run(['powershell', '-NoProfile', '-Command', ps], env=env, capture_output=True, **NO_WINDOW)
        print('Raccourci "YT Album" cree sur le Bureau et dans le menu Demarrer.')
    else:
        python = os.path.join(VENV, 'bin', 'python')
        entry = ('[Desktop Entry]\nType=Application\nName=YT Album\n'
                 'Comment=Telecharger albums et titres YouTube Music\n'
                 f'Exec="{python}" "{launcher}"\nIcon={icon}\nTerminal=false\nCategories=AudioVideo;Audio;\n')
        apps = os.path.expanduser('~/.local/share/applications')
        targets = [os.path.join(apps, 'yt-album.desktop')]
        desktop = xdg_dir('DESKTOP')
        if desktop and os.path.isdir(desktop):
            targets.append(os.path.join(desktop, 'yt-album.desktop'))
        for t in targets:
            os.makedirs(os.path.dirname(t), exist_ok=True)
            with open(t, 'w') as f:
                f.write(entry)
            os.chmod(t, 0o755)
            # Marque le lanceur comme "de confiance" (GNOME, et XFCE qui verifie une empreinte)
            subprocess.run(['gio', 'set', t, 'metadata::trusted', 'true'], capture_output=True)
            subprocess.run(['gio', 'set', '-t', 'string', t, 'metadata::xfce-exe-checksum',
                            hashlib.sha256(entry.encode()).hexdigest()], capture_output=True)
        print('Raccourci "YT Album" cree dans le menu des applications' + (' et sur le Bureau.' if desktop else '.'))


def show_error(msg):
    print(msg, file=sys.stderr)
    if os.name == 'nt':
        ctypes.windll.user32.MessageBoxW(0, msg, 'YT Album', 0x10)
    else:
        for cmd in (['zenity', '--error', '--title=YT Album', f'--text={msg}'], ['notify-send', 'YT Album', msg]):
            try:
                subprocess.run(cmd)
                break
            except OSError:
                continue


def main():
    setup = '--setup' in sys.argv
    if not setup:
        # Pas de console : tout part dans yt-album.log (remis a zero s'il depasse 2 Mo)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 2_000_000:
            os.remove(LOG)
        sys.stdout = sys.stderr = open(LOG, 'a', encoding='utf-8', buffering=1)
        print(f'\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===')

    if already_running():
        if setup:
            print('YT Album tourne deja.')
        else:
            webbrowser.open(URL)
        return 0

    if not os.environ.get('YTA_UPDATED'):
        import update
        if update.run():
            if setup:
                return 3
            os.environ['YTA_UPDATED'] = '1'
            subprocess.Popen([sys.executable, os.path.abspath(__file__)] + sys.argv[1:], **NO_WINDOW)
            return 0

    update_libs()
    import app
    if setup:
        app.ensure_ffmpeg()
        make_shortcuts()
        return 0
    app.serve(open_browser=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        if '--setup' in sys.argv:
            show_error(f'YT Album n\'a pas pu s\'installer :\n\n{e}')
        else:
            import traceback
            traceback.print_exc()
            show_error(f'YT Album n\'a pas pu demarrer :\n\n{e}\n\nDetails dans {LOG}')
        sys.exit(1)
