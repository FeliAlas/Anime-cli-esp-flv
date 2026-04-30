"""
downloader.py — Motor de descarga ultra-rápido para Anime CLI
Soporta aria2c (si disponible) como acelerador externo.
Fallback: descarga multi-conexión con ThreadPoolExecutor para MP4,
yt-dlp con concurrent_fragment_downloads mejorado para M3U8.
"""

import os
import shutil
import sys
import subprocess
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
_BASE_DIR = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
from rich.progress import (
    Progress, TextColumn, BarColumn, DownloadColumn,
    TransferSpeedColumn, TimeRemainingColumn
)

# ─────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────

CHUNK_SIZE = 1024 * 1024  # 1 MB por iteración (vs 8KB anterior)
NUM_SEGMENTOS = 8         # Conexiones paralelas para descarga MP4
MAX_REINTENTOS = 5        # Reintentos por segmento
ARIA2C_CONNS = 16         # Conexiones por servidor para aria2c

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www3.animeflv.net/",
    "Connection": "keep-alive",
}

# Sesión global con connection pooling + keep-alive
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
# Incrementar el pool de conexiones para permitir más paralelas
adapter = requests.adapters.HTTPAdapter(
    pool_connections=32,
    pool_maxsize=32,
    max_retries=3,
)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)


# ─────────────────────────────────────────
# DETECCIÓN DE ARIA2C
# ─────────────────────────────────────────

_aria2c_disponible = None  # Cache del resultado

