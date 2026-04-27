"""
scraper.py — Extrae información de AnimeFLV
Busca animes, obtiene episodios y extrae URLs de servidores de video.
"""

import re
import json
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www3.animeflv.net"

# Headers que simulan un navegador real para evitar bloqueos
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": BASE_URL,
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def obtener_inicio() -> list[dict]:
    """Retorna una lista con los últimos episodios agregados a la portada de AnimeFLV."""
    try:
        resp = SESSION.get(BASE_URL, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        lista = []
        # .ListEpisodios li a
        for item in soup.select('.ListEpisodios li a')[:10]: # Devolvemos los ultimos 10
            # Extraer link
            link = BASE_URL.rstrip('/') + item['href']  # ej: /ver/naruto-1
            titulo_tag = item.select_one('.Title')
            numero_tag = item.select_one('.Capi')
            
            if not titulo_tag: continue
            
            titulo = titulo_tag.text.strip()
            numero = numero_tag.text.strip() if numero_tag else "Episodio ?"
            
            # El href suele ser /ver/nombre-del-anime-NUMERO
            # Extraemos el slug del anime base
            slug_match = re.search(r'/ver/([^\/]+)-\d+$', item['href'])
            slug = slug_match.group(1) if slug_match else ""
            
            lista.append({
                "titulo": titulo,
                "episodio": numero,
                "url_ver": link,
                "serie_slug": slug
            })
        return lista
    except Exception as e:
        # Silently fail or return empty list for the UI to handle
        return []


# ─────────────────────────────────────────
# BÚSQUEDA
# ─────────────────────────────────────────

def buscar_anime(query: str) -> list[dict]:
    """
    Busca animes por nombre en AnimeFLV.
    Devuelve lista de dicts: {titulo, id, url, tipo, sinopsis, rating}
    """
    url = f"{BASE_URL}/browse?q={requests.utils.quote(query)}"
    try:
        resp = SESSION.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ConnectionError(f"Error conectando a AnimeFLV: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    resultados = []

    for articulo in soup.select("ul.ListAnimes article.Anime"):
        titulo_tag = articulo.select_one("a h3")
        link_tag   = articulo.select_one("a")
        tipo_tag   = articulo.select_one("a span.Type")
        sinop_tag  = articulo.select_one("div.Description p:nth-of-type(2)")
        rating_tag = articulo.select_one("div.Calify")

        if not titulo_tag or not link_tag:
            continue

        href = link_tag.get("href", "")
        anime_id = href.replace("/anime/", "").strip("/")

        resultados.append({
            "titulo":   titulo_tag.text.strip(),
            "id":       anime_id,
            "url":      BASE_URL + href,
            "tipo":     tipo_tag.text.strip() if tipo_tag else "Anime",
            "sinopsis": sinop_tag.text.strip() if sinop_tag else "Sin descripción.",
            "rating":   rating_tag.text.strip() if rating_tag else "N/A",
        })

    return resultados


# ─────────────────────────────────────────
# INFO + EPISODIOS
# ─────────────────────────────────────────

def obtener_info_anime(anime_id: str) -> dict:
    """
    Obtiene la info completa de un anime y su lista de episodios.
    Devuelve: {titulo, sinopsis, estado, generos, episodios: [{numero, id}]}
    """
    url = f"{BASE_URL}/anime/{anime_id}"
    try:
        resp = SESSION.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ConnectionError(f"Error obteniendo info del anime: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")

    titulo   = soup.select_one("h1.Title")
    sinopsis = soup.select_one("div.Description p")
    estado   = soup.select_one("p.AnmStts span")
    generos  = [g.text for g in soup.select("nav.Nvgnrs a")]

    # La lista de episodios está en una variable JS dentro de un <script>
    # Formato: var episodes = [[num, id], [num, id], ...]
    episodios = []
    for script in soup.find_all("script"):
        if "var episodes" in (script.string or ""):
            match = re.search(r"var episodes\s*=\s*(\[.*?\]);", script.string, re.DOTALL)
            if match:
                try:
                    datos = json.loads(match.group(1))
                    # AnimeFLV los devuelve en orden inverso, los invertimos
                    episodios = [
                        {"numero": ep[0], "ep_id": ep[1]}
                        for ep in reversed(datos)
                    ]
                except json.JSONDecodeError:
                    pass
            break

    return {
        "titulo":    titulo.text.strip() if titulo else anime_id,
        "sinopsis":  sinopsis.text.strip() if sinopsis else "Sin descripción.",
        "estado":    estado.text.strip() if estado else "Desconocido",
        "generos":   generos,
        "episodios": episodios,
        "anime_id":  anime_id,
    }


# ─────────────────────────────────────────
# SERVIDORES DE VIDEO
# ─────────────────────────────────────────

def obtener_servidores(anime_id: str, numero_ep: int) -> list[dict]:
    """
    Obtiene los servidores de video de un episodio específico.
    Devuelve lista de dicts: {servidor, titulo, url}
    
    Los servidores típicos de AnimeFLV son:
    streamtape, okru (ok.ru), yourupload, fembed, natsuki/izanagi
    """
    url = f"{BASE_URL}/ver/{anime_id}-{numero_ep}"
    try:
        resp = SESSION.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ConnectionError(f"Error obteniendo el episodio: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Los servidores están en: var videos = {"SUB": [...], "LAT": [...]}
    # (formato anterior era un array anidado: [[...], [...]])
    for script in soup.find_all("script"):
        texto = script.string or ""
        if "var videos" not in texto:
            continue

        # Capturar todo el valor JSON después de "var videos ="
        # Usamos greedy match hasta el ; para capturar objetos anidados completos
        match = re.search(r"var videos\s*=\s*(\{.+\}|\[.+\])\s*;", texto, re.DOTALL)
        if not match:
            continue

        try:
            datos = json.loads(match.group(1))

            # Determinar la lista de servidores según el formato
            if isinstance(datos, dict):
                # Formato nuevo: {"SUB": [...], "LAT": [...]}
                # Priorizar SUB, luego LAT, luego cualquier clave disponible
                servidores_raw = datos.get("SUB", [])
                if not servidores_raw:
                    servidores_raw = datos.get("LAT", [])
                if not servidores_raw:
                    # Tomar la primera lista disponible
                    for valor in datos.values():
                        if isinstance(valor, list) and valor:
                            servidores_raw = valor
                            break
            elif isinstance(datos, list) and datos:
                # Formato antiguo: [[{...}, ...], [{...}, ...]]
                servidores_raw = datos[0] if datos else []
            else:
                servidores_raw = []

            servidores = []
            for s in servidores_raw:
                # La URL puede estar en "code" o "url"
                embed_url = s.get("code") or s.get("url", "")
                if embed_url:
                    servidores.append({
                        "servidor": s.get("server", "unknown"),
                        "titulo":   s.get("title", "Desconocido"),
                        "url":      embed_url,
                    })
            return servidores

        except (json.JSONDecodeError, IndexError, TypeError):
            pass

    return []
