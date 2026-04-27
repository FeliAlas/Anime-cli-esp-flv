"""
app.py — Anime CLI
Interfaz de terminal para buscar y ver anime desde AnimeFLV sin descargarlo.

Uso: python app.py
"""

import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.text import Text
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.columns import Columns

import scraper
import player
from downloader import descargar_video

console = Console()

# ─────────────────────────────────────────
# HELPERS DE UI
# ─────────────────────────────────────────

def limpiar():
    console.clear()

def cabecera():
    console.print(Panel(
        Text("🎌  ANIME CLI  🎌", justify="center", style="bold cyan"),
        subtitle="[dim]Desarrollado para AnimeFLV[/dim]",
        border_style="cyan",
    ))

def separador():
    console.print()

def esperar_enter():
    Prompt.ask("\n[dim]Presiona Enter para continuar[/dim]")


# ─────────────────────────────────────────
# PANTALLA: INICIO (NOVEDADES)
# ─────────────────────────────────────────

def pantalla_inicio() -> tuple[str, list[dict]]:
    limpiar()
    cabecera()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as prog:
        prog.add_task("Cargando novedades de AnimeFLV...", total=None)
        recientes = scraper.obtener_inicio()
        
    if recientes:
        tabla = Table(
            show_header=True,
            header_style="bold magenta",
            box=box.ROUNDED,
            expand=True,
            title="[bold yellow]Últimos Episodios Agregados[/bold yellow]",
            title_justify="left"
        )
        tabla.add_column("#",     style="dim", width=4, justify="right")
        tabla.add_column("Anime", style="bold white")
        tabla.add_column("Episodio", style="cyan", justify="center")
        
        for i, r in enumerate(recientes, 1):
            tabla.add_row(str(i), r["titulo"], r["episodio"])
            
        console.print(tabla)
    else:
        console.print("[yellow]⚠ No se pudieron cargar las novedades.[/yellow]")

    separador()
    console.print("[bold cyan]b.[/bold cyan] Buscar un anime")
    console.print("[bold cyan]0.[/bold cyan] Salir")
    if recientes:
        console.print(f"[dim]O elige un número (1-{len(recientes)}) para ver el episodio directamente.[/dim]")
    
    separador()
    opc = Prompt.ask("[bold]Selecciona una opción[/bold]", default="b").lower()
    return opc, recientes


# ─────────────────────────────────────────
# PANTALLA: BÚSQUEDA
# ─────────────────────────────────────────

def pantalla_busqueda() -> list[dict] | None:
    limpiar()
    cabecera()

    query = Prompt.ask("\n[bold yellow]🔍 Buscar anime[/bold yellow]").strip()
    if not query:
        return None

    separador()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as prog:
        prog.add_task(f"Buscando '[cyan]{query}[/cyan]'...", total=None)
        try:
            resultados = scraper.buscar_anime(query)
        except ConnectionError as e:
            console.print(f"\n[red]❌ Error de conexión:[/red] {e}")
            esperar_enter()
            return None

    if not resultados:
        console.print(f"\n[yellow]⚠  No se encontraron resultados para '[bold]{query}[/bold]'.[/yellow]")
        esperar_enter()
        return None

    return resultados


# ─────────────────────────────────────────
# PANTALLA: LISTA DE RESULTADOS
# ─────────────────────────────────────────

def mostrar_resultados(resultados: list[dict]) -> dict | None:
    limpiar()
    cabecera()

    tabla = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.ROUNDED,
        expand=True,
        show_lines=False,
    )
    tabla.add_column("#",       style="dim", width=4, justify="right")
    tabla.add_column("Título",  style="bold white", min_width=25)
    tabla.add_column("Tipo",    style="cyan", width=10)
    tabla.add_column("Rating",  style="yellow", width=8, justify="center")
    tabla.add_column("Sinopsis",style="dim", max_width=45)

    for i, anime in enumerate(resultados, 1):
        # Trunca la sinopsis si es muy larga
        sinopsis = anime["sinopsis"]
        if len(sinopsis) > 120:
            sinopsis = sinopsis[:117] + "..."

        tabla.add_row(
            str(i),
            anime["titulo"],
            anime["tipo"],
            anime["rating"],
            sinopsis,
        )

    console.print(tabla)
    separador()

    try:
        eleccion = IntPrompt.ask(
            f"[bold]Elige un anime[/bold] [dim](1-{len(resultados)}, 0 para volver)[/dim]",
            default=0,
        )
    except KeyboardInterrupt:
        return None

    if eleccion == 0 or eleccion > len(resultados):
        return None

    return resultados[eleccion - 1]


