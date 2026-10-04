"""Datos del mundo que no estan en los cofres: seed, dia, jefes derrotados, portales,
colmenas, nidos y cultivos. Sin spoilers: no se publican lugares del mapa y de los jefes
solo van los derrotados y el siguiente.

- _main.N.fwl2: i32 tamano, i32 version, nombre, seed, ...; mas adelante la lista de
  jugadores que entraron (i32 cantidad y por cada uno: id de Steam, nombre, nombre, id).
- _main.N.db2: i32 version, f64 tiempo del mundo en segundos, i32 largo y un gzip. Adentro,
  entre otras cosas: las marcas globales (i32 cantidad + strings, ej. "defeated_dragon"),
  un byte, i32 cantidad de lugares y por cada uno: u32 hash del nombre, 3 floats de
  posicion y un byte que vale 1 si esa zona ya se genero (alguien paso cerca).
"""
import glob
import math
import os
import re
import struct
import zlib

from zdo import Reader, stable_hash

DAY_SECONDS = 1800

# clave global, nombre, item para invocarlo, cantidad (en orden de progresion)
BOSSES = [
    ("defeated_eikthyr", "Eikthyr", "TrophyDeer", 2),
    ("defeated_gdking", "El Anciano", "AncientSeed", 3),
    ("defeated_bonemass", "Bonemass", "WitheredBone", 10),
    ("defeated_dragon", "Moder", "DragonEgg", 3),
    ("defeated_goblinking", "Yagluth", "GoblinTotem", 5),
    ("defeated_queen", "La Reina", "DvergrKey", 1),
    ("defeated_fader", "Fader", "BellFragment", 3),
]
CROPS = {  # lo que se cosecha (ya crecido) y lo que esta creciendo
    "Pickable_Carrot": "Zanahoria", "Pickable_SeedCarrot": "Semillas de zanahoria",
    "Pickable_Turnip": "Nabo", "Pickable_SeedTurnip": "Semillas de nabo",
    "Pickable_Onion": "Cebolla", "Pickable_SeedOnion": "Semillas de cebolla",
    "Pickable_Barley": "Cebada", "Pickable_Flax": "Lino",
    "Pickable_Mushroom_JotunPuffs": "Bufasetas de Jotun", "Pickable_Mushroom_Magecap": "Gorromago",
}
PORTALS = {"portal_wood", "portal", "portal_stone"}
TAG, TAG_AUTHOR, LEVEL = stable_hash("tag"), stable_hash("tagauthor"), stable_hash("level")


def _latest(world_dir, ext):
    files = glob.glob(os.path.join(world_dir, f"_main.*.{ext}"))
    return max(files, key=lambda f: int(os.path.basename(f).split(".")[1])) if files else None


def read_fwl2(path):
    r = Reader(open(path, "rb").read())
    r.u32(); r.u32()
    out = {"world": r.string(), "seed": r.string(), "players": {}}
    data = r.d
    # La lista de jugadores esta mas adelante: i32 cantidad seguido del primer "Steam_..."
    i = data.find(b"Steam_")
    if i > 5:
        r.p = i - 5
        try:
            for _ in range(r.u32()):
                sid, name, _, _ = r.string(), r.string(), r.string(), r.string()
                out["players"][sid] = name
        except (IndexError, struct.error):
            pass
    return out


def _tables(d):
    """La tabla de lugares termina justo al final del bloque descomprimido y tiene las
    marcas globales inmediatamente antes; se exigen las dos cosas para no confundirse."""
    for start in range(0, len(d) - 4):
        n = struct.unpack_from("<i", d, start)[0]
        if n <= 0 or start + 4 + n * 17 != len(d):
            continue
        keys = _global_keys(d, start)
        if keys:
            locs = [(struct.unpack_from("<I", d, p)[0], *struct.unpack_from("<3f", d, p + 4), d[p + 16])
                    for p in range(start + 4, len(d), 17)]
            return keys, locs
    return [], []


def _global_keys(d, end):
    """Las marcas globales: i32 cantidad + strings, justo antes de la tabla de lugares."""
    for start in range(max(0, end - 4000), end):
        n = struct.unpack_from("<i", d, start)[0]
        if not 0 < n < 300:
            continue
        r = Reader(d, start + 4)
        try:
            keys = [r.string() for _ in range(n)]
        except (IndexError, UnicodeDecodeError):
            continue
        if r.p + 1 == end and all(re.fullmatch(r"[a-z_]+( \S+)?", k) for k in keys):
            return keys
    return []


