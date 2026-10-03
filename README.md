# Arcón de Pancheim

Página con todo lo guardado en los cofres, vehículos y tumbas del mundo de
Valheim `pancheim`, más el estado de fermentadores, fundiciones y hornos. Se
arma sola cada 30 minutos: una acción de GitHub baja el mundo por FTP desde
G-Portal, lo lee y publica la página en GitHub Pages.

No incluye lo que cada jugador lleva encima: eso vive en la PC de cada uno, no
en el servidor.

## Puesta en marcha

1. En el panel de G-Portal, buscá los datos de acceso FTP del servidor
   (servidor, puerto, usuario y contraseña).
2. En este repositorio: **Settings → Secrets and variables → Actions → New
   repository secret**, y cargá:

   | Secreto | Valor |
   |---|---|
   | `FTP_HOST` | el servidor FTP |
   | `FTP_PORT` | el puerto (si no lo cargás, usa 21) |
   | `FTP_USER` | el usuario |
   | `FTP_PASS` | la contraseña |
   | `FTP_TLS` | `1` solo si G-Portal pide FTPS; si no, no lo cargues |
   | `FTP_WORLD_DIR` | opcional; por defecto `save/worlds_local/gportal_unzip_ppqaovp_` |

3. **Actions → Actualizar inventario → Run workflow** para la primera
   corrida. Si falla en "Bajar el mundo", revisá los secretos y la carpeta.

La página queda en la dirección de GitHub Pages del repositorio (ver Settings → Pages).

## Para leer sin navegador

Además de la página, cada corrida publica:

- [`inventario.md`](https://pancheim.github.io/inventario.md): resumen en texto
  (totales por item, estaciones, cofres uno por uno). Sirve para leerlo de
  corrido o pasárselo a un asistente.
- [`inventario.json`](https://pancheim.github.io/inventario.json): los mismos
  datos, exactos, para scripts o agentes.

## Cosas a saber

- El servidor guarda aunque nadie juegue, así que la corrida programada compara
  el contenido (cofres, estaciones y plano) con el publicado (`estado.txt`) y,
  si es igual, no republica. A mano o al subir código se arma siempre.
- GitHub pausa las tareas programadas si el repositorio pasa 60 días sin
  actividad. Se reactivan desde la pestaña Actions.
- La "base" es todo lo que está a menos de 150 m de (1290, -195). Se cambia
  con las variables `BASE_X`, `BASE_Z` y `BASE_RADIUS` en el paso "Armar la
  pagina" del workflow.
- Probar en local con una carpeta de mundo ya bajada:

  ```
  python arcon/build.py <carpeta_del_mundo> site/index.html
  ```

## De dónde sale cada cosa

- `arcon/zdo.py` lee el formato de guardado por chunks de Valheim (world
  version 41).
- `data/hashes.json` traduce los identificadores del guardado a nombres de
  prefab; sale de la lista de prefabs de la documentación de Jötunn.
- Los íconos de los items se bajan de la documentación de Jötunn al armar la
  página y quedan en caché entre corridas.
- `data/names.json` tiene el nombre en español y la categoría de cada item,
  tal como los muestra el juego.
