"""Plano de la base visto desde arriba, armado con las piezas construidas.

Cada pieza se dibuja con su posicion y su giro horizontal, con el tamano del juego (metros).
Los techos no se dibujan porque desde arriba tapan todo lo de adentro. Para que se lea como
Valheim: tablones en los pisos de madera, baldosas en los de piedra, troncos en las empalizadas,
la huerta, piedras y arboles del lugar, y las estaciones (forja, fuego, banco...) como marcas.
Norte arriba: x crece hacia la derecha y z hacia arriba, asi que en SVG y = -z.
"""
import math

# prefab: (capa, largo, ancho). Las paredes se dibujan con un ancho fijo.
WALL_W = 0.35
SHAPES = {
    "wood_floor": ("floor_wood", 2, 2), "wood_floor_1x1": ("floor_wood", 1, 1),
    "wood_stair": ("floor_wood", 2, 2),
    "stone_floor_2x2": ("floor_stone", 2, 2), "stone_floor": ("floor_stone", 4, 4), "stone_stair": ("floor_stone", 2, 2),
    "blackmarble_floor": ("floor_marble", 2, 2), "blackmarble_floor_large": ("floor_marble", 4, 4),
    "blackmarble_stair": ("floor_marble", 2, 2),
    "rug_fur": ("rug", 2.4, 1.6),
    "woodwall": ("wall_wood", 2, WALL_W), "wood_wall_half": ("wall_wood", 2, WALL_W),
    "wood_wall_quarter": ("wall_wood", 2, WALL_W), "wood_wall_roof_45": ("wall_wood", 2, WALL_W),
    "wood_wall_roof": ("wall_wood", 2, WALL_W), "wood_gate": ("wall_wood", 2, WALL_W),
    "wood_door": ("wall_wood", 1.2, WALL_W), "wood_fence": ("wall_wood", 2, WALL_W),
    "wood_fence_gate": ("wall_wood", 2, WALL_W), "darkwood_wall": ("wall_wood", 2, WALL_W),
    "wood_beam": ("beam", 2, 0.22), "wood_beam_26": ("beam", 2, 0.22), "wood_beam_45": ("beam", 2, 0.22),
    "woodiron_beam": ("beam", 2, 0.25),
    "stone_wall_1x1": ("wall_stone", 1, 0.5), "stone_wall_2x1": ("wall_stone", 2, 0.5),
    "stone_wall_4x2": ("wall_stone", 4, 0.5), "stone_fence": ("wall_stone", 2, 0.5),
    "stone_pillar": ("wall_stone", 0.7, 0.7), "stone_arch": ("wall_stone", 2, 0.5),
    "blackmarble_2x1x1": ("wall_marble", 2, 1), "blackmarble_1x1": ("wall_marble", 1, 1),
    "blackmarble_base_1": ("wall_marble", 2, 2), "blackmarble_out_1": ("wall_marble", 2, 1),
    "iron_wall_1x1": ("wall_iron", 1, 0.25), "iron_wall_2x2": ("wall_iron", 2, 0.25), "iron_grate": ("wall_iron", 1, 0.25),
}
STAKES = {"stake_wall": 2, "piece_sharpstakes": 2}
# Marcas sueltas: estaciones y cosas del lugar. tipo -> prefabs.
MARKS = {
    "fire": ("hearth", "bonfire", "fire_pit"),
    "torch": ("piece_groundtorch_wood", "piece_groundtorch", "piece_groundtorch_green", "piece_groundtorch_blue", "Torch"),
    "forge": ("forge", "blackforge"),
    "table": ("piece_workbench", "piece_artisanstation", "piece_magetable", "piece_preptable", "piece_stonecutter",
              "piece_cartographytable", "piece_table", "piece_table_oak"),
    "furnace": ("smelter", "blastfurnace", "charcoal_kiln", "piece_oven", "eitrrefinery"),
    "cauldron": ("piece_cauldron", "piece_MeadCauldron", "piece_cookingstation", "piece_cookingstation_iron"),
    "portal": ("portal_wood", "portal_stone", "portal"),
    "bed": ("bed", "piece_bed02"),
    "hive": ("piece_beehive",),
    "barrel": ("fermenter",),
    "windmill": ("windmill",),
    "wheel": ("piece_spinningwheel",),
    "rock": ("Rock_3", "Rock_4", "Rock_7", "placeable_bigrock_02", "rock4_coast_frac", "Rock_3_frac"),
    "tree": ("Beech1", "Beech_small1", "Beech_small2", "Birch1", "Birch2", "Oak1", "FirTree", "FirTree_small", "Pinetree_01"),
    "bush": ("Bush01", "Bush02_en", "RaspberryBush", "BlueberryBush", "Birch_Sapling", "Beech_Sapling", "VineGreen_sapling"),
    "crop": ("Pickable_Carrot", "Pickable_Onion", "Pickable_Turnip", "Pickable_SeedCarrot", "Pickable_SeedOnion",
             "Pickable_SeedTurnip", "Pickable_Barley", "Pickable_Flax", "sapling_carrot", "sapling_onion",
             "sapling_turnip", "sapling_barley", "sapling_flax", "sapling_seedcarrot", "sapling_seedonion", "sapling_seedturnip"),
}
MARK_OF = {p: k for k, ps in MARKS.items() for p in ps}
LAYERS = ("soil", "floor_stone", "floor_marble", "floor_wood", "grout", "plank", "rug", "wall_stone", "wall_marble",
          "wall_iron", "wall_wood", "beam", "stake")
