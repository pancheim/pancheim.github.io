"""Arma la pagina del inventario a partir de la carpeta de un mundo de Valheim.

Uso: python arcon/build.py <carpeta_del_mundo> <salida.html>
"""
import collections
import glob
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

import historial
import registro
from mundo import World
from plan import Plan
from texto import to_json, to_markdown
from zdo import parse_items, stable_hash, world_objects

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HASHES = {int(k): v for k, v in json.load(open(os.path.join(ROOT, "data", "hashes.json"))).items()}
NAMES = json.load(open(os.path.join(ROOT, "data", "names.json"), encoding="utf-8"))
# Nombre en ingles de cada item (del juego, lo genera valheim-contexto: tools/recetas.py --exportar).
_EN = os.path.join(ROOT, "data", "names_en.json")
NAMES_EN = json.load(open(_EN, encoding="utf-8")) if os.path.exists(_EN) else {}
# Recetas de items, leidas del juego en la PC (valheim-contexto: tools/recetas.py --exportar).
RECETAS = os.path.join(ROOT, "data", "recetas.json")

KIND = {"piece_chest_wood": "Cofre", "piece_chest": "Cofre reforzado", "piece_chest_private": "Cofre personal",
        "piece_chest_blackmetal": "Cofre de metal negro", "Cart": "Carro", "Karve": "Karve",
        "VikingShip": "Drakkar", "VikingShip_Ashlands": "Drakkar de las Cenizas", "Raft": "Balsa",
        "Player_tombstone": "Tumba"}
STATIONS = {"fermenter": "Fermentador", "smelter": "Fundición", "charcoal_kiln": "Horno de carbón",
            "blastfurnace": "Alto horno", "piece_spinningwheel": "Rueca", "windmill": "Molino",
            "eitrrefinery": "Refinería de eitr"}
ITEMS, CONTENT, QUEUED, FUEL, OWNER = (stable_hash(k) for k in ("items", "Content", "queued", "fuel", "ownerName"))
STATION_HASH = {stable_hash(k): v for k, v in STATIONS.items()}
# La base principal: lo que esta a menos de BASE_RADIUS metros cuenta como "base".
BASE = (float(os.environ.get("BASE_X", 1290)), float(os.environ.get("BASE_Z", -195)))
BASE_RADIUS = float(os.environ.get("BASE_RADIUS", 150))
# El plano dibuja lo construido a menos de PLAN_RADIUS metros del centro de la base.
PLAN_RADIUS = float(os.environ.get("PLAN_RADIUS", 110))
ART = timezone(timedelta(hours=-3))


def name_es(prefab):
    return NAMES.get(prefab, {}).get("es", prefab)


def build(world_dir):
    containers, stations, used = [], [], set()
    plan = Plan(BASE[0], BASE[1], PLAN_RADIUS)
    world = World(world_dir, BASE, BASE_RADIUS, NAMES)
    for z in world_objects(world_dir):
        pf = HASHES.get(z["prefab"])
        plan.add(pf, z["pos"], z["yaw"])
        world.add(pf, z)
        x, _, zz = z["pos"] or (0, 0, 0)
        if pf in KIND and ITEMS in z.get("bytes", {}):
            items = [[HASHES.get(h, hex(h)), s, q] for h, s, q in parse_items(z["bytes"][ITEMS])]
            if not items:
                continue
            used.update(p for p, _, _ in items)
            c = {"kind": KIND[pf], "x": round(x), "z": round(zz), "p": [round(x, 1), round(-zz, 1)],
                 "base": (x - BASE[0]) ** 2 + (zz - BASE[1]) ** 2 < BASE_RADIUS ** 2, "items": items}
            if pf == "Player_tombstone":
                c["owner"] = z.get("strs", {}).get(OWNER, "")
            containers.append(c)
        elif z["prefab"] in STATION_HASH:
            kind = STATION_HASH[z["prefab"]]
            ints, strs = z.get("ints", {}), z.get("strs", {})
            if kind == "Fermentador":
                c = ints.get(CONTENT)
                detail = f"Fermentando {name_es(HASHES[c])}" if c in HASHES else "Vacío"
            else:
                parts = []
                queued = ints.get(QUEUED, 0)
                if queued:
                    ores = collections.Counter(v for v in strs.values() if v)
                    what = ", ".join(f"{name_es(k)} ×{v}" for k, v in ores.items())
                    parts.append(f"{queued} en cola" + (f" ({what})" if what else ""))
                fuel = z.get("floats", {}).get(FUEL)
                if fuel:
                    parts.append(f"carbón cargado: {fuel:.0f}")
                detail = "; ".join(parts) or "Vacío"
            stations.append({"kind": kind, "x": round(x), "z": round(zz), "detail": detail})

    ok = sorted(glob.glob(os.path.join(world_dir, "_main.*.ok")), key=os.path.getmtime)
    saved = datetime.fromtimestamp(os.path.getmtime(ok[-1]) if ok else 0, ART)
    stored = historial.totals(containers)
    world = world.summary(stored)
    used.update(b["item"] for b in world["bosses"])
    return {"saved": saved.isoformat(timespec="minutes"),
            "built": datetime.now(ART).isoformat(timespec="minutes"),
            "containers": containers, "stations": stations, "plan": plan.to_json(), "world": world,
            "names": {p: NAMES.get(p, {"es": p, "cat": "Otros"}) for p in sorted(used)}}


