@echo off
REM ==========================================================
REM  preparer_hors_ligne.bat
REM
REM  A lancer UNE SEULE FOIS, sur un PC connecte a Internet.
REM  Telecharge tous les paquets Python necessaires (reportlab,
REM  pyinstaller, et leurs dependances) dans le dossier vendor\.
REM
REM  Une fois ce dossier vendor\ present (a garder dans le
REM  projet, y compris sur une cle USB ou dans le zip que vous
REM  transportez), build.bat pourra compiler VoteMGR.exe sur
REM  N'IMPORTE QUEL PC WINDOWS, meme SANS AUCUNE CONNEXION
REM  INTERNET.
REM ==========================================================

cd /d "%~dp0\.."

echo.
echo [1/2] Verification de Python...
python --version
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou pas dans le PATH.
    pause
    exit /b 1
)

echo.
echo [2/2] Telechargement des paquets dans vendor\ (necessite Internet)...
python -m pip install --upgrade pip
python -m pip download -r requirements.txt -d vendor

if errorlevel 1 (
    echo ERREUR lors du telechargement.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Termine ! Le dossier vendor\ contient maintenant tout ce
echo  qu'il faut. Copiez le dossier votemgr\ complet (avec
echo  vendor\) sur la machine hors-ligne, puis lancez
echo  installer\build.bat : il compilera sans Internet.
echo ============================================================
pause
