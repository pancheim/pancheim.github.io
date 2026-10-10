"""Baja la carpeta del mundo desde el FTP de G-Portal.

Lee la configuracion de variables de entorno (en GitHub van como secretos):
  FTP_HOST, FTP_USER, FTP_PASS     obligatorias
  FTP_PORT                         por defecto 21
  FTP_TLS                          "1" para FTPS explicito
  FTP_WORLD_DIR                    carpeta del mundo en el servidor,
                                   por defecto save/worlds_local/gportal_unzip_ppqaovp_

A cada archivo bajado le pone la fecha que tiene en el servidor, porque de ahi
sale la hora del guardado que muestra la pagina.

Uso: python arcon/fetch_ftp.py <carpeta_destino>
"""
import ftplib
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone

MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _utc(dt):
    return dt.replace(tzinfo=timezone.utc).timestamp()


def _from_list_line(parts):
    """Fecha de una linea estilo ls: 'Oct  2 19:26' (este anio) u 'Oct  2  2025'."""
    mon, day, hm = parts[5], int(parts[6]), parts[7]
    now = datetime.now(timezone.utc)
    if ":" in hm:
        h, m = map(int, hm.split(":"))
        dt = datetime(now.year, MONTHS[mon], day, h, m)
        if dt > now.replace(tzinfo=None):
            dt = dt.replace(year=now.year - 1)
        return _utc(dt)
    return _utc(datetime(int(hm), MONTHS[mon], day))


def list_files(ftp):
    """{nombre: fecha (epoch) o None} de la carpeta actual, y de donde salieron las fechas.

    El FTP de G-Portal no implementa NLST, asi que se prueba MLSD y despues LIST."""
    try:
        out = {}
        for name, facts in ftp.mlsd():
            if facts.get("type") == "file":
                mod = facts.get("modify")
                out[name] = _utc(datetime.strptime(mod[:14], "%Y%m%d%H%M%S")) if mod else None
        return out, "MLSD"
    except ftplib.error_perm:
        pass
    lines = []
    ftp.retrlines("LIST", lines.append)
    out = {}
    for line in lines:
        if not line or line.startswith(("d", "total")):
            continue
        parts = line.split(None, 8)
        try:
            out[parts[-1]] = _from_list_line(parts)
        except (ValueError, KeyError, IndexError):
            out[parts[-1]] = None
    return out, "LIST"


ATTEMPTS, WAIT = 3, 30
CHUNK = re.compile(r"^(.*)_(\d+)\.chunk$")


def current_files(files):
    """Los _main del guardado mas alto y, de cada chunk, solo su version mas nueva
    (mientras el servidor guarda pueden convivir la vieja y la nueva)."""
    mains = [n for n in files if n.startswith("_main.")]
    if not mains:
        return None, []
    latest = max(int(n.split(".")[1]) for n in mains)
    newest = {}
    for n in files:
        m = CHUNK.match(n)
        if m and (m.group(1) not in newest or int(m.group(2)) > newest[m.group(1)][0]):
            newest[m.group(1)] = (int(m.group(2)), n)
    return latest, [n for n in files if n.startswith(f"_main.{latest}.")] + [n for _, n in newest.values()]


def download(ftp, dest, remote):
    files, source = list_files(ftp)
    latest, wanted = current_files(files)
    if latest is None:
        sys.exit(f"No hay archivos _main en {remote}: revisa FTP_WORLD_DIR.")
    dated = 0
    for n in wanted:
        path = os.path.join(dest, n)
        with open(path, "wb") as f:
            ftp.retrbinary(f"RETR {n}", f.write)
        t = files.get(n)
        if t is None:
            try:
                ts = ftp.voidcmd(f"MDTM {n}")[4:].strip()
                t = _utc(datetime.strptime(ts[:14], "%Y%m%d%H%M%S"))
            except (ftplib.all_errors, ValueError):
                t = None
        if t is not None:
            os.utime(path, (t, t))
            dated += 1
    return latest, wanted, dated, source


def main(dest):
    missing = [k for k in ("FTP_HOST", "FTP_USER", "FTP_PASS") if not os.environ.get(k)]
    if missing:
        sys.exit(f"Faltan los secretos {', '.join(missing)}: cargalos en Settings > Secrets and variables > Actions.")
    host, user, pw = os.environ["FTP_HOST"], os.environ["FTP_USER"], os.environ["FTP_PASS"]
    port = int(os.environ.get("FTP_PORT") or 21)
    remote = os.environ.get("FTP_WORLD_DIR") or "save/worlds_local/gportal_unzip_ppqaovp_"
    ftp = ftplib.FTP_TLS() if os.environ.get("FTP_TLS") == "1" else ftplib.FTP()
    ftp.connect(host, port, timeout=60)
    ftp.login(user, pw)
    if isinstance(ftp, ftplib.FTP_TLS):
        ftp.prot_p()
    ftp.cwd(remote)
    # Si el servidor guarda mientras bajamos, un archivo listado puede desaparecer
    # (se reemplaza por la version nueva del chunk) y el RETR da 550. En ese caso
    # se empieza de nuevo con un listado fresco.
    for attempt in range(1, ATTEMPTS + 1):
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest)
        try:
            latest, wanted, dated, source = download(ftp, dest, remote)
            break
        except ftplib.error_perm as e:
            if not str(e).startswith("550") or attempt == ATTEMPTS:
                raise
            print(f"::warning::Un archivo cambió durante la descarga ({e}); el servidor estaba guardando. "
                  f"Reintento {attempt + 1}/{ATTEMPTS} en {WAIT * attempt} s.")
            time.sleep(WAIT * attempt)
    ftp.quit()
    print(f"Bajados {len(wanted)} archivos del guardado {latest} desde {remote}; "
          f"fechas del servidor: {dated}/{len(wanted)} (listado con {source})")
    if not dated:
        print("::warning::El FTP no informó fechas: la hora del guardado va a ser la de la descarga.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
