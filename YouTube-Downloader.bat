@echo off
setlocal
title YouTube Downloader
cd /d "%~dp0"

rem === Dossiers ===
set "BIN=%~dp0bin"
set "OUT=%USERPROFILE%\Downloads\YouTube"
if not exist "%BIN%" mkdir "%BIN%"
if not exist "%OUT%" mkdir "%OUT%"
set "PATH=%BIN%;%PATH%"

rem === Installation automatique de yt-dlp ===
if not exist "%BIN%\yt-dlp.exe" (
    echo Telechargement de yt-dlp...
    curl -L --fail -o "%BIN%\yt-dlp.exe" "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
    if errorlevel 1 goto :dl_error
) else (
    echo Mise a jour de yt-dlp...
    "%BIN%\yt-dlp.exe" -U >nul 2>&1
)

rem === Installation automatique de ffmpeg (fusion video+audio, MP3) ===
if not exist "%BIN%\ffmpeg.exe" (
    echo Telechargement de ffmpeg ^(une seule fois, ~100 Mo^)...
    curl -L --fail -o "%BIN%\ffmpeg.zip" "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    if errorlevel 1 goto :dl_error
    tar -xf "%BIN%\ffmpeg.zip" -C "%BIN%"
    for /r "%BIN%" %%F in (ffmpeg*.exe ffprobe*.exe) do (
        if /i not "%%~dpF"=="%BIN%\" move /y "%%F" "%BIN%\" >nul
    )
    del "%BIN%\ffmpeg.zip"
    for /d %%D in ("%BIN%\ffmpeg-*") do rmdir /s /q "%%D"
)

rem Lien passe en argument (ou glisse sur le .bat)
set "URL=%~1"

:menu
cls
echo ==============================================
echo            YOUTUBE DOWNLOADER
echo ==============================================
echo  Fichiers enregistres dans :
echo  %OUT%
echo ==============================================
echo.
if not defined URL set /p "URL=Colle le lien de la video (ou Entree pour quitter) : "
if not defined URL goto :eof

echo.
echo  1 - Video MP4 (meilleure qualite)
echo  2 - Video MP4 720p (fichier plus leger)
echo  3 - Audio MP3 seulement
echo.
set "CHOIX=1"
set /p "CHOIX=Ton choix [1] : "
if not "%CHOIX%"=="1" if not "%CHOIX%"=="2" if not "%CHOIX%"=="3" goto :menu

set "COMMON=--no-playlist -P "%OUT%" -o "%%(title)s.%%(ext)s" --windows-filenames"

if "%CHOIX%"=="1" yt-dlp %COMMON% -S "vcodec:h264,res,acodec:m4a" --merge-output-format mp4 "%URL%"
if "%CHOIX%"=="2" yt-dlp %COMMON% -S "vcodec:h264,res:720,acodec:m4a" --merge-output-format mp4 "%URL%"
if "%CHOIX%"=="3" yt-dlp %COMMON% -x --audio-format mp3 --audio-quality 0 --embed-thumbnail --embed-metadata "%URL%"

echo.
if errorlevel 1 (
    echo *** Erreur pendant le telechargement. Verifie le lien. ***
) else (
    echo Termine !
    start "" "%OUT%"
)
echo.
set "URL="
pause
goto :menu

:dl_error
echo.
echo *** Impossible de telecharger les outils. Verifie ta connexion internet. ***
pause
exit /b 1
