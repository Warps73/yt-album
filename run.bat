@echo off
setlocal
title YT Album
cd /d "%~dp0"
rem Installe / met a jour YT Album (Windows), cree les raccourcis, puis le lance sans console.
rem Ensuite, le raccourci "YT Album" du Bureau ou du menu Demarrer suffit.

set "VENVPY=%~dp0.venv\Scripts\python.exe"

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

rem === Environnement Python isole (.venv) ===
if exist "%VENVPY%" goto :venv_ok
echo Premiere installation...
if exist ".venv" rmdir /s /q ".venv"
%PY% -m venv .venv
if errorlevel 1 goto :error
:venv_ok

rem === Mises a jour, bibliotheques, ffmpeg, raccourcis ===
rem Une seule ligne : la mise a jour peut remplacer ce fichier. Code 3 = app mise a jour, on relance ce script.
"%VENVPY%" launcher.py --setup & if errorlevel 3 (set "YTA_UPDATED=1" & "%~f0" & exit /b)
if errorlevel 1 goto :error

rem === Lancement sans console ===
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launcher.py"
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

:error
echo.
echo *** L'installation a echoue (voir le message ci-dessus). Verifie ta connexion internet puis relance. ***
pause
exit /b 1
