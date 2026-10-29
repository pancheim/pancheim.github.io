"""Registro completo de lo guardado: los totales de cada guardado en que cambio algo.

Vive en la rama `registro` del repo (registro.jsonl, una linea por guardado), asi no se
pierde como el historial de la pagina, que guarda solo los ultimos 50 cambios. El workflow
saca esa rama a una carpeta, build.py agrega la linea nueva y el workflow la sube.

Cuenta cofres, carros y barcos; las tumbas no, porque son lo que alguien llevaba encima.
"""
import json
import os


def totals(containers):
    out = {}
    for c in containers:
        if c["kind"] == "Tumba":
            continue
        for p, s, _ in c["items"]:
            out[p] = out.get(p, 0) + s
    return out


def load(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def update(path, saved, day, now_totals):
    """Agrega el guardado si los totales cambiaron. Devuelve todas las lineas."""
    rows = load(path)
    if not path:
        return rows
    if rows and (rows[-1]["t"] >= saved or rows[-1]["totales"] == now_totals):
        return rows
    row = {"t": saved, "dia": day, "totales": dict(sorted(now_totals.items()))}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return rows + [row]


def series(rows):
    """Para la pagina, compacto: por item, solo los puntos en que cambia ([indice, cantidad])."""
    out, last = {}, {}
    for i, r in enumerate(rows):
        tot = r["totales"]
        for p in set(last) | set(tot):
            v = tot.get(p, 0)
            if last.get(p, 0) != v:
                out.setdefault(p, []).append([i, v])
            last[p] = v
    return {"t": [r["t"] for r in rows], "dia": [r.get("dia") for r in rows], "items": out,
            "rearmado": [i for i, r in enumerate(rows) if r.get("rearmado")]}
