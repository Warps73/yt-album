# YT Album

Interface web locale pour télécharger des albums et des titres depuis YouTube Music en MP3, proprement rangés et tagués.

- Recherche d'albums ou de titres, ou lien YouTube collé directement
- Préfère les pistes audio officielles aux clips (un lien de clip est remplacé par la version album)
- Rangement `Artiste/Album/NN - Titre.mp3` avec les vrais numéros de piste, pochette HD, date de sortie, label et crédits
- Lives, remixes et sessions décochés par défaut ; titres déjà présents signalés
- File d'attente pour enchaîner plusieurs albums

## Installation et lancement

| Système | Première fois | Ensuite |
|---|---|---|
| Linux | `./run.sh` | raccourci « YT Album » (menu des applications ou Bureau) |
| Windows | double-clic sur `run.bat` | raccourci « YT Album » (Bureau ou menu Démarrer) |

`run.sh` / `run.bat` installent ce qui manque (Python via winget et ffmpeg dans `bin/` sous Windows, `python3-venv` / `ffmpeg` via apt sous Linux, après confirmation), les bibliothèques Python dans `.venv/`, et créent le raccourci.

L'app tourne ensuite en arrière-plan, sans console : le navigateur s'ouvre sur http://127.0.0.1:5123, et le bouton **Quitter** de l'interface l'arrête. Relancer le raccourci quand elle tourne déjà rouvre simplement l'onglet. Le journal est dans `yt-album.log`.

À chaque lancement, l'app se met à jour depuis GitHub ; les bibliothèques (dont yt-dlp) une fois par jour.

## Réglages

- `MUSIC_DIR` : dossier de sortie (par défaut, le dossier Musique du système)
- `PORT` : port de l'interface (5123 par défaut)

## En ligne de commande

`./dl-album.sh "Artiste" "Album" "<lien playlist>" [pistes]` (Linux) ; `tag.py` pour retaguer un dossier.
