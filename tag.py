"""Reecrit des tags ID3 propres sur les MP3 d'un album telecharge depuis YouTube.

Usage : [DATE=AAAA-MM-JJ] tag.py <dossier> <artiste> <album> <cover.jpg> [genre]
Les infos (date, label, copyright, credits) sont lues dans la description
"Provided to YouTube by ..." que yt-dlp a embarquee.
"""
import glob
import os
import re
import sys

from mutagen.id3 import (ID3, TIT2, TPE1, TPE2, TALB, TRCK, TPOS, TDRC, TDRL, TCON,
                         TPUB, TCOP, TCOM, TEXT, TIPL, TCMP, APIC)

LABELS = ['Deutsche Grammophon', 'Play It Again Sam', 'PIAS', 'Universal', 'Sony', 'Warner', 'Domino', 'XL', '4AD', 'Sub Pop']
CREDITS = ['Producer', 'Mixing Engineer', 'Mastering Engineer', 'Recording Engineer']
WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}


def safe_name(name):
    """Nom de fichier/dossier valide sous Linux ET Windows."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', name).strip().rstrip('. ')
    if name.split('.')[0].upper() in WINDOWS_RESERVED:
        name = '_' + name
    return name or 'Inconnu'


def clean_title(title, artist):
    """Retire "Artiste - " et les suffixes "(Official Audio)", "[Lyrics]"..."""
    title = re.sub(rf'^{re.escape(artist)}\s*-\s*', '', title)
    title = re.sub(r'\s*[(\[][^)\]]*\b(official|audio|video|lyrics?|visuali[sz]er)\b[^)\]]*[)\]]', '', title, flags=re.I)
    return title.strip()


def tag_album(folder, artist, album, cover_path, genre='', date='', default_date='', total=None):
    """Tague tous les "NN - *.mp3" du dossier. Retourne [(n, titre, date, label)].

    date : force la date ; default_date : utilisee si la description n'en donne pas.
    total : nombre de pistes de l'album (par defaut : nombre de fichiers du dossier).
    """
    cover = open(cover_path, 'rb').read()
    files = sorted(glob.glob(os.path.join(folder, '[0-9][0-9] - *.mp3')))
    total = total or len(files)
    done = []
    for f in files:
        old = ID3(f)
        desc = str(old['TXXX:description']) if 'TXXX:description' in old else ''
        lines = [l.strip() for l in desc.splitlines()]
        n = int(os.path.basename(f)[:2])
        title = clean_title(str(old['TIT2']) if 'TIT2' in old else os.path.basename(f)[5:-4], artist)

        # Credits "Role, Role: Nom"
        roles = {}
        for line in lines:
            m = re.match(r'^([A-Za-z ,]+): (.+)$', line)
            if m and m.group(1) != 'Released on':
                for r in m.group(1).split(','):
                    roles.setdefault(r.strip(), []).append(m.group(2).strip())
        copy = next((l for l in lines if l.startswith('℗')), '')
        label = next((lab for lab in LABELS if lab in copy), '')
        m = re.search(r'Released on: (\d{4}-\d{2}-\d{2})', desc)
        d = date or (m.group(1) if m else '') or default_date or (str(old['TDRC']) if 'TDRC' in old else '')

        old.delete(f)  # repart de zero : vire description/synopsis/purl/comment/encoder
        t = ID3()
        t.add(TIT2(encoding=3, text=title))
        t.add(TPE1(encoding=3, text=artist))
        t.add(TPE2(encoding=3, text=artist))
        t.add(TALB(encoding=3, text=album))
        t.add(TRCK(encoding=3, text=f'{n}/{total}'))
        t.add(TPOS(encoding=3, text='1/1'))
        if d:
            t.add(TDRC(encoding=3, text=d))
            t.add(TDRL(encoding=3, text=d))
        if genre:
            t.add(TCON(encoding=3, text=genre))
        t.add(TCMP(encoding=3, text='0'))
        if label:
            t.add(TPUB(encoding=3, text=label))
        if copy:
            t.add(TCOP(encoding=3, text=copy.lstrip('℗ ').strip()))
        if 'Composer' in roles:
            t.add(TCOM(encoding=3, text=roles['Composer']))
        if 'Lyricist' in roles:
            t.add(TEXT(encoding=3, text=roles['Lyricist']))
        people = [[r, p] for r in CREDITS for p in roles.get(r, [])]
        if people:
            t.add(TIPL(encoding=3, people=people))
        t.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover))
        t.save(f, v2_version=3)
        # Nom de fichier propre : "NN - Titre.mp3"
        clean = os.path.join(folder, f'{n:02d} - ' + safe_name(title) + '.mp3')
        if clean != f:
            os.replace(f, clean)
        done.append((n, title, d, label))
    return done


if __name__ == '__main__':
    folder, artist, album, cover_path = sys.argv[1:5]
    genre = sys.argv[5] if len(sys.argv) > 5 else ''
    rows = tag_album(folder, artist, album, cover_path, genre, date=os.environ.get('DATE', ''))
    for n, title, d, label in rows:
        print(f'{n:02d}/{len(rows)}  {title}  | {d or "?"} | {label or "?"}')
