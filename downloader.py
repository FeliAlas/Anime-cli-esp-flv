import os
import subprocess
import requests
from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

def descargar_video(url: str, nombre_anime: str, numero_ep: int|str) -> bool:
    """
    Descarga el video. Para MP4 usa requests, para M3U8 usa ffmpeg.
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
    console.print(f"\n[cyan]Descargando en:[/cyan] {filepath}")
    
    # Si es directo MP4
    if url.endswith('.mp4') or "video/mp4" in url or "mp4" in url.lower() and ".m3u8" not in url.lower():
        return _descargar_mp4(url, filepath)
    else:
        # Usar yt-dlp nativamente para descargas M3U8 hiper-aceleradas
        return _descargar_m3u8_acelerado(url, filepath)

def _descargar_mp4(url: str, filepath: str) -> bool:
    """Descarga directa de MP4 mostrando progreso con Rich."""
    try:
        response = requests.get(url, stream=True, timeout=10)
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
                for chunk in response.iter_content(chunk_size=8192):
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

def _descargar_m3u8_acelerado(url: str, filepath: str) -> bool:
    """
    Usa yt-dlp para descargar M3U8 conectándose hasta a 15 fragmentos simultáneamente,
    exprimiendo el ancho de banda al 100%.
    """
    from app import console
    import yt_dlp
    
    console.print("[dim]INICIANDO DESCARGA (YT-DLP)...[/dim]")
    
    # yt-dlp no soporta crear la carpeta directamente a veces, nos aseguramos:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    opciones = {
        'outtmpl': filepath,
        'concurrent_fragment_downloads': 3,  # Se baja de 15 a 3 para evitar baneos por DDOS (archivos cortados/rotos)
        'retries': 20,                       # Intentar reconectar si se corta
        'fragment_retries': 20,
        'quiet': False,
        'no_warnings': True,
        'format': 'bestvideo+bestaudio/best',
    }
    
    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            resultado = ydl.download([url])
            return resultado == 0
    except Exception as e:
        console.print(f"[red]❌ Error de descarga acelerada:[/red] {str(e)}")
        if os.path.exists(filepath):
            try: os.remove(filepath)
            except: pass
        return False
