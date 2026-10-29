"""Relieve de la base para el fondo del plano: altura del terreno con lo que los jugadores
subieron y cavaron con la azada (murallas, fosos, explanadas), sombreada como el juego y con agua.

La altura generada sale de la seed y no cambia nunca: se calculo una vez en la PC (valheim-contexto,
tools/biomas.py con rios y lagos, unos 7 min) y vive en data/base_caja.bin.gz, en centimetros, con
1 m de grilla. Lo que tocaron los jugadores esta en el mundo: cada zona de 64 m modificada tiene un
objeto "_TerrainCompiler" con TCData (gzip): version, operaciones, ultimo punto, radio y despues
65x65 vertices con (modificado u8, levelDelta f32, smoothDelta f32), y la pintura. El vertice i esta
en zona + (i % 65 - 32, i // 65 - 32); los bordes los comparten dos zonas, asi que se pisan.
Solo biblioteca estandar: corre en la accion de GitHub sin instalar nada.
"""
import gzip
import hashlib
import math
import os
import struct
import zlib

from zdo import parse_chunk, stable_hash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "data", "base_caja.bin.gz")
BOX = dict(x0=1180, x1=1400, z0=-305, z1=-85)   # la caja que cubre base_caja.bin.gz
SCALE = 2           # pixeles por metro
EXAG = 1.5          # exageracion vertical del sombreado
WATER = 30.0        # nivel del mar en Valheim
TC, TCDATA = stable_hash("_TerrainCompiler"), stable_hash("TCData")


def _base():
    d = gzip.decompress(open(BASE, "rb").read())
    x0, z0, n = struct.unpack_from("<iii", d)
    v = struct.unpack_from("<%dh" % (n * n), d, 12)
    return x0, z0, n, [[v[r * n + c] / 100 for c in range(n)] for r in range(n)]


def heights(world_dir):
    """Grilla de 1 m (fila = z, columna = x) con la altura final: generada + lo que hicieron."""
    x0, z0, n, h = _base()
    delta = {}
    for f in sorted(os.listdir(world_dir)):
        if not f.endswith(".chunk") or f.startswith("00_00"):
            continue
        for z in parse_chunk(os.path.join(world_dir, f)):
            if z["prefab"] != TC or TCDATA not in z.get("bytes", {}) or "zone" not in z:
                continue
            cx, cz = z["zone"]
            if cx + 32 < x0 or cx - 32 > x0 + n - 1 or cz + 32 < z0 or cz - 32 > z0 + n - 1:
                continue
            d = gzip.decompress(z["bytes"][TCDATA])
            count, p = struct.unpack_from("<i", d, 24)[0], 28
            for i in range(count):
                if d[p]:
                    lv, sm = struct.unpack_from("<ff", d, p + 1)
                    p += 9
                    r, c = cz - 32 + i // 65 - z0, cx - 32 + i % 65 - x0
                    if 0 <= r < n and 0 <= c < n:
                        delta[r, c] = lv + sm
                else:
                    p += 1
    for (r, c), v in delta.items():
        h[r][c] += v
    return x0, z0, h


def _png(w, h, rows):
    raw = b"".join(b"\0" + bytes(r) for r in rows)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _mix(a, b, t):
    return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))


def render(world_dir, out_dir):
    """Escribe relieve.png en out_dir. Devuelve lo que necesita el plano (href y caja en el SVG), o None."""
    if not os.path.exists(BASE):
        return None
    x0, z0, h = heights(world_dir)

    def alt(x, z):
        fx, fz = x - x0, z - z0
        c, r = int(fx), int(fz)
        tx, tz = fx - c, fz - r
        a, b = h[r], h[r + 1]
        return (a[c] * (1 - tx) + a[c + 1] * tx) * (1 - tz) + (b[c] * (1 - tx) + b[c + 1] * tx) * tz

    # Luz del noroeste a 45 grados, como el sombreado de los mapas.
    az, el = math.radians(315), math.radians(45)
    lx, ly, lz = math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)
    grass, grass_hi = (88, 114, 56), (112, 134, 66)
    sand, shallow, deep = (176, 160, 112), (78, 122, 128), (40, 74, 92)
    w, hh, step = (BOX["x1"] - BOX["x0"]) * SCALE, (BOX["z1"] - BOX["z0"]) * SCALE, 1 / SCALE
    rows = []
    for j in range(hh):
        z = BOX["z1"] - (j + .5) * step
        row = bytearray(w * 3)
        for i in range(w):
            x = BOX["x0"] + (i + .5) * step
            y = alt(x, z)
            gx = (alt(x + step / 2, z) - alt(x - step / 2, z)) / step * EXAG
            gz = (alt(x, z + step / 2) - alt(x, z - step / 2)) / step * EXAG
            light = (-gx * lx - gz * ly + lz) / math.sqrt(gx * gx + gz * gz + 1)
            shade = min(1.3, max(.45, .3 + light))   # llano = 1
            if y < WATER:
                col, shade = _mix(shallow, deep, min(1, (WATER - y) / 6)), 1 + (shade - 1) * .25
            elif y < WATER + .6:
                col = sand
            else:
                col = _mix(grass, grass_hi, min(1, max(0, (y - WATER - 4) / 20)))
            row[i * 3:i * 3 + 3] = bytes(min(255, int(c * shade)) for c in col)
        rows.append(row)
    body = _png(w, hh, rows)
    open(os.path.join(out_dir, "relieve.png"), "wb").write(body)
    return {"href": "relieve.png?v=" + hashlib.sha1(body).hexdigest()[:10],
            "box": [BOX["x0"], -BOX["z1"], BOX["x1"] - BOX["x0"], BOX["z1"] - BOX["z0"]]}