def _detectar_aria2c() -> bool:
    """Detecta si aria2c está instalado y disponible en el PATH."""
    global _aria2c_disponible
    if _aria2c_disponible is not None:
        return _aria2c_disponible

    ruta = shutil.which("aria2c")
    if ruta:
        _aria2c_disponible = True
        return True

    # Buscar en ubicaciones comunes de Windows
    rutas_comunes = [
        os.path.join(os.environ.get("ProgramFiles", ""), "aria2", "aria2c.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "aria2", "aria2c.exe"),
        os.path.join(_BASE_DIR, "aria2c.exe"),
    ]
    for ruta in rutas_comunes:
        if ruta and os.path.isfile(ruta):
            _aria2c_disponible = True
            return True

    _aria2c_disponible = False
    return False


# ─────────────────────────────────────────
# PUNTO DE ENTRADA PRINCIPAL
# ─────────────────────────────────────────

def descargar_video(url: str, nombre_anime: str, numero_ep: int|str) -> bool:
    """
    Descarga el video. Detecta automáticamente el mejor método:
    - aria2c (si disponible) → máxima velocidad
    - Multi-conexión Python (MP4) / yt-dlp mejorado (M3U8) → fallback
    Se guarda en Descargas_Anime/Nombre_del_anime/
    """
    # Limpiar nombre de anime para que sea válido en el sistema de archivos
    safe_name = "".join(c for c in nombre_anime if c.isalnum() or c in (' ', '-', '_')).strip()

    # Crear estructura de carpetas
    base_dir = os.path.join(os.getcwd(), "Descargas_Anime", safe_name)
    os.makedirs(base_dir, exist_ok=True)

    # Archivo de salida
    filepath = os.path.join(base_dir, f"{safe_name} - Episodio {numero_ep}.mp4")

    if os.path.exists(filepath):
        from app import console
        console.print(f"[yellow]⚠ El episodio ya está descargado en: {filepath}[/yellow]")
        return True

    from app import console

    # Mostrar motor de descarga
    tiene_aria2c = _detectar_aria2c()
    motor = "[bold green]aria2c[/bold green] (turbo)" if tiene_aria2c else "[yellow]Python multi-hilo[/yellow]"
    console.print(f"\n[cyan]Motor de descarga:[/cyan] {motor}")
    console.print(f"[cyan]Guardando en:[/cyan] {filepath}")

    # Determinar tipo de descarga
    es_mp4 = (
        url.endswith('.mp4') or
        "video/mp4" in url or
        ("mp4" in url.lower() and ".m3u8" not in url.lower())
    )

    if es_mp4:
        if tiene_aria2c:
            return _descargar_aria2c(url, filepath, "MP4")
        return _descargar_mp4_multiconexion(url, filepath)
    else:
        return _descargar_m3u8_acelerado(url, filepath, tiene_aria2c)


# ─────────────────────────────────────────
# DESCARGA CON ARIA2C (MP4 y M3U8 directos)
# ─────────────────────────────────────────

def _descargar_aria2c(url: str, filepath: str, tipo: str = "MP4") -> bool:
    """
    Descarga usando aria2c con 16 conexiones simultáneas.
    Máxima velocidad posible.
    """
    from app import console

    console.print(f"[dim]ARIA2C → {tipo} con {ARIA2C_CONNS} conexiones paralelas...[/dim]")

    directorio = os.path.dirname(filepath)
    nombre_archivo = os.path.basename(filepath)
    aria2c_bin = shutil.which("aria2c") or os.path.join(_BASE_DIR, "aria2c.exe")
    cmd = [
        aria2c_bin,
        url,
        f"--dir={directorio}",
        f"--out={nombre_archivo}",
        f"--max-connection-per-server={ARIA2C_CONNS}",
        f"--split={ARIA2C_CONNS}",
        "--min-split-size=1M",
        "--file-allocation=none",       # Arranque instantáneo
        "--continue=true",               # Soporta reanudación
        f"--max-tries={MAX_REINTENTOS}",
        "--retry-wait=3",
        "--timeout=30",
        "--connect-timeout=10",
        "--check-certificate=false",
        f"--user-agent={HEADERS['User-Agent']}",
        f"--referer={HEADERS['Referer']}",
        "--summary-interval=0",         # No imprimir resumen periódico
        "--console-log-level=warn",     # Solo errores y warnings
        "--download-result=hide",
    ]

    try:
        resultado = subprocess.run(
            cmd,
            capture_output=False,
            timeout=600,  # Timeout de 10 min para la descarga completa
        )
        if resultado.returncode == 0 and os.path.exists(filepath):
            return True
        else:
            console.print(f"[red]❌ aria2c falló (código {resultado.returncode})[/red]")
            return False
    except subprocess.TimeoutExpired:
        console.print("[red]❌ Timeout: la descarga tardó más de 10 minutos.[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]❌ aria2c no encontrado. Usando fallback...[/red]")
        return False
    except Exception as e:
        console.print(f"[red]❌ Error aria2c:[/red] {str(e)}")
        return False


# ─────────────────────────────────────────
# DESCARGA MP4 MULTI-CONEXIÓN (FALLBACK)
# ─────────────────────────────────────────

def _descargar_mp4_multiconexion(url: str, filepath: str) -> bool:
    """
    Descarga MP4 usando múltiples conexiones HTTP paralelas con Range requests.
    Divide el archivo en N segmentos y los descarga simultáneamente.
    Fallback: si el servidor no soporta Range, descarga single-thread optimizada.
    """
    from app import console

    try:
        # 1. Obtener tamaño total y verificar soporte de Range
        head = SESSION.head(url, timeout=10, allow_redirects=True)
        head.raise_for_status()

        total_size = int(head.headers.get('content-length', 0))
        acepta_rangos = head.headers.get('accept-ranges', '').lower() == 'bytes'

        if total_size == 0 or not acepta_rangos:
            console.print("[dim]Servidor no soporta descarga segmentada. Usando modo single-thread optimizado...[/dim]")
            return _descargar_mp4_simple(url, filepath)

        console.print(
            f"[dim]MULTI-CONEXIÓN → {NUM_SEGMENTOS} hilos paralelos "
            f"| Archivo: {total_size / (1024*1024):.1f} MB[/dim]"
        )

        # 2. Calcular rangos para cada segmento
        segment_size = total_size // NUM_SEGMENTOS
        rangos = []
        for i in range(NUM_SEGMENTOS):
            inicio = i * segment_size
            fin = (i + 1) * segment_size - 1 if i < NUM_SEGMENTOS - 1 else total_size - 1
            rangos.append((i, inicio, fin))

        # 3. Crear archivos temporales para cada segmento
        archivos_temp = [f"{filepath}.part{i}" for i in range(NUM_SEGMENTOS)]

        # 4. Barra de progreso compartida
        descargado_total = [0]  # Lista mutable para compartir entre threads

        with Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn()
        ) as progress:
            tarea = progress.add_task("Descargando...", total=total_size)

            def descargar_segmento(seg_info):
                idx, inicio, fin = seg_info
                for intento in range(MAX_REINTENTOS):
                    try:
                        headers = {**HEADERS, "Range": f"bytes={inicio}-{fin}"}
                        resp = SESSION.get(url, headers=headers, stream=True, timeout=30)
                        resp.raise_for_status()

                        with open(archivos_temp[idx], 'wb') as f:
                            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                                if chunk:
                                    f.write(chunk)
                                    descargado_total[0] += len(chunk)
                                    progress.update(tarea, completed=descargado_total[0])
                        return True
                    except Exception as e:
                        if intento < MAX_REINTENTOS - 1:
                            time.sleep(2 ** intento)  # Backoff exponencial
                        else:
                            console.print(f"[red]Segmento {idx} falló tras {MAX_REINTENTOS} intentos: {e}[/red]")
                            return False

            # 5. Lanzar descargas en paralelo
            with ThreadPoolExecutor(max_workers=NUM_SEGMENTOS) as executor:
                futuros = {executor.submit(descargar_segmento, r): r for r in rangos}
                resultados = []
                for futuro in as_completed(futuros):
                    resultados.append(futuro.result())

        # 6. Verificar que todos los segmentos se descargaron
        if not all(resultados):
            console.print("[red]❌ Algunos segmentos fallaron. Limpiando...[/red]")
            _limpiar_temporales(archivos_temp, filepath)
            return False

        # 7. Unir todos los segmentos en el archivo final
        console.print("[dim]Uniendo segmentos...[/dim]")
        with open(filepath, 'wb') as salida:
            for temp in archivos_temp:
                with open(temp, 'rb') as entrada:
                    while True:
                        chunk = entrada.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        salida.write(chunk)

        # 8. Limpiar temporales
        for temp in archivos_temp:
            try:
                os.remove(temp)
            except OSError:
                pass

        # 9. Verificar tamaño final
        final_size = os.path.getsize(filepath)
        if abs(final_size - total_size) > 1024:  # Tolerancia de 1KB
            console.print(f"[red]❌ Tamaño incorrecto: {final_size} vs {total_size} bytes[/red]")
            os.remove(filepath)
            return False

        return True

    except Exception as e:
        console.print(f"[red]❌ Error en descarga multi-conexión:[/red] {str(e)}")
        _limpiar_temporales(
            [f"{filepath}.part{i}" for i in range(NUM_SEGMENTOS)],
            filepath
        )
        return False