# ─────────────────────────────────────────
# PANTALLA: DETALLE DEL ANIME + EPISODIOS
# ─────────────────────────────────────────

def pantalla_anime(anime_elegido: dict) -> tuple[dict, int] | None:
    """Muestra info del anime y permite elegir un episodio. Retorna (info, numero_ep)."""
    limpiar()
    cabecera()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as prog:
        prog.add_task(f"Cargando [cyan]{anime_elegido['titulo']}[/cyan]...", total=None)
        try:
            info = scraper.obtener_info_anime(anime_elegido["id"])
        except ConnectionError as e:
            console.print(f"\n[red]❌ Error:[/red] {e}")
            esperar_enter()
            return None

    # Panel de info del anime
    estado_color = "green" if "emision" in info["estado"].lower() else "yellow"
    generos_str  = " · ".join(info["generos"]) if info["generos"] else "N/A"

    sinopsis = info["sinopsis"]
    if len(sinopsis) > 300:
        sinopsis = sinopsis[:297] + "..."

    console.print(Panel(
        f"[bold white]{info['titulo']}[/bold white]\n\n"
        f"[dim]{sinopsis}[/dim]\n\n"
        f"Estado: [{estado_color}]{info['estado']}[/{estado_color}]  |  "
        f"Géneros: [cyan]{generos_str}[/cyan]  |  "
        f"Episodios: [yellow]{len(info['episodios'])}[/yellow]",
        border_style="magenta",
        padding=(1, 2),
    ))
    separador()

    episodios = info["episodios"]
    if not episodios:
        console.print("[yellow]⚠  Este anime no tiene episodios disponibles.[/yellow]")
        esperar_enter()
        return None

    # Mostrar lista de episodios en columnas para ahorrar espacio
    ultimo = episodios[-1]["numero"]
    primero = episodios[0]["numero"]
    console.print(
        f"[bold]Episodios disponibles:[/bold] "
        f"[cyan]{primero}[/cyan] al [cyan]{ultimo}[/cyan]"
    )
    separador()

    # Si hay muchos episodios, mostrar en formato compacto
    if len(episodios) > 30:
        _mostrar_episodios_compacto(episodios)
    else:
        _mostrar_episodios_tabla(episodios)

    separador()

    try:
        numero_ep = IntPrompt.ask(
            f"[bold]¿Qué episodio ver?[/bold] [dim](0 para volver)[/dim]",
            default=0,
        )
    except KeyboardInterrupt:
        return None

    if numero_ep == 0:
        return None

    # Verificar que el episodio existe
    numeros_validos = {ep["numero"] for ep in episodios}
    if numero_ep not in numeros_validos:
        console.print(f"[red]❌ El episodio {numero_ep} no existe.[/red]")
        esperar_enter()
        return None

    return info, numero_ep


def _mostrar_episodios_tabla(episodios: list[dict]):
    """Tabla simple para animes con pocos episodios."""
    tabla = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    fila = []
    for ep in episodios:
        fila.append(f"[cyan]Ep {ep['numero']}[/cyan]")
        if len(fila) == 10:
            tabla.add_row(*fila)
            fila = []
    if fila:
        tabla.add_row(*fila)
    console.print(tabla)


def _mostrar_episodios_compacto(episodios: list[dict]):
    """Muestra los episodios en formato compacto cuando hay muchos."""
    nums = [str(ep["numero"]) for ep in episodios]

    # Agrupar en filas de 20
    filas = []
    for i in range(0, len(nums), 20):
        grupo = nums[i:i+20]
        filas.append("  ".join(f"[cyan]{n}[/cyan]" for n in grupo))

    for fila in filas:
        console.print(fila)


# ─────────────────────────────────────────
# REPRODUCCIÓN / DESCARGA
# ─────────────────────────────────────────

