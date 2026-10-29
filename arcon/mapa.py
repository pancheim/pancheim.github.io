"""Mapa del clan: el terreno solo donde el clan ya estuvo, segun la mesa de cartografia de la base.

La mesa (piece_cartographytable) guarda en el mundo el mapa compartido: ZDO "data" en gzip con
version (3), cantidad de celdas (2048 * 2048) y un byte por celda (1 = registrada). Cada celda
mide 12 m y la grilla esta centrada en el origen: columna = x / 12 + 1024, fila = z / 12 + 1024
(validado: los 70 portales, tumbas y extractores del guardado 1738 caen en celdas registradas).

El terreno de todo el mundo sale de la seed (valheim-contexto, tools/biomas.py) y mostrarlo entero
seria el spoiler mas grande. Por eso vive en data/mapa_terreno.bin cifrado con MAP_KEY (secreto del
repo): sin la clave no se puede ver, y la pagina solo publica las celdas que registraron en la mesa.
Solo biblioteca estandar.
"""
import gzip
import hashlib
import os
import struct
import zlib

from zdo import parse_chunk, stable_hash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERRAIN = os.path.join(ROOT, "data", "mapa_terreno.bin")
SIZE, CELL = 2048, 12
TABLE, DATA = stable_hash("piece_cartographytable"), stable_hash("data")
PAPER = (205, 185, 143)   # pergamino donde no estuvieron


def keystream_xor(data, key):
    """Cifrado simetrico simple: XOR con SHA-256(clave || contador). Alcanza para que el repo publico
    no muestre el mapa; la clave esta en los secretos de GitHub y en la PC del usuario."""
    k = hashlib.sha256(key.encode()).digest()
    stream = b"".join(hashlib.sha256(k + i.to_bytes(8, "little")).digest() for i in range((len(data) + 31) // 32))
    return (int.from_bytes(data, "little") ^ int.from_bytes(stream[:len(data)], "little")).to_bytes(len(data), "little")


def encrypt_terrain(rgb_rows_north_first, key, path=TERRAIN):
    """Una vez, en la PC: guarda el terreno (filas de norte a sur, RGB) cifrado."""
    raw = b"".join(rgb_rows_north_first)
    open(path, "wb").write(keystream_xor(zlib.compress(raw, 9), key))


def explored(world_dir):
    """Celdas registradas en la mesa de cartografia (bytes de 2048 * 2048, fila = z), o None."""
    for f in sorted(os.listdir(world_dir)):
        if not f.endswith(".chunk"):
            continue
        for z in parse_chunk(os.path.join(world_dir, f)):
            if z["prefab"] == TABLE and DATA in z.get("bytes", {}):
                d = gzip.decompress(z["bytes"][DATA])
                ver, n = struct.unpack_from("<ii", d, 0)
                if n == SIZE * SIZE:
                    return d[8:8 + n]
    return None


def _png(w, h, rows):
    raw = b"".join(b"\0" + bytes(r) for r in rows)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def render(world_dir, out_dir):
    """Escribe mapa.png (lo registrado en la mesa, recortado) y devuelve {href, box} para el SVG, o None."""
    key = os.environ.get("MAP_KEY")
    if not key or not os.path.exists(TERRAIN):
        return None
    seen = explored(world_dir)
    if not seen:
        return None
    terrain = zlib.decompress(keystream_xor(open(TERRAIN, "rb").read(), key))
    cells = [i for i in range(SIZE * SIZE) if seen[i]]
    cols, rows = [i % SIZE for i in cells], [i // SIZE for i in cells]
    c0, c1 = max(0, min(cols) - 4), min(SIZE - 1, max(cols) + 4)
    r0, r1 = max(0, min(rows) - 4), min(SIZE - 1, max(rows) + 4)
    paper = bytes(PAPER)
    out = []
    for r in range(r1, r0 - 1, -1):          # de norte a sur
        north = SIZE - 1 - r                 # el terreno esta guardado con la fila 0 al norte
        t = terrain[north * SIZE * 3:(north + 1) * SIZE * 3]
        line = bytearray()
        for c in range(c0, c1 + 1):
            line += t[c * 3:c * 3 + 3] if seen[r * SIZE + c] else paper
        out.append(line)
    body = _png(c1 - c0 + 1, r1 - r0 + 1, out)
    open(os.path.join(out_dir, "mapa.png"), "wb").write(body)
    # Caja en coordenadas del SVG (x, y = -z): cada celda va de (c - 1024 - .5) * 12 a (c - 1024 + .5) * 12.
    x0, x1 = (c0 - SIZE // 2 - .5) * CELL, (c1 - SIZE // 2 + .5) * CELL
    zmax, zmin = (r1 - SIZE // 2 + .5) * CELL, (r0 - SIZE // 2 - .5) * CELL
    return {"href": "mapa.png?v=" + hashlib.sha1(body).hexdigest()[:10], "box": [x0, -zmax, x1 - x0, zmax - zmin]}
