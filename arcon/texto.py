"""Versiones del inventario para leer sin navegador: JSON (datos exactos) y Markdown
(resumen para una persona o un agente). Salen de los mismos datos que la pagina."""
import collections
from datetime import datetime

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
                          "items": [{"item": p, "nombre": data["names"][p]["es"], "cantidad": s, "calidad": q}
                                    for p, s, q in c["items"]]}
                         for c in data["containers"]],
        "estaciones": [{"tipo": s["kind"], "x": s["x"], "z": s["z"], "estado": s["detail"]}
                       for s in data["stations"]],
        "items": {p: {"nombre": n["es"], "categoria": n.get("cat", "Otros")} for p, n in data["names"].items()},
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
        "## Totales por item",
    ]
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
            out.append(f"- **{c['kind']}** ({c['x']}, {c['z']}): {items}")
    return "\n".join(out) + "\n"