def read_db2(path):
    raw = open(path, "rb").read()
    _, seconds, _ = struct.unpack_from("<idi", raw, 0)
    d = zlib.decompressobj(31).decompress(raw[16:])
    keys, locs = _tables(d)
    if not keys:
        print("::warning::No encontré las marcas globales ni los lugares en el .db2: ¿cambió el formato?")
    return {"day": int(seconds // DAY_SECONDS) + 1, "keys": [k.split(" ")[0] for k in keys], "locations": locs}


class World:
    """Junta lo que build.py le pasa objeto por objeto y arma el resumen."""

    def __init__(self, world_dir, base, radius, names):
        self.base, self.radius, self.names = base, radius, names
        self.portals, self.hives, self.nests = [], [], []
        self.crops = {}
        fwl = _latest(world_dir, "fwl2")
        db = _latest(world_dir, "db2")
        self.meta = read_fwl2(fwl) if fwl else {"world": None, "seed": None, "players": {}}
        try:
            self.db = read_db2(db) if db else {"day": None, "keys": [], "locations": []}
        except (zlib.error, struct.error) as e:
            print(f"::warning::No pude leer {db}: {e}")
            self.db = {"day": None, "keys": [], "locations": []}

    def _dist(self, x, z):
        return math.hypot(x - self.base[0], z - self.base[1])

    def add(self, prefab, z):
        if not prefab or z["pos"] is None:
            return
        x, _, zz = z["pos"]
        if prefab in PORTALS:
            strs = z.get("strs", {})
            author = strs.get(TAG_AUTHOR, "")
            self.portals.append({"tag": strs.get(TAG, ""), "x": round(x), "z": round(zz),
                                 "by": self.meta["players"].get(author, "")})
        elif prefab in ("piece_beehive", "piece_birdnest"):
            lst = self.hives if prefab == "piece_beehive" else self.nests
            lst.append({"x": round(x), "z": round(zz), "n": z.get("ints", {}).get(LEVEL, 0)})
        elif prefab in CROPS and self._dist(x, zz) < self.radius:
            self.crops[prefab] = self.crops.get(prefab, 0) + 1
        elif prefab.startswith("sapling_") and self._dist(x, zz) < self.radius:
            key = "growing:" + prefab
            self.crops[key] = self.crops.get(key, 0) + 1

    def summary(self, stored):
        """stored: {prefab: cantidad} de todo lo guardado, para contar invocaciones."""
        keys = set(self.db["keys"])
        bosses = []
        for key, name, item, need in BOSSES:
            have = stored.get(item, 0)
            bosses.append({"name": name, "done": key in keys, "item": item,
                           "item_es": self.names.get(item, {}).get("es", item), "need": need,
                           "have": have, "tries": have // need})
            if key not in keys:
                break   # el siguiente se muestra; los que vienen despues no (spoiler)

        count = {}
        for p in self.portals:
            count[p["tag"]] = count.get(p["tag"], 0) + 1
        for p in self.portals:
            p["pair"] = count[p["tag"]]
        self.portals.sort(key=lambda p: (p["pair"] == 2, p["tag"].lower()))

        crops = [{"name": CROPS[k], "n": n} for k, n in self.crops.items() if not k.startswith("growing:")]
        growing = [{"name": self.names.get(k[8:], {}).get("es", k[8:].replace("sapling_", "")), "n": n}
                   for k, n in self.crops.items() if k.startswith("growing:")]
        # La seed no se publica: con ella se puede ver el mapa entero (spoiler).
        return {"day": self.db["day"], "bosses": bosses,
                "portals": self.portals,
                "hives": {"n": len(self.hives), "ready": sum(h["n"] for h in self.hives), "full": sum(h["n"] >= 4 for h in self.hives)},
                "nests": {"n": len(self.nests), "ready": sum(h["n"] for h in self.nests), "full": sum(h["n"] >= 4 for h in self.nests)},
                "crops": sorted(crops, key=lambda c: -c["n"]), "growing": sorted(growing, key=lambda c: -c["n"])}
