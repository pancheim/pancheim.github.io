"""Versiones del inventario para leer sin navegador: JSON (datos exactos) y Markdown
(resumen para una persona o un agente). Salen de los mismos datos que la pagina."""
import collections
from datetime import datetime

from historial import totals as item_totals

WHERE = ("base", "afuera", "tumbas")


def _where(c):
    return "tumbas" if c["kind"] == "Tumba" else ("base" if c["base"] else "afuera")


def _when(iso):
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")


def to_json(data, base, radius):
    """Los datos de la pagina sin lo que solo sirve para dibujar (plano, iconos, posicion en el SVG)."""
    return {
        "guardado": data["saved"], "publicado": data["built"],
        "base": {"x": base[0], "z": base[1], "radio_m": radius},
        "contenedores": [{"tipo": c["kind"], "x": c["x"], "z": c["z"], "donde": _where(c),
                          **({"dueño": c["owner"]} if "owner" in c else {}),
                          "items": [{"item": p, "nombre": data["names"][p]["es"], "cantidad": s, "calidad": q}
                                    for p, s, q in c["items"]]}
                         for c in data["containers"]],
        "estaciones": [{"tipo": s["kind"], "x": s["x"], "z": s["z"], "estado": s["detail"]}
                       for s in data["stations"]],
        "items": {p: {"nombre": n["es"], "categoria": n.get("cat", "Otros")} for p, n in data["names"].items()},
        "totales": item_totals(data["containers"]),
        "mundo": data["world"],
        "historial": data.get("history", []),
    }


def to_markdown(data, base, radius):
    names = data["names"]
    nm = lambda p: names[p]["es"]
    totals = collections.defaultdict(collections.Counter)   # prefab -> {base, afuera, tumbas}
    for c in data["containers"]:
        for p, s, _ in c["items"]:
            totals[p][_where(c)] += s
    by_cat = collections.defaultdict(list)
    for p in totals:
        by_cat[names[p].get("cat", "Otros")].append(p)

    out = [
        "# Arcón de Pancheim: inventario",
        "",
        f"- Guardado del servidor: **{_when(data['saved'])}** (hora de Argentina)",
        f"- Publicado: {_when(data['built'])}",
        f"- Base: a menos de {radius:g} m de ({base[0]:g}, {base[1]:g}). Coordenadas del mapa (x, z).",
        "- No incluye lo que cada jugador lleva encima ni los trofeos colgados.",
        "- Datos exactos en [inventario.json](inventario.json); versión visual en [la página](./).",
        "",
    ]
    out += _world_md(data, nm)
    out += ["", "## Totales por item"]
    for cat in sorted(by_cat):
        out += ["", f"### {cat}", "", "| Item | Base | Afuera | Tumbas | Total |", "|---|--:|--:|--:|--:|"]
        for p in sorted(by_cat[cat], key=nm):
            t = totals[p]
            cells = [str(t[w]) if t[w] else "" for w in WHERE]
            out.append(f"| {nm(p)} `{p}` | " + " | ".join(cells) + f" | {sum(t.values())} |")

    out += ["", "## Estaciones", ""]
    out += [f"- {s['kind']} ({s['x']}, {s['z']}): {s['detail']}" for s in data["stations"]] or ["Ninguna."]

    out += ["", "## Contenedores uno por uno"]
    for w in WHERE:
        group = [c for c in data["containers"] if _where(c) == w]
        if not group:
            continue
        out += ["", f"### {w.capitalize()}", ""]
        for c in sorted(group, key=lambda c: (c["kind"], c["x"], c["z"])):
            stacks = collections.Counter()   # las pilas repetidas del mismo item van juntas
            for p, s, q in c["items"]:
                stacks[p, q] += s
            items = ", ".join(f"{nm(p)} ×{s}" + (f" (nivel {q})" if q > 1 else "") for (p, q), s in stacks.items())
            who = f" de {c['owner']}" if c.get("owner") else ""
            out.append(f"- **{c['kind']}{who}** ({c['x']}, {c['z']}): {items}")
    return "\n".join(out) + "\n"


def _world_md(data, nm):
    w = data["world"]
    out = ["", "## Mundo", "", f"- Día {w['day']}"]
    out += ["", "## Jefes", "", "| Jefe | Estado | Para invocarlo | Hay | Intentos |", "|---|---|---|--:|--:|"]
    for b in w["bosses"]:
        out.append(f"| {b['name']} | {'derrotado' if b['done'] else 'próximo'} | {b['need']} × {b['item_es']} "
                   f"| {b['have']} | {b['tries']} |")

    hv, ns = w["hives"], w["nests"]
    out += ["", "## Colmenas, nidos y cultivos", "",
            f"- Colmenas: {hv['n']}, con {hv['ready']} de miel para sacar ({hv['full']} llenas)",
            f"- Nidos de pájaro: {ns['n']}, con {ns['ready']} plumas para sacar ({ns['full']} llenos)"]
    if w["crops"]:
        out.append("- Para cosechar en la base: " + ", ".join(f"{c['name']} ×{c['n']}" for c in w["crops"]))
    if w["growing"]:
        out.append("- Creciendo en la base: " + ", ".join(f"{c['name']} ×{c['n']}" for c in w["growing"]))

    out += ["", "## Portales", ""]
    for p in w["portals"]:
        state = {1: "**sin pareja**", 2: "conectado"}.get(p["pair"], f"**{p['pair']} con el mismo nombre**")
        tag = f"“{p['tag']}”" if p["tag"] else "(sin nombre)"
        out.append(f"- {tag} ({p['x']}, {p['z']}): {state}" + (f" · puesto por {p['by']}" if p["by"] else ""))

    hist = data.get("history", [])
    out += ["", "## Últimos cambios en los cofres", ""]
    for h in hist[:10]:
        parts = [f"+{n} {nm(p)}" for p, n in h["entro"].items()] + [f"−{n} {nm(p)}" for p, n in h["salio"].items()]
        out.append(f"- {_when(h['desde'])} → {_when(h['hasta'])}: " + ", ".join(parts))
    if not hist:
        out.append("Todavía no hay cambios registrados.")

    return out