# Lo que vende Haldor: lo conocen desde que encontraron al mercader (portal MERCADER).
HALDOR = {"YmirRemains"}


def recetas(seen):
    """Lo que me falta para fabricar algo, sin spoilers: solo las recetas de cosas que el clan ya
    tuvo, o cuyos ingredientes pasaron alguna vez por los cofres (registro completo o ahora).
    Lo que nunca tuvieron no aparece."""
    if not os.path.exists(RECETAS):
        return None
    d = json.load(open(RECETAS, encoding="utf-8"))
    seen = seen | HALDOR
    ok = [r for r in d["recetas"] if r["res"] and (r["out"] in seen or all(p in seen for p, _, _ in r["res"]))]
    for r in ok:   # las de "uno de estos" (pescado crudo) no nombran lo que nunca tuvieron
        if r["one"]:
            r["res"] = [x for x in r["res"] if x[0] in seen] or r["res"]
    return {"estaciones": {s: d["estaciones"][s] for s in {r["st"] for r in ok if r["st"]}},
            "nombres": d["nombres"], "recetas": ok}


ICON_URL = "https://valheim-modding.github.io/Jotunn/Documentation/images/items/{}.png"
ICON_CACHE = os.environ.get("ICON_CACHE", os.path.join(ROOT, ".icons"))


def copy_icons(prefabs, dest):
    """Copia a dest el icono de cada item. Los que faltan en la cache se bajan de
    la documentacion de Jotunn; si uno no existe, la pagina muestra el item sin icono."""
    os.makedirs(ICON_CACHE, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    have = []
    for p in prefabs:
        cached = os.path.join(ICON_CACHE, p + ".png")
        if not os.path.exists(cached):
            try:
                with urllib.request.urlopen(ICON_URL.format(p), timeout=20) as r:
                    body = r.read()
                if body[:8] == b"\x89PNG\r\n\x1a\n":
                    open(cached, "wb").write(body)
            except OSError:
                continue
        if os.path.exists(cached):
            shutil.copyfile(cached, os.path.join(dest, p + ".png"))
            have.append(p)
    return have


def main(world_dir, out_path):
    if not glob.glob(os.path.join(world_dir, "*.chunk")):
        sys.exit(f"No hay archivos .chunk en {world_dir}: no publico una pagina vacia.")
    data = build(world_dir)
    # Historial: se compara con lo publicado antes (el workflow lo baja a PREV_DIR).
    data["history"] = historial.update(os.environ.get("PREV_DIR"), data["saved"], historial.totals(data["containers"]))
    # Registro completo (rama `registro`, el workflow la saca a REGISTRO y la sube despues).
    rows = registro.update(os.environ.get("REGISTRO"), data["saved"], data["world"].get("day"),
                           registro.totals(data["containers"]))
    data["registro"] = registro.series(rows)
    data["recetas"] = recetas(set(data["registro"]["items"]) | set(historial.totals(data["containers"])))
    for p in (*(p for h in data["history"] for p in (*h["entro"], *h["salio"])), *data["registro"]["items"]):
        data["names"].setdefault(p, NAMES.get(p, {"es": p, "cat": "Otros"}))
    if data["recetas"]:
        extra = data["recetas"].pop("nombres")
        for r in data["recetas"]["recetas"]:
            for p in (r["out"], *(x[0] for x in r["res"])):
                data["names"].setdefault(p, NAMES.get(p, {"es": extra.get(p, p), "cat": "Otros"}))
    data["names"] = {p: {**n, "en": NAMES_EN[p]} if NAMES_EN.get(p, n["es"]) != n["es"] else n
                     for p, n in data["names"].items()}
    out_dir = os.path.dirname(os.path.abspath(out_path))
    data["icons"] = copy_icons(data["names"], os.path.join(out_dir, "icons"))
    template = open(os.path.join(ROOT, "template.html"), encoding="utf-8").read()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    os.makedirs(out_dir, exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(template.replace("__DATA__", payload))
    # Lo mismo sin navegador: JSON con los datos exactos y Markdown para leer de corrido.
    with open(os.path.join(out_dir, "inventario.json"), "w", encoding="utf-8") as f:
        json.dump(to_json(data, BASE, BASE_RADIUS), f, ensure_ascii=False, indent=1)
    open(os.path.join(out_dir, "inventario.md"), "w", encoding="utf-8").write(to_markdown(data, BASE, BASE_RADIUS))
    with open(os.path.join(out_dir, "historial.json"), "w", encoding="utf-8") as f:
        json.dump(data["history"], f, ensure_ascii=False, indent=1)
    # Huella del contenido (sin horas): el workflow no republica si es igual a la publicada.
    world = {k: v for k, v in data["world"].items() if k != "day"}   # el dia avanza solo: no cuenta como cambio
    content = json.dumps({**{k: data[k] for k in ("containers", "stations", "plan", "names")}, "world": world},
                         sort_keys=True)
    open(os.path.join(out_dir, "estado.txt"), "w").write(hashlib.sha256(content.encode()).hexdigest() + "\n")
    print(f"{len(data['containers'])} contenedores, {len(data['stations'])} estaciones, "
          f"{len(data['names'])} items distintos; guardado {data['saved']} -> {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
