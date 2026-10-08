@echo off
setlocal
title YT Album
cd /d "%~dp0"
rem Lance YT Album (Windows) : http://127.0.0.1:5123

set "BIN=%~dp0bin"
set "VENVPY=%~dp0.venv\Scripts\python.exe"
set "STAMP=%~dp0.venv\last-update.txt"
if not defined PORT set "PORT=5123"
if not exist "%BIN%" mkdir "%BIN%"

rem === Python 3 (installe via winget si absent) ===
call :find_python
if defined PY goto :python_ok
echo Python 3 n'est pas installe.
where winget >nul 2>&1
if errorlevel 1 goto :python_manual
choice /c ON /m "L'installer maintenant avec winget (O = oui, N = non)"
if errorlevel 2 goto :python_manual
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
call :find_python
if defined PY goto :python_ok
:python_manual
echo.
echo *** Installe Python 3 depuis https://www.python.org/downloads/ en cochant "Add python.exe to PATH", puis relance. ***
pause
exit /b 1
:python_ok

rem === ffmpeg dans bin\ (une seule fois, ~100 Mo) ===
where ffmpeg >nul 2>&1
if not errorlevel 1 goto :ffmpeg_ok
if exist "%BIN%\ffmpeg.exe" goto :ffmpeg_ok
echo Telechargement de ffmpeg...
curl -L --fail -o "%BIN%\ffmpeg.zip" "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
if errorlevel 1 goto :dl_error
tar -xf "%BIN%\ffmpeg.zip" -C "%BIN%"
for /r "%BIN%" %%F in (ffmpeg*.exe ffprobe*.exe) do if /i not "%%~dpF"=="%BIN%\" move /y "%%F" "%BIN%\" >nul
del "%BIN%\ffmpeg.zip"
for /d %%D in ("%BIN%\ffmpeg-*") do rmdir /s /q "%%D"
:ffmpeg_ok

rem === Environnement Python isole (.venv) ===
if exist "%VENVPY%" goto :venv_ok
echo Premiere installation...
if exist ".venv" rmdir /s /q ".venv"
%PY% -m venv .venv
if errorlevel 1 goto :dl_error
:venv_ok

rem === Mise a jour de l'app depuis GitHub (une seule ligne : ce fichier peut etre remplace pendant la mise a jour) ===
if not defined YTA_UPDATED "%VENVPY%" update.py & if errorlevel 3 (set "YTA_UPDATED=1" & "%~f0" & exit /b)

rem === Bibliotheques : mise a jour au plus une fois par jour ===
set "TODAY=%DATE%"
set "LAST="
if exist "%STAMP%" set /p LAST=<"%STAMP%"
"%VENVPY%" -c "import flask, ytmusicapi, yt_dlp, mutagen" >nul 2>&1
if errorlevel 1 goto :update
if "%LAST%"=="%TODAY%" goto :start
:update
echo Mise a jour des bibliotheques...
"%VENVPY%" -m pip -q install -U --timeout 10 --retries 1 -r requirements.txt
if not errorlevel 1 (
    > "%STAMP%" echo %TODAY%
    goto :start
)
"%VENVPY%" -c "import flask, ytmusicapi, yt_dlp, mutagen" >nul 2>&1
if errorlevel 1 goto :dl_error
echo ATTENTION : mise a jour impossible ^(pas d'internet ?^), demarrage avec les versions deja installees.

:start
start "" "http://127.0.0.1:%PORT%"
"%VENVPY%" app.py
pause
exit /b 0

:find_python
rem Le "python" du Microsoft Store n'est qu'un raccourci vers le Store : --version echoue, on l'ignore
set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
    exit /b 0
)
python --version >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
    exit /b 0
)
rem Juste apres une installation winget, le PATH de cette console n'est pas encore a jour
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set PY="%%D\python.exe"
exit /b 0

:dl_error
echo.
echo *** Impossible de telecharger les outils. Verifie ta connexion internet. ***
pause
exit /b 1