# Del lugar (piedras, arboles, huerta) solo lo que esta cerca de lo construido.
NEAR = 30


def _local(x, z, yaw):
    """Pasa coordenadas de la pieza (a sobre su largo, b sobre su ancho) al mundo."""
    t = math.radians(yaw or 0)
    ux, uz, vx, vz = math.cos(t), -math.sin(t), math.sin(t), math.cos(t)
    return lambda a, b: (x + a * ux + b * vx, z + a * uz + b * vz)


def _rect(x, z, yaw, length, width):
    at, hl, hw = _local(x, z, yaw), length / 2, width / 2
    return [at(a * hl, b * hw) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _lines(x, z, yaw, length, width, along, across):
    """Rayas de la pieza: `along` rayas paralelas al largo y `across` al ancho, repartidas parejo."""
    at, hl, hw, out = _local(x, z, yaw), length / 2, width / 2, []
    for i in range(1, along):
        b = -hw + width * i / along
        out.append([at(-hl, b), at(hl, b)])
    for i in range(1, across):
        a = -hl + length * i / across
        out.append([at(a, -hw), at(a, hw)])
    return out


def _path(polys, close=True):
    return "".join("M" + "L".join(f"{px:.2f} {-pz:.2f}" for px, pz in poly) + ("Z" if close else "") for poly in polys)


class Plan:
    def __init__(self, cx, cz, radius):
        self.cx, self.cz, self.r2 = cx, cz, radius ** 2
        self.layers = {k: [] for k in LAYERS}
        self.marks = []
        self.pts = []

    def add(self, prefab, pos, yaw):
        if pos is None or yaw is None:
            return
        x, y, z = pos
        if (x - self.cx) ** 2 + (z - self.cz) ** 2 > self.r2:
            return
        if prefab in SHAPES:
            layer, length, width = SHAPES[prefab]
            poly = _rect(x, z, yaw, length, width)
            self.layers[layer].append((y, poly))
            self.pts.extend(poly)
            if layer == "floor_wood":     # tablones de medio metro
                self.layers["plank"] += [(y, l) for l in _lines(x, z, yaw, length, width, round(width / .5), 0)]
            elif layer in ("floor_stone", "floor_marble"):   # baldosas de un metro
                n = round(length)
                self.layers["grout"] += [(y, l) for l in _lines(x, z, yaw, length, width, n, n)]
        elif prefab in STAKES:            # troncos en fila
            at, n = _local(x, z, yaw), 5
            for i in range(n):
                cx, cz = at(-STAKES[prefab] / 2 + (i + .5) * STAKES[prefab] / n, 0)
                self.layers["stake"].append((y, [(cx + .2 * math.cos(k * math.pi / 3), cz + .2 * math.sin(k * math.pi / 3)) for k in range(6)]))
        elif prefab in MARK_OF:
            self.marks.append([MARK_OF[prefab], round(x, 1), round(-z, 1)])
            if MARK_OF[prefab] == "crop":     # tierra arada debajo
                self.layers["soil"].append((y, _rect(x, z, 0, 1, 1)))

    def to_json(self):
        if not self.pts:
            return None
        xs = [p[0] for p in self.pts]; zs = [p[1] for p in self.pts]
        box = (min(xs) - NEAR, max(xs) + NEAR, min(zs) - NEAR, max(zs) + NEAR)
        near = lambda x, nz: box[0] <= x <= box[1] and box[2] <= -nz <= box[3]
        layers = {}
        for name, polys in self.layers.items():
            polys.sort(key=lambda t: t[0])   # lo mas alto se dibuja ultimo
            layers[name] = _path([p for _, p in polys], close=name not in ("plank", "grout"))
        return {"box": [round(min(xs) - 4, 1), round(-max(zs) - 4, 1),
                        round(max(xs) - min(xs) + 8, 1), round(max(zs) - min(zs) + 8, 1)],
                "layers": layers, "marks": [m for m in self.marks if near(m[1], m[2])]}