def _descargar_mp4_simple(url: str, filepath: str) -> bool:
    """
    Descarga MP4 single-thread optimizada (para servidores sin Range).
    Mejora sobre la versión anterior: chunk_size de 1MB, sesión con keep-alive.
    """
    try:
        response = SESSION.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))

        with Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn()
        ) as progress:
            tarea = progress.add_task("Descargando...", total=total_size)

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        progress.update(tarea, advance=len(chunk))
        return True
    except Exception as e:
        from app import console
        console.print(f"[red]❌ Error al descargar MP4:[/red] {str(e)}")
        if os.path.exists(filepath):
            os.remove(filepath)
        return False


# ─────────────────────────────────────────
# DESCARGA M3U8 CON YT-DLP (+ ARIA2C)
# ─────────────────────────────────────────

def _precalentar_conexiones(url: str, num_conexiones: int = 8):
    """
    Pre-calienta conexiones HTTP al servidor de video.
    Esto fuerza el TCP slow start ANTES de la descarga real,
    eliminando el periodo de rampa de 30-40 segundos.
    """
    import threading

    def _ping(url_base):
        try:
            # Hacer un HEAD request para abrir la conexión TCP + TLS
            SESSION.head(url_base, timeout=5, allow_redirects=True)
        except Exception:
            pass

    hilos = []
    # Extraer el dominio base para pre-calentar al servidor correcto
    from urllib.parse import urlparse
    parsed = urlparse(url)
    url_base = f"{parsed.scheme}://{parsed.netloc}/"

    for _ in range(num_conexiones):
        t = threading.Thread(target=_ping, args=(url_base,), daemon=True)
        t.start()
        hilos.append(t)

    # Esperar máximo 3 segundos
    for t in hilos:
        t.join(timeout=3)


