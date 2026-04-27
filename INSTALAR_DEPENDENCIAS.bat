@echo off
echo ==========================================
echo INSTALANDO DEPENDENCIAS PARA ANIME CLI
echo ==========================================
echo.

:: 1. Instalar dependencias de Python
echo [1/2] Instalando paquetes de Python...
pip install -r requirements.txt
echo.

:: 2. Instalar aria2c (acelerador de descargas)
echo [2/2] Verificando aria2c (acelerador de descargas)...

:: Verificar si ya existe aria2c en la carpeta actual
if exist "%~dp0aria2c.exe" (
    echo    aria2c ya esta instalado. Omitiendo...
    goto :fin
)

:: Verificar si aria2c esta en el PATH del sistema
where aria2c >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo    aria2c encontrado en el sistema. Omitiendo...
    goto :fin
)

:: Descargar aria2c portable
echo    Descargando aria2c portable...
set ARIA2_URL=https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip
set ARIA2_ZIP=%~dp0aria2_temp.zip
set ARIA2_DIR=%~dp0aria2_temp

:: Usar PowerShell para descargar
powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%ARIA2_URL%' -OutFile '%ARIA2_ZIP%' }" 2>nul

if not exist "%ARIA2_ZIP%" (
    echo    [!] No se pudo descargar aria2c.
    echo    [!] Las descargas funcionaran pero mas lento sin aria2c.
    echo    [!] Puedes instalarlo manualmente desde: https://aria2.github.io/
    goto :fin
)

:: Extraer aria2c.exe del zip
echo    Extrayendo aria2c...
powershell -Command "& { Expand-Archive -Path '%ARIA2_ZIP%' -DestinationPath '%ARIA2_DIR%' -Force }" 2>nul

:: Buscar aria2c.exe dentro de la carpeta extraida
for /R "%ARIA2_DIR%" %%f in (aria2c.exe) do (
    copy "%%f" "%~dp0aria2c.exe" >nul 2>nul
)

:: Limpiar archivos temporales
if exist "%ARIA2_ZIP%" del "%ARIA2_ZIP%" >nul 2>nul
if exist "%ARIA2_DIR%" rmdir /s /q "%ARIA2_DIR%" >nul 2>nul

if exist "%~dp0aria2c.exe" (
    echo    aria2c instalado correctamente!
) else (
    echo    [!] No se pudo extraer aria2c.
    echo    [!] Las descargas funcionaran pero mas lento.
)

:fin
echo.
echo ==========================================
echo    INSTALACION COMPLETADA
echo ==========================================
echo.
echo Ahora puedes usar INICIAR_APP.bat
echo.
pause
