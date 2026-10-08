"""Met YT Album a jour depuis GitHub. Code de sortie 3 = mise a jour installee (le lanceur redemarre).

- Clone git : git pull --ff-only (n'ecrase jamais des modifications locales).
- Sinon : compare le dernier commit de GitHub a .version, et remplace les fichiers depuis le zip.
Toute erreur (pas d'internet, limite de l'API GitHub...) est ignoree : on demarre avec la version actuelle.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

REPO = 'Warps73/yt-album'
BRANCH = 'main'
HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(HERE, '.version')
KEEP = {'.venv', 'bin', '.version', '.git'}  # jamais touches par la mise a jour


def git_update():
    def head():
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=HERE, capture_output=True, text=True).stdout.strip()
    before = head()
    subprocess.run(['git', 'pull', '--ff-only', '-q'], cwd=HERE, capture_output=True, timeout=30)
    return head() != before


def zip_update():
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/commits/{BRANCH}',
                                 headers={'Accept': 'application/vnd.github+json'})
    latest = json.load(urllib.request.urlopen(req, timeout=10))['sha']
    current = open(VERSION_FILE).read().strip() if os.path.exists(VERSION_FILE) else ''
    if latest == current:
        return False
    print('Nouvelle version de YT Album disponible, installation...')
    data = urllib.request.urlopen(f'https://github.com/{REPO}/archive/{latest}.zip', timeout=60).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = z.namelist()[0].split('/')[0] + '/'
        for name in z.namelist():
            rel = name[len(root):]
            if not rel or rel.split('/')[0] in KEEP or name.endswith('/'):
                continue
            dest = os.path.join(HERE, *rel.split('/'))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            tmp = dest + '.new'
            with z.open(name) as src, open(tmp, 'wb') as out:
                shutil.copyfileobj(src, out)
            if rel.endswith('.sh'):
                os.chmod(tmp, 0o755)
            os.replace(tmp, dest)  # nouveau fichier : un script deja en cours d'execution n'est pas perturbe
    with open(VERSION_FILE, 'w') as f:
        f.write(latest)
    return True


if __name__ == '__main__':
    try:
        has_git = os.path.isdir(os.path.join(HERE, '.git')) and shutil.which('git')
        updated = git_update() if has_git else zip_update()
    except Exception:  # noqa: BLE001 - jamais bloquant
        updated = False
    if updated:
        print('YT Album mis a jour, redemarrage...')
    sys.exit(3 if updated else 0)
