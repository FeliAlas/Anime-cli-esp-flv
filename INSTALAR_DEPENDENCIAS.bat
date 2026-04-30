@echo off
echo ==========================================
echo INSTALANDO DEPENDENCIAS PARA ANIME CLI
echo ==========================================
echo.
echo [1/2] Instalando paquetes Python...
pip install -r requirements.txt
echo.
echo [2/2] Verificando aria2c (acelerador de descargas)...
where aria2c >nul 2>nul
if %ERRORLEVEL% == 0 (
    echo    ✅ aria2c detectado. Las descargas iran a MAXIMA velocidad.
) else (
    echo    ⚠ aria2c NO encontrado. Las descargas funcionaran pero mas lentas.
    echo.
    echo    Para MAXIMA velocidad, instala aria2c:
    echo      Opcion A: winget install aria2.aria2
    echo      Opcion B: https://github.com/aria2/aria2/releases
    echo    Descarga el .zip, extrae aria2c.exe junto a app.py, o agregalo al PATH.
)
echo.
echo ==========================================
echo Proceso terminado. Ya puedes usar INICIAR_APP.bat
echo ==========================================
pause