def accionar_episodio(info: dict, numero_ep: int):
    """Maneja Reproducir o Descargar."""
    
    limpiar()
    cabecera()
    console.print(f"\n[bold]Anime:[/bold] {info['titulo']} | [bold]Episodio:[/bold] {numero_ep}")
    separador()
    console.print("[cyan]1.[/cyan] Reproducir (VLC)")
    console.print("[cyan]2.[/cyan] Descargar (MP4 acelerado)")
    console.print("[cyan]0.[/cyan] Cancelar")
    
    try:
        opc = Prompt.ask("\n[bold]¿Qué deseas hacer?[/bold]", choices=["1", "2", "0"], default="1")
    except KeyboardInterrupt:
        return
        
    if opc == "0":
       return
       
    titulo = f"{info['titulo']} - Episodio {numero_ep}"
    
    console.print(f"\n[bold]▶  Preparando:[/bold] [cyan]{titulo}[/cyan]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as prog:
        prog.add_task("Obteniendo servidores de video...", total=None)
        try:
            servidores = scraper.obtener_servidores(info["anime_id"], numero_ep)
        except ConnectionError as e:
            console.print(f"[red]❌ Error:[/red] {e}")
            esperar_enter()
            return
            
    if not servidores:
        console.print("[red]❌ No se encontraron servidores para este episodio.[/red]")
        esperar_enter()
        return
        
    # Extraer url 
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as prog:
        prog.add_task("Resolviendo enlace directo...", total=None)
        enlace = player.intentar_extraer(servidores)
    
    if not enlace:
         console.print("[red]❌ No se pudo extraer la URL directa de ningún servidor disponible.[/red]")
         esperar_enter()
         return
         
    if opc == "1":
         # Reproducir
         calidad = player.obtener_calidad(enlace)
         if player.reproducir_en_vlc(enlace, titulo):
             console.print(f"\n[bold green]✅ Reproduciendo... [dim]({calidad})[/dim][/bold green]")
             console.print("[dim]VLC se abrió en una ventana separada.[/dim]")
         else:
             console.print(f"\n[bold red]❌ Error abriendo VLC.[/bold red]")
             esperar_enter()
    elif opc == "2":
         # Descargar
         exito = descargar_video(enlace, info['titulo'], numero_ep)
         if exito:
              console.print("\n[bold green]✅ Descarga finalizada con éxito.[/bold green]")
              esperar_enter()
         else:
              console.print("\n[bold red]❌ Falló la descarga acelerada.[/bold red]")
              esperar_enter()
              
    # Preguntar por siguiente (opcional o volver)
    # Buscamos si existe siguiente en la info (si la tenemos completa)
    if "episodios" in info and info["episodios"]:
        siguiente = numero_ep + 1
        numeros_validos = {ep["numero"] for ep in info["episodios"]}
        if siguiente in numeros_validos:
            if Prompt.ask(f"\n[bold yellow]¿Intentar con el episodio {siguiente}?[/bold yellow] (s/n)", default="s").lower() == "s":
                accionar_episodio(info, siguiente)


# ─────────────────────────────────────────
# LOOP PRINCIPAL
# ─────────────────────────────────────────

def main():
    while True:
        try:
            opc, recientes = pantalla_inicio()
            
            if opc == "0":
                console.print("\n[cyan]¡Hasta pronto! 👋[/cyan]")
                sys.exit(0)
            elif opc == "b":
                # Flujo de búsqueda normal
                resultados = pantalla_busqueda()
                if not resultados: continue
                
                anime_elegido = mostrar_resultados(resultados)
                if not anime_elegido: continue
                
                seleccion = pantalla_anime(anime_elegido)
                if not seleccion: continue
                
                info, numero_ep = seleccion
                accionar_episodio(info, numero_ep)
                
            elif opc.isdigit() and recientes:
                idx = int(opc) - 1
                if 0 <= idx < len(recientes):
                    r = recientes[idx]
                    # Obtenemos numero de ep del string
                    try:
                        num_ep = int(re.search(r'(\d+)', r["episodio"]).group(1))
                    except:
                        num_ep = 1
                        
                    # Para el home, como solo tenemos el slug y ep, 
                    # lo mejor es tratar de obtener info completa primero para tener la lista de episodios
                    # y permitir el flujo de "siguiente"
                    anime_falso = {"id": r["serie_slug"], "titulo": r["titulo"]}
                    seleccion = pantalla_anime(anime_falso)
                    if seleccion:
                        info, num_ep = seleccion
                        accionar_episodio(info, num_ep)
                else:
                    console.print("[red]Opción inválida.[/red]")
                    esperar_enter()
            else:
                console.print("[red]Opción no reconocida.[/red]")
                esperar_enter()
                
        except KeyboardInterrupt:
            console.print("\n\n[dim]¡Acción cancelada! Volviendo al inicio...[/dim]")
            import time
            time.sleep(1)
            continue
        except Exception as e:
            console.print(f"\n[bold red]Hubo un error inesperado:[/bold red] {e}")
            esperar_enter()

if __name__ == "__main__":
    main()
