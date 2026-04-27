"""
extractors.py — Extractores manuales de URLs de video para servidores de AnimeFLV
Sin dependencias pesadas: usa requests + Obscura (solo para bypass Cloudflare).
"""

import re
import os
import subprocess
import requests

# Ruta al ejecutable de Obscura (junto al script)
OBSCURA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "obscura.exe")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ─────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────

def _unpack_js(p: str, a: int, c: int, k: list[str]) -> str:
    """
    Desempaqueta código ofuscado con Dean Edwards JS Packer.
    Formato: eval(function(p,a,c,k,e,d){...}('código',base,count,'keywords'.split('|')))
    """
    def base_n(num: int, base: int) -> str:
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if num < base:
            return chars[num]
        return base_n(num // base, base) + chars[num % base]

    while c > 0:
        c -= 1
        if k[c]:
            p = re.sub(r'\b' + base_n(c, a) + r'\b', k[c], p)
    return p


def _extraer_packed_js(html: str) -> str | None:
    """Busca y desempaqueta el primer bloque eval(function(p,a,c,k,e,d)) en el HTML."""
    match = re.search(
        r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split",
        html,
        re.DOTALL,
    )
    if not match:
        return None

    p_str = match.group(1)
    a_val = int(match.group(2))
    c_val = int(match.group(3))
    k_list = match.group(4).split("|")

    return _unpack_js(p_str, a_val, c_val, k_list)


def _resolver_cloudflare(url: str) -> str | None:
    """
    Usa Obscura para descubrir la URL real detrás de Cloudflare.
    Obscura navega a la URL, pasa el challenge, y devuelve la URL final.
    """
    if not os.path.exists(OBSCURA_PATH):
        return None

    try:
        result = subprocess.run(
            [OBSCURA_PATH, "fetch", url,
             "--wait-until", "load", "--quiet",
             "--eval", "window.location.href"],
            capture_output=True,
            text=True,
            timeout=20,
        )

        for line in result.stdout.splitlines():
            line = line.strip()
            # La URL real es la que no pertenece al dominio original
            if line.startswith("http") and not any(
                d in line for d in ["streamwish.to", "Page loaded"]
            ):
                return line

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return None


# ─────────────────────────────────────────
# EXTRACTORES POR SERVIDOR
# ─────────────────────────────────────────

def extraer_streamwish(embed_url: str) -> str | None:
    """
    Extrae la URL M3U8 de StreamWish.
    Pipeline: Obscura (bypass CF) → requests (HTML) → unpack JS → M3U8
    """
    # 1. Resolver dominio real con Obscura
    real_url = _resolver_cloudflare(embed_url)
    if not real_url:
        return None

    # 2. Fetch directo al backend (sin Cloudflare)
    try:
        resp = SESSION.get(real_url, timeout=10)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None

    # 3. Desempaquetar el JS ofuscado
    unpacked = _extraer_packed_js(resp.text)
    if not unpacked:
        return None

    # 4. Extraer URL M3U8 del código desempaquetado
    #    Priorizar hls2 (URL completa con token) sobre hls4 (path relativo)
    m3u8_urls = re.findall(r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*', unpacked)
    if m3u8_urls:
        return m3u8_urls[0]

    # Fallback: buscar el campo "file" de JWPlayer
    file_match = re.search(r'"file"\s*:\s*"([^"]+)"', unpacked)
    if file_match:
        file_url = file_match.group(1)
        if file_url.startswith("http"):
            return file_url
        # Si es path relativo, construir URL completa
        from urllib.parse import urljoin
        return urljoin(real_url, file_url)

    return None


def extraer_yourupload(embed_url: str) -> str | None:
    """
    Extrae la URL MP4 de YourUpload.
    La URL está en la config de JWPlayer: file: 'https://vidcache.net.../video.mp4'
    """
    try:
        resp = SESSION.get(embed_url, timeout=10)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None

    # Buscar en JWPlayer config: file: 'url.mp4'
    match = re.search(r"file:\s*['\"]([^'\"]+\.mp4[^'\"]*)['\"]", resp.text)
    if match:
        return match.group(1)

    # Fallback: og:video meta tag
    match = re.search(r'og:video["\s]+content="([^"]+)"', resp.text)
    if match and ".mp4" in match.group(1):
        return match.group(1)

    return None


def extraer_netu(embed_url: str) -> str | None:
    """
    Extrae la URL M3U8 de Netu/HQQ.
    La URL .m3u8 está directamente en el HTML estático.
    """
    try:
        resp = SESSION.get(embed_url, timeout=10)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None

    # Buscar URLs M3U8 directas
    m3u8_urls = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', resp.text)
    if m3u8_urls:
        return m3u8_urls[0]

    # Buscar URLs MP4 directas (fallback)
    mp4_urls = re.findall(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', resp.text)
    # Filtrar data URIs y thumbnails
    for url in mp4_urls:
        if "thumb" not in url and "poster" not in url:
            return url

    return None


def extraer_okru(embed_url: str) -> str | None:
    """
    Intenta extraer URL de video de OK.ru.
    Los videos de OK.ru frecuentemente están borrados, así que esto puede fallar.
    """
    try:
        resp = SESSION.get(embed_url, timeout=10)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None

    # Buscar data-options con metadata de video
    import html as html_mod
    import json

    options_match = re.search(r'data-options="([^"]*)"', resp.text)
    if not options_match:
        return None

    try:
        opts = html_mod.unescape(options_match.group(1))
        opts_json = json.loads(opts)

        if "flashvars" in opts_json and "metadata" in opts_json["flashvars"]:
            meta = json.loads(opts_json["flashvars"]["metadata"])
            if "videos" in meta:
                # Ordenar por calidad (mayor primero)
                videos = sorted(meta["videos"], key=lambda v: v.get("name", ""), reverse=True)
                for v in videos:
                    url = v.get("url")
                    if url and url.startswith("http"):
                        return url
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return None


# ─────────────────────────────────────────
# DISPATCHER PRINCIPAL
# ─────────────────────────────────────────

# Mapeo servidor → función extractora
_EXTRACTORES = {
    "sw":     extraer_streamwish,
    "yu":     extraer_yourupload,
    "netu":   extraer_netu,
    "okru":   extraer_okru,
}


def extraer_url(servidor: str, embed_url: str) -> str | None:
    """
    Extrae la URL directa del video desde la URL embed de un servidor.
    Retorna la URL del stream (MP4 o M3U8) o None si no se puede extraer.
    """
    extractor = _EXTRACTORES.get(servidor)
    if extractor:
        return extractor(embed_url)
    return None


def servidores_soportados() -> list[str]:
    """Devuelve la lista de servidores que tienen extractor."""
    return list(_EXTRACTORES.keys())

def extraer_con_ytdlp(embed_url: str) -> str | None:
    """Fallback oculto que usa yt-dlp para desencriptar MegaCloud y Streamtape."""
    from app import console
    # console.print("[dim]Desencriptando servidor externo...[/dim]")
    try:
        # Importar ytdlp internamente sin hacer ruido
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
            'geturl': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(embed_url, download=False)
            if info and 'url' in info:
                return info['url']
    except Exception:
        pass
    return None
