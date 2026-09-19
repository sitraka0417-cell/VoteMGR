@echo off
REM ==========================================================
REM  build.bat — Compile VoteMGR en .exe Windows (PyInstaller)
REM  A lancer depuis une invite de commandes, a la racine du
REM  projet OU depuis ce dossier "installer" (le script se
REM  replace tout seul).
REM ==========================================================

cd /d "%~dp0\.."

echo.
echo [1/3] Verification de l'environnement Python...
python --version
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou pas dans le PATH.
    echo Installez Python 3.10+ depuis https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [2/3] Installation des dependances (reportlab, pyinstaller)...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR lors de l'installation des dependances.
    pause
    exit /b 1
)

echo.
echo [3/3] Compilation avec PyInstaller...
python -m PyInstaller --noconfirm --windowed --name VoteMGR ^
    --add-data "assets;assets" ^
    main.py

if errorlevel 1 (
    echo ERREUR pendant la compilation PyInstaller.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Termine ! L'executable se trouve dans dist\VoteMGR\VoteMGR.exe
echo  Vous pouvez maintenant creer l'installateur avec Inno Setup
echo  en ouvrant installer\votemgr.iss (voir README.md).
echo ============================================================
pause

