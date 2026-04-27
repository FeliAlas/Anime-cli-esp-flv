"""
player.py — Extrae la URL directa del video y abre VLC para transmitir
Usa extractores manuales por servidor y VLC como reproductor.
Sin descargar nada a disco.
"""

import subprocess
import os
import re
import requests
import extractors

# Servidores ordenados por preferencia (los que tienen extractor primero)
PREFERENCIA_SERVIDORES = [
    "sw",           # StreamWish — extractor con Obscura + JS unpacker
    "yu",           # YourUpload — extractor directo (MP4)
    "netu",         # Netu/HQQ — extractor directo (M3U8)
    "okru",         # OK.ru — extractor parcial
    "stape",        # Streamtape — sin extractor (URLs suelen estar muertas)
    "fembed",       # Fembed — sin extractor (servidor muerto)
    "mega",         # MEGA — sin extractor (cifrado propietario)
    "maru",         # Mail.ru — sin extractor (frecuentes 404)
]

# Ruta de VLC en Windows (ruta por defecto)
VLC_PATHS_WINDOWS = [
    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
]


def ordenar_servidores(servidores: list[dict]) -> list[dict]:
    """Ordena los servidores según la preferencia definida."""
    def prioridad(s):
        nombre = s["servidor"].lower()
        try:
            return PREFERENCIA_SERVIDORES.index(nombre)
        except ValueError:
            return len(PREFERENCIA_SERVIDORES)  # Los no listados van al final

    return sorted(servidores, key=prioridad)


def _es_url_valida(url: str) -> bool:
    """
    Filtra URLs que no son streams reales.
    Descarta data URIs (data:video/mp4;base64,...) y URLs no-HTTP.
    """
    if url.startswith("data:"):
        return False
    if not url.startswith(("http://", "https://")):
        return False
    return True

def obtener_calidad(url: str) -> str:
    """Intenta descargar el manifest M3U8 o inspeccionar el MP4 para obtener la calidad."""
    if ".m3u8" in url:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                # Buscar la máxima resolución en el manifest
                resoluciones = re.findall(r'RESOLUTION=(\d+x\d+)', r.text)
                if resoluciones:
                    # Parsear "WIDTHxHEIGHT" y ordenar por alto (HEIGHT)
                    sizes = []
                    for res in resoluciones:
                        w, h = res.split('x')
                        sizes.append((int(w), int(h)))
                    max_res = max(sizes, key=lambda x: x[1])
                    return f"{max_res[0]}x{max_res[1]} ({max_res[1]}p)"
                else:
                    # Alternativamente, si hay un ancho de banda alto, es HD
                    if "BANDWIDTH" in r.text:
                        return "Auto (HLS)"
        except Exception:
            return "HLS"
        return "HLS"
    elif ".mp4" in url:
        return "MP4 Original"
    
    return "Desconocida"


def encontrar_vlc() -> str | None:
    """Busca el ejecutable de VLC en las rutas conocidas de Windows."""
    # Primero intenta si vlc está en el PATH
    try:
        result = subprocess.run(
            ["vlc", "--version"],
            capture_output=True,
            timeout=3,
        )
        if result.returncode == 0:
            return "vlc"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Si no, busca en las rutas por defecto de Windows
    for ruta in VLC_PATHS_WINDOWS:
        if os.path.exists(ruta):
            return ruta

    return None


def reproducir_en_vlc(stream_url: str, titulo: str = "Anime CLI") -> bool:
    """
    Abre VLC con la URL del stream. VLC transmite directo sin guardar nada.
    Retorna True si VLC se abrió correctamente.
    """
    vlc = encontrar_vlc()
    if not vlc:
        return False

    try:
        # --meta-title muestra el título en la ventana de VLC
        subprocess.Popen(
            [vlc, stream_url, f"--meta-title={titulo}", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def intentar_extraer(servidores: list[dict]) -> str | None:
    """Busca en los servidores y retorna la URL directa del video (M3U8 o MP4) sin usar VLC."""
    if not servidores:
        return None

    # Ordenar priorizando los que dicen "Directo" o tienen extractor soportado
    soportados = extractors.servidores_soportados()
    
    def get_score(s):
        if "directo" in s["titulo"].lower() or s["url"].endswith((".m3u8", ".mp4")):
            return 0
        match = next((e for e in PREFERENCIA_SERVIDORES if e in s["url"]), None)
        return PREFERENCIA_SERVIDORES.index(match) + 1 if match else 999
        
    servidores.sort(key=get_score)

    for servidor in servidores:
        srv_id    = servidor["servidor"] if "servidor" in servidor else None
        embed_url = servidor["url"]

        # Si ya es un video directo o Miruro mandó M3U8, no necesita extractor
        if "directo" in servidor["titulo"].lower() or embed_url.endswith((".m3u8", ".mp4")):
            if _es_url_valida(embed_url):
                 return embed_url
                 
        # Si no hay ID o no es soportado, se salta
        if not srv_id and not next((e for e in soportados if e in embed_url), None):
             continue
             
        if not srv_id:
             srv_id = next((e for e in soportados if e in embed_url), None)

        if srv_id in soportados:
             stream_url = extractors.extraer_url(srv_id, embed_url)
             if stream_url and _es_url_valida(stream_url):
                 return stream_url

    return None


def intentar_reproducir(servidores: list[dict], titulo: str = "") -> tuple[bool, str]:
    """
    Intenta extraer y reproducir desde cada servidor en orden de preferencia.
    Solo intenta servidores que tienen extractor disponible.
    Retorna (éxito: bool, mensaje: str)
    """
    if not servidores:
        return False, "No hay servidores disponibles para este episodio."

    servidores_ordenados = ordenar_servidores(servidores)
    soportados = extractors.servidores_soportados()
    intentados = []

    for servidor in servidores_ordenados:
        nombre    = servidor["titulo"]
        srv_id    = servidor["servidor"]
        embed_url = servidor["url"]

        # Solo intentar servidores con extractor
        if srv_id not in soportados:
            continue

        intentados.append(nombre)

        # Extraer URL directa con el extractor manual
        stream_url = extractors.extraer_url(srv_id, embed_url)

        if stream_url and _es_url_valida(stream_url):
            # Tentar obtener calidad
            calidad = obtener_calidad(stream_url)
            
            # Abrir VLC con esa URL
            if reproducir_en_vlc(stream_url, titulo):
                return True, f"Reproduciendo desde {nombre} [dim cyan]({calidad})[/dim cyan]"
            else:
                return False, (
                    "VLC no encontrado. Instálalo desde https://www.videolan.org/vlc/ "
                    "o agrégalo al PATH."
                )

    if not intentados:
        nombres = [s["titulo"] for s in servidores]
        return False, (
            f"Ningún servidor disponible ({', '.join(nombres)}) tiene extractor. "
            f"Servidores soportados: {', '.join(soportados)}"
        )

    return False, (
        f"No se pudo extraer el video de: {', '.join(intentados)}. "
        "Prueba de nuevo en unos minutos."
    )
