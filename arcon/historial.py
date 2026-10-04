"""Que entro y que salio de los cofres entre una publicacion y la siguiente.

No hay base de datos: la pagina publicada es la memoria. El workflow baja el
inventario.json y el historial.json publicados a una carpeta (PREV_DIR); aca se
comparan los totales con los nuevos y se agrega una entrada si cambio algo.
"""
import json
import os

KEEP = 50


def totals(containers):
    out = {}
    for c in containers:
        for p, s, _ in c["items"]:
            out[p] = out.get(p, 0) + s
    return out


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def update(prev_dir, saved, now_totals):
    """Devuelve el historial nuevo (lo mas reciente primero)."""
    history = _load(os.path.join(prev_dir, "historial.json"), []) if prev_dir else []
    prev = _load(os.path.join(prev_dir, "inventario.json"), None) if prev_dir else None
    if not prev or "totales" not in prev or prev.get("guardado") == saved:
        return history[:KEEP]
    before = prev["totales"]
    diff = {p: now_totals.get(p, 0) - before.get(p, 0) for p in set(before) | set(now_totals)}
    diff = {p: d for p, d in diff.items() if d}
    if diff:
        history.insert(0, {"desde": prev["guardado"], "hasta": saved,
                           "entro": {p: d for p, d in sorted(diff.items(), key=lambda t: -t[1]) if d > 0},
                           "salio": {p: -d for p, d in sorted(diff.items(), key=lambda t: t[1]) if d < 0}})
    return history[:KEEP]
