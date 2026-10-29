"""Lector del formato ChunkedSave de Valheim (world version 41).

Cada .chunk es: u16 version, u32 cantidad de objetos (ZDO) y los objetos.
Cada ZDO: u16 flags, posicion (3 floats, o 2 shorts si 0x2000), u32 prefab,
rotacion opcional (0x1000; 2 bytes si el bit alto esta prendido, si no 4),
conexion (0x01) y luego grupos tipados: floats 0x02, vec3 0x04, quat 0x08,
ints 0x10, longs 0x20, strings 0x40, byte arrays 0x80. Las claves son el
hash estable del nombre (ver stable_hash).
"""
import glob
import os
import struct


def stable_hash(s):
    """String.GetStableHashCode de Valheim, como entero sin signo."""
    n1 = n2 = 5381
    i = 0
    while i < len(s):
        n1 = (((n1 << 5) + n1) ^ ord(s[i])) & 0xFFFFFFFF
        if i == len(s) - 1:
            break
        n2 = (((n2 << 5) + n2) ^ ord(s[i + 1])) & 0xFFFFFFFF
        i += 2
    return (n1 + n2 * 1566083941) & 0xFFFFFFFF


class Reader:
    def __init__(self, data, pos=0):
        self.d, self.p = data, pos

    def u8(self):
        v = self.d[self.p]; self.p += 1; return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]; self.p += 2; return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v

    def i64(self):
        v = struct.unpack_from("<q", self.d, self.p)[0]; self.p += 8; return v

    def floats(self, n=1):
        v = struct.unpack_from("<%df" % n, self.d, self.p); self.p += 4 * n; return v

    def raw(self, n):
        v = self.d[self.p:self.p + n]; self.p += n; return v

    def count(self):
        v = self.u8()
        if v & 0x80:
            v = ((v & 0x7F) << 8) | self.u8()
        return v

    def string(self):
        n = shift = 0
        while True:
            b = self.u8(); n |= (b & 0x7F) << shift; shift += 7
            if not b & 0x80:
                break
        return self.raw(n).decode("utf-8", "replace")


def parse_chunk(path):
    data = open(path, "rb").read()
    r = Reader(data)
    r.u16()
    out = []
    for _ in range(r.u32()):
        z = {}
        fl = r.u16()
        if fl & 0x2000:
            # posicion corta: la zona (x, z) en dos i16; la usan los objetos de terreno (_TerrainCompiler)
            z["zone"] = struct.unpack("<hh", r.raw(4)); z["pos"] = None
        else:
            z["pos"] = r.floats(3)
        z["prefab"] = r.u32()
        z["yaw"] = 0.0
        if fl & 0x1000:
            w = struct.unpack_from("<H", data, r.p)[0]
            if w & 0x8000:
                # Solo giro horizontal (lo normal en piezas construidas): medios grados.
                z["yaw"] = (w & 0x7FFF) / 2
                r.p += 2
            else:
                z["yaw"] = None  # rotacion completa en 4 bytes; no la necesitamos
                r.p += 4
        if fl & 0x01: r.u8(); r.u32()
        if fl & 0x02: z["floats"] = {r.u32(): r.floats()[0] for _ in range(r.count())}
        if fl & 0x04: z["vec3"] = {r.u32(): r.floats(3) for _ in range(r.count())}
        if fl & 0x08: z["quat"] = {r.u32(): r.floats(4) for _ in range(r.count())}
        if fl & 0x10: z["ints"] = {r.u32(): r.u32() for _ in range(r.count())}
        if fl & 0x20: z["longs"] = {r.u32(): r.i64() for _ in range(r.count())}
        if fl & 0x40: z["strs"] = {r.u32(): r.string() for _ in range(r.count())}
        if fl & 0x80:
            z["bytes"] = {}
            for _ in range(r.count()):
                k = r.u32(); z["bytes"][k] = r.raw(r.u32())
        out.append(z)
    if r.p != len(data):
        raise ValueError(f"{path}: sobran {len(data) - r.p} bytes; cambio el formato?")
    return out


def world_objects(world_dir):
    """Todos los objetos del mundo. El chunk 00_00 guarda otra cosa y se saltea."""
    for f in sorted(glob.glob(os.path.join(world_dir, "*.chunk"))):
        if os.path.basename(f).startswith("00_00"):
            continue
        yield from parse_chunk(f)


def parse_items(blob):
    """Contenido de un contenedor: lista de (hash del prefab, cantidad, nivel)."""
    r = Reader(blob)
    r.u32()
    out = []
    for _ in range(r.u16()):
        r.u32(); r.u8(); r.u8(); r.u8()        # durabilidad, x, y, ?
        fl = r.u8()
        quality = r.u16() if fl & 0x04 else 1
        stack = r.u16() if fl & 0x08 else 1
        if fl & 0x10: r.u32()                  # variante
        if fl & 0x20: r.i64(); r.string()      # quien lo fabrico
        out.append((r.u32(), stack, quality))
        r.u8()
    return out