def _descargar_m3u8_acelerado(url: str, filepath: str, usar_aria2c: bool = False) -> bool:
    """
    Usa yt-dlp para descargar M3U8.
    Si aria2c está disponible, lo usa como downloader externo (máxima velocidad).
    Si no, usa el downloader interno con concurrent_fragment_downloads optimizado.
    Incluye pre-calentamiento de conexiones para eliminar el slow start.
    """
    from app import console
    import yt_dlp

    # Pre-calentar conexiones TCP/TLS antes de iniciar la descarga
    console.print("[dim]Pre-calentando conexiones al servidor...[/dim]")
    _precalentar_conexiones(url, num_conexiones=12)

    if usar_aria2c:
        console.print(f"[dim]YT-DLP + ARIA2C → {ARIA2C_CONNS} conexiones por fragmento...[/dim]")
    else:
        console.print("[dim]YT-DLP → 32 fragmentos concurrentes + buffer optimizado...[/dim]")

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    opciones = {
        'outtmpl': filepath,
        'retries': 20,
        'fragment_retries': 20,
        'quiet': False,
        'no_warnings': True,
        'nocheckcertificate': True,
        'no_check_update': True,
        'format': 'best',  # Servidores de anime usan stream único, no separar audio/video
        # Headers anti-throttle
        'http_headers': HEADERS,
        # ── Optimizaciones anti slow-start ──
        'http_chunk_size': 10485760,  # 10 MB — fuerza chunks grandes desde el inicio
        'buffersize': 1048576,        # 1 MB buffer interno (vs ~8KB default)
        'socket_timeout': 15,         # Timeout corto → descarta conexiones lentas rápido
    }

    if usar_aria2c:
        # Usar aria2c como motor de descarga de cada fragmento
        opciones['external_downloader'] = 'aria2c'
        opciones['external_downloader_args'] = {
            'aria2c': [
                f'--max-connection-per-server={ARIA2C_CONNS}',
                f'--split={ARIA2C_CONNS}',
                '--min-split-size=1M',
                '--file-allocation=none',
                '--continue=true',
                f'--max-tries={MAX_REINTENTOS}',
                '--retry-wait=3',
                '--check-certificate=false',
                '--console-log-level=warn',
                '--summary-interval=0',
                '--download-result=hide',
                # Buffer grande para arranque rápido
                '--stream-piece-selector=inorder',
                '--uri-selector=adaptive',
            ]
        }
    else:
        # Fallback: usar el downloader interno con máxima concurrencia
        # 32 fragmentos concurrentes llena el pipeline mucho más rápido que 16
        opciones['concurrent_fragment_downloads'] = 32

    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            resultado = ydl.download([url])
            return resultado == 0
    except Exception as e:
        console.print(f"[red]❌ Error de descarga:[/red] {str(e)}")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        return False


# ─────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────

def _limpiar_temporales(archivos_temp: list[str], filepath: str):
    """Limpia archivos temporales y parciales."""
    for temp in archivos_temp:
        try:
            if os.path.exists(temp):
                os.remove(temp)
        except OSError:
            pass
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass
