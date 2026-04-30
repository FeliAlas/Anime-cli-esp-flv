"""
scraper.py — Extrae información de AnimeFLV y MonosChinos
Busca animes, obtiene episodios y extrae URLs de servidores de video.
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# Headers que simulan un navegador real para evitar bloqueos
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

class AnimeFLV:
    BASE_URL = "https://www3.animeflv.net"
    
    @staticmethod
    def buscar_anime(query: str) -> list[dict]:
        url = f"{AnimeFLV.BASE_URL}/browse?q={requests.utils.quote(query)}"
        try:
            resp = SESSION.get(url, headers={"Referer": AnimeFLV.BASE_URL}, timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            return []

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
                "proveedor": "AnimeFLV",
                "titulo":   titulo_tag.text.strip(),
                "id":       anime_id,
                "url":      AnimeFLV.BASE_URL + href,
                "tipo":     tipo_tag.text.strip() if tipo_tag else "Anime",
                "sinopsis": sinop_tag.text.strip() if sinop_tag else "Sin descripción.",
                "rating":   rating_tag.text.strip() if rating_tag else "N/A",
            })

        return resultados

    @staticmethod
    def obtener_info_anime(anime_id: str) -> dict:
        url = f"{AnimeFLV.BASE_URL}/anime/{anime_id}"
        try:
            resp = SESSION.get(url, headers={"Referer": AnimeFLV.BASE_URL}, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(f"Error obteniendo info del anime en AnimeFLV: {e}")

        soup = BeautifulSoup(resp.text, "html.parser")

        titulo   = soup.select_one("h1.Title")
        sinopsis = soup.select_one("div.Description p")
        estado   = soup.select_one("p.AnmStts span")
        generos  = [g.text for g in soup.select("nav.Nvgnrs a")]

        episodios = []
        for script in soup.find_all("script"):
            if "var episodes" in (script.string or ""):
                match = re.search(r"var episodes\s*=\s*(\[.*?\]);", script.string, re.DOTALL)
                if match:
                    try:
                        datos = json.loads(match.group(1))
                        episodios = [
                            {"numero": ep[0], "ep_id": ep[1]}
                            for ep in reversed(datos)
                        ]
                    except json.JSONDecodeError:
                        pass
                break

        return {
            "proveedor": "AnimeFLV",
            "titulo":    titulo.text.strip() if titulo else anime_id,
            "sinopsis":  sinopsis.text.strip() if sinopsis else "Sin descripción.",
            "estado":    estado.text.strip() if estado else "Desconocido",
            "generos":   generos,
            "episodios": episodios,
            "anime_id":  anime_id,
        }

    @staticmethod
    def obtener_servidores(anime_id: str, numero_ep: int) -> list[dict]:
        url = f"{AnimeFLV.BASE_URL}/ver/{anime_id}-{numero_ep}"
        try:
            resp = SESSION.get(url, headers={"Referer": AnimeFLV.BASE_URL}, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(f"Error obteniendo el episodio en AnimeFLV: {e}")

        soup = BeautifulSoup(resp.text, "html.parser")
        for script in soup.find_all("script"):
            texto = script.string or ""
            if "var videos" not in texto:
                continue

            match = re.search(r"var videos\s*=\s*(\{.+\}|\[.+\])\s*;", texto, re.DOTALL)
            if not match:
                continue

            try:
                datos = json.loads(match.group(1))
                if isinstance(datos, dict):
                    servidores_raw = datos.get("SUB", [])
                    if not servidores_raw:
                        servidores_raw = datos.get("LAT", [])
                    if not servidores_raw:
                        for valor in datos.values():
                            if isinstance(valor, list) and valor:
                                servidores_raw = valor
                                break
                elif isinstance(datos, list) and datos:
                    servidores_raw = datos[0] if datos else []
                else:
                    servidores_raw = []

                servidores = []
                for s in servidores_raw:
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

class MonosChinos:
    BASE_URL = "https://monoschino2.com"

    @staticmethod
    def buscar_anime(query: str) -> list[dict]:
        url = f"{MonosChinos.BASE_URL}/directorio/anime?q={requests.utils.quote(query)}"
        try:
            resp = SESSION.get(url, headers={"Referer": MonosChinos.BASE_URL}, timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        resultados = []

        for articulo in soup.select("article"):
            link_tag = articulo.select_one("a")
            if not link_tag:
                continue
            
            titulo_tag = articulo.select_one("a > p")
            if not titulo_tag:
                titulo_tag = articulo.select_one("p")
                
            tipo_tag = articulo.select_one(".tipo")
            estado_tag = articulo.select_one(".figure-title p")
            
            href = link_tag.get("href", "")
            if not href.startswith("http"):
                href = MonosChinos.BASE_URL + href
                
            anime_id = href.split("/")[-1]
            
            nombre_anime = titulo_tag.text.strip() if titulo_tag else "Desconocido"

            resultados.append({
                "proveedor": "MonosChinos",
                "titulo":   nombre_anime,
                "id":       link_tag.get("href", ""),
                "url":      href,
                "tipo":     tipo_tag.text.strip() if tipo_tag else "Anime",
                "sinopsis": "Ver en MonosChinos",
                "rating":   estado_tag.text.strip() if estado_tag else "N/A",
            })

        return resultados

    @staticmethod
    def obtener_info_anime(anime_id: str) -> dict:
        # anime_id is the relative path, e.g. /latino/naruto or /one-piece-tv
        url = f"{MonosChinos.BASE_URL}{anime_id}" if str(anime_id).startswith("/") else f"{MonosChinos.BASE_URL}/anime/{anime_id}"
        try:
            resp = SESSION.get(url, headers={"Referer": MonosChinos.BASE_URL}, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(f"Error obteniendo info del anime en MonosChinos: {e}")

        soup = BeautifulSoup(resp.text, "html.parser")

        titulo_tag = soup.find("h1")
        sinopsis_tag = soup.find("div", class_="sinopsis")
        estado_tag = soup.find("p", class_="status")
        
        generos = [a.text.strip() for a in soup.select(".generos a, .genres a")]

        # Extract slug for AJAX
        slug = anime_id.strip("/").split("/")[-1]
        
        # Extract episodes via AJAX pagination
        episodios = []
        start = 0
        while True:
            ajax_url = f"{MonosChinos.BASE_URL}{anime_id}?id={slug}&load=episodes&start={start}"
            try:
                ajax_resp = SESSION.get(ajax_url, headers={"Referer": url}, timeout=10)
                if not ajax_resp.text.strip():
                    break
                
                ajax_soup = BeautifulSoup(ajax_resp.text, "html.parser")
                items = ajax_soup.find_all("a", href=True)
                if not items:
                    break
                
                chunk_found = 0
                for a in items:
                    href = a["href"]
                    if "/ver/" in href:
                        # e.g. /ver/one-piece-tv-1 or /ver/latino/naruto-1
                        # Extract episode number from the end of the URL
                        match = re.search(r"-(\d+)$", href)
                        if match:
                            num = int(match.group(1))
                            if not any(e["numero"] == num for e in episodios):
                                episodios.append({
                                    "numero": num,
                                    "ep_id": href
                                })
                                chunk_found += 1
                
                if chunk_found == 0:
                    break
                
                start += 16 # MonosChinos seems to use chunks of 16 or 20
                if start > 2000: break # Safety break
            except:
                break
        
        episodios.sort(key=lambda x: x["numero"])

        return {
            "proveedor": "MonosChinos",
            "titulo":    titulo_tag.text.strip() if titulo_tag else str(anime_id).split("/")[-1],
            "sinopsis":  sinopsis_tag.text.strip() if sinopsis_tag else "Sin descripción.",
            "estado":    estado_tag.text.strip() if estado_tag else "Desconocido",
            "generos":   generos,
            "episodios": episodios,
            "anime_id":  anime_id,
        }

    @staticmethod
    def obtener_servidores(anime_id: str, numero_ep: int, info: dict = None) -> list[dict]:
        ep_url = None
        if info and "episodios" in info:
            for ep in info["episodios"]:
                if ep["numero"] == numero_ep:
                    ep_url = ep.get("ep_id")
                    break
                    
        if not ep_url:
            # Fallback reconstruction
            if str(anime_id).startswith("/"):
                parts = str(anime_id).strip("/").split("/")
                ep_url = f"{MonosChinos.BASE_URL}/ver/{parts[-1]}-{numero_ep}"
            else:
                ep_url = f"{MonosChinos.BASE_URL}/ver/{anime_id}-{numero_ep}"
                
        if not str(ep_url).startswith("http"):
            ep_url = f"{MonosChinos.BASE_URL}{ep_url}"

        try:
            resp = SESSION.get(ep_url, headers={"Referer": MonosChinos.BASE_URL}, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(f"Error obteniendo el episodio en MonosChinos: {e}")

        soup = BeautifulSoup(resp.text, "html.parser")
        
        tabs_dict = {}
        for script in soup.find_all("script"):
            texto = script.string or ""
            if "tabsArray" in texto:
                matches = re.finditer(r"tabsArray\['([^']+)'\]\s*=\s*[\"'](.*?)[\"'];", texto)
                for m in matches:
                    tab_id = m.group(1)
                    html_content = m.group(2)
                    src_match = re.search(r"src=\\?[\"']([^\"'\\]+)\\?[\"']", html_content)
                    if src_match:
                        tabs_dict[tab_id] = src_match.group(1)

        servidores = []
        server_list = soup.find(class_="episode-page__servers-list")
        if server_list:
            for li in server_list.find_all("a"):
                href = li.get("href", "")
                if href.startswith("#vid"):
                    tab_id = href.replace("#vid", "")
                    nombre = li.text.strip()
                    url = tabs_dict.get(tab_id)
                    if url:
                        servidores.append({
                            "servidor": nombre,
                            "titulo": nombre,
                            "url": url
                        })
        return servidores

# ─────────────────────────────────────────
# FACHADA PÚBLICA
# ─────────────────────────────────────────

def obtener_inicio() -> list[dict]:
    try:
        resp = SESSION.get(AnimeFLV.BASE_URL, headers={"Referer": AnimeFLV.BASE_URL}, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        lista = []
        for item in soup.select('.ListEpisodios li a')[:10]:
            link = AnimeFLV.BASE_URL.rstrip('/') + item['href']
            titulo_tag = item.select_one('.Title')
            numero_tag = item.select_one('.Capi')
            if not titulo_tag: continue
            
            slug_match = re.search(r'/ver/([^\/]+)-\d+$', item['href'])
            lista.append({
                "proveedor": "AnimeFLV",
                "titulo": titulo_tag.text.strip(),
                "episodio": numero_tag.text.strip() if numero_tag else "Episodio ?",
                "url_ver": link,
                "serie_slug": slug_match.group(1) if slug_match else ""
            })
        return lista
    except Exception:
        return []

def buscar_anime(query: str) -> list[dict]:
    resultados = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(AnimeFLV.buscar_anime, query)
        f2 = executor.submit(MonosChinos.buscar_anime, query)
        
        try:
            resultados.extend(f1.result())
        except Exception:
            pass
        try:
            resultados.extend(f2.result())
        except Exception:
            pass
            
    return resultados

def obtener_info_anime(anime_elegido: dict) -> dict:
    proveedor = anime_elegido.get("proveedor", "AnimeFLV") if isinstance(anime_elegido, dict) else "AnimeFLV"
    anime_id = anime_elegido.get("id") if isinstance(anime_elegido, dict) else anime_elegido

    if proveedor == "MonosChinos":
        return MonosChinos.obtener_info_anime(anime_id)
    return AnimeFLV.obtener_info_anime(anime_id)

def obtener_servidores(info: dict, numero_ep: int) -> list[dict]:
    proveedor = info.get("proveedor", "AnimeFLV")
    if proveedor == "MonosChinos":
        return MonosChinos.obtener_servidores(info["anime_id"], numero_ep, info)
    return AnimeFLV.obtener_servidores(info["anime_id"], numero_ep)
