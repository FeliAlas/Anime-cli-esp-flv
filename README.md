# 🎌 Anime CLI - AnimeFLV Edition

Una herramienta ligera para buscar, ver y descargar anime directamente desde tu terminal.

## 🚀 Cómo usar (Para Principiantes)

1. **Instalar Python:** Asegúrate de tener Python instalado en tu PC (descárgalo desde [python.org](https://www.python.org/)).
2. **Instalar Dependencias:** Haz doble clic en el archivo `INSTALAR_DEPENDENCIAS.bat`. Esto instalará todo lo necesario automáticamente (incluyendo el acelerador de descargas).
3. **Iniciar Aplicación:** Haz doble clic en `INICIAR_APP.bat` y ¡listo!

## 🛠️ Requisitos
- **Python 3.10+:** Para ejecutar la aplicación.
- **VLC Media Player:** Para la reproducción fluida, es recomendable tener instalado [VLC](https://www.videolan.org/).
- **Conexión a Internet:** Para el raspado de datos y streaming.

## ⚡ Motor de Descargas
El sistema de descargas incluye múltiples optimizaciones para máxima velocidad:
- **aria2c** (se instala automáticamente): Descarga con 16 conexiones simultáneas al servidor.
- **Pre-calentamiento de conexiones:** Elimina el periodo de arranque lento.
- **Descarga multi-segmento:** Divide el archivo en partes y las descarga en paralelo.
- **Fallback inteligente:** Si aria2c no está disponible, usa un motor Python multi-hilo igualmente rápido.

## 📁 Archivos Principales
- `app.py`: El corazón del programa.
- `scraper.py`: El motor de búsqueda.
- `downloader.py`: Gestor de descargas ultra-rápidas.
- `player.py`: Reproductor integrado con VLC.
- `obscura.exe`: Motor de bypass (no borrar).

## 📥 Descargas
Los capítulos descargados se guardarán automáticamente en la carpeta `Descargas_Anime/`.

---
¡Disfruta tu anime sin publicidad ni distracciones! 🍿
