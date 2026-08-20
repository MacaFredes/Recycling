# -*- coding: utf-8 -*-
"""
GRAFICAR MAPAS DE SENSIBILIDAD DE DEMANDA - Script independiente
Lee sensitivity_demand_solutions.xlsx y genera sensitivity_demand_maps.pdf

v2: Rosa de los vientos añadida
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.backends.backend_pdf import PdfPages
import json
import sys
import os

# =============================================================================
# PARÁMETROS
# =============================================================================
INPUT_EXCEL  = 'sensitivity_demand_solutions.xlsx'
OUTPUT_PDF   = 'sensitivity_demand_maps.pdf'
GEOJSON_FILE = 'manzanas_estacion_central.geojson'

SEMANAS = 52
KG_TON  = 1000

ESCENARIOS = [
    ('low',      'Low demand scenario',      10.36),
    ('baseline', 'Baseline demand scenario', 12.48),
    ('high',     'High demand scenario',     15.60),
]

COLOR_TIPO = {
    1: '#E67E22',
    2: '#9B59B6',
    3: '#2ECC71',
}
LABEL_TIPO = {
    1: 'Small container',
    2: 'Medium container',
    3: 'Large container',
}
CAPACITY = {1: 600, 2: 900, 3: 1200}

COLOR_ASIGNADO    = '#E74C3C'
COLOR_NO_ASIGNADO = '#5B9BD5'

BOX_W, BOX_H = 0.0030, 0.0014
DISTANCIAS   = [0.0025, 0.0035, 0.0048, 0.006]
DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0),
        (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)]

plt.rcParams.update({'font.family': 'serif', 'font.size': 11})

# =============================================================================
# IMPORTAR INSTANCIA
# =============================================================================
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

try:
    import Instancia
    df_candidatos = Instancia.df_candidatos
    df_demandas   = Instancia.df_demandas
    phi           = Instancia.phi
    r_radio       = Instancia.r
    I_global      = Instancia.I
except ImportError:
    print("No se pudo importar Instancia.")
    sys.exit(1)

with open(GEOJSON_FILE, 'r', encoding='utf-8') as fg:
    manzanas_data = json.load(fg)

coord_map = {}
for _, row in df_candidatos.iterrows():
    coord_map[row['id_unico']] = (row['longitud'], row['latitud'])

def get_coords(sitio):
    return coord_map.get(sitio, (None, None))

# =============================================================================
# ANTI-COLISIÓN
# =============================================================================
def solapan(ax_, ay, bx, by):
    return abs(ax_ - bx) < BOX_W * 1.1 and abs(ay - by) < BOX_H * 2.0

def tapa_bin(cx, cy, bx, by):
    return abs(cx - bx) < BOX_W * 1.2 and abs(cy - by) < BOX_H * 2.5

def fuera_mapa(cx, cy):
    return cx < -70.737 or cx > -70.666 or cy < -33.488 or cy > -33.438

def calcular_offsets(sitios_info):
    N        = len(sitios_info)
    bin_lons = np.array([s['lon'] for s in sitios_info])
    bin_lats = np.array([s['lat'] for s in sitios_info])

    RADIO_DENSIDAD = 0.012
    for info in sitios_info:
        info['densidad'] = sum(
            1 for other in sitios_info
            if other is not info
            and abs(other['lon'] - info['lon']) < RADIO_DENSIDAD
            and abs(other['lat'] - info['lat']) < RADIO_DENSIDAD
        )
    sitios_info.sort(key=lambda x: -x['densidad'])

    posiciones = []
    for idx, info in enumerate(sitios_info):
        lon, lat = info['lon'], info['lat']
        mejor = None
        for dist in DISTANCIAS:
            if mejor: break
            for dx_u, dy_u in DIRS:
                dx = dx_u * dist * 1.2
                dy = dy_u * dist
                cx, cy = lon + dx, lat + dy
                if fuera_mapa(cx, cy): continue
                if any(solapan(cx, cy, px, py) for px, py in posiciones): continue
                if any(tapa_bin(cx, cy, bin_lons[k], bin_lats[k])
                       for k in range(N)): continue
                mejor = (dx, dy)
                break
        if mejor is None:
            mejor = (0, DISTANCIAS[0])
        info['offset'] = mejor
        posiciones.append((lon + mejor[0], lat + mejor[1]))
    return sitios_info

# =============================================================================
# FUNCIÓN: ROSA DE LOS VIENTOS
# =============================================================================

def add_patch_no_clip(ax, patch):
    ax.add_patch(patch)
    patch.set_clip_on(False)
    patch.set_clip_path(None)

def dibujar_norte(ax, x=0.15, y=0.20, size=0.045):
    t = ax.transAxes

    def pt(dx, dy):
        return (x + dx * size, y + dy * size)

    add_patch_no_clip(ax, MplPolygon(
        [pt(0, 1.4), pt(0.18, 0), pt(0, -1.4), pt(-0.18, 0)],
        closed=True, facecolor='#444444', edgecolor='black',
        linewidth=0.6, zorder=42, transform=t))

    add_patch_no_clip(ax, MplPolygon(
        [pt(1.4, 0), pt(0, 0.18), pt(-1.4, 0), pt(0, -0.18)],
        closed=True, facecolor='#cccccc', edgecolor='black',
        linewidth=0.6, zorder=42, transform=t))

    for p1, p2, p3 in [
        (pt(0, 0.18),  pt(0.85, 0.85),  pt(0.18, 0)),
        (pt(0.18, 0),  pt(0.85, -0.85), pt(0, -0.18)),
        (pt(0, -0.18), pt(-0.85, -0.85),pt(-0.18, 0)),
        (pt(-0.18, 0), pt(-0.85, 0.85), pt(0, 0.18)),
    ]:
        add_patch_no_clip(ax, MplPolygon(
            [p1, p2, p3], closed=True, facecolor='#888888',
            edgecolor='black', linewidth=0.5, zorder=43, transform=t))

    for p1, p2, p3 in [
        (pt(0, 1.4),  pt(0, 0), pt(-0.18, 0)),
        (pt(0, -1.4), pt(0, 0), pt(0.18, 0)),
        (pt(1.4, 0),  pt(0, 0), pt(0, -0.18)),
        (pt(-1.4, 0), pt(0, 0), pt(0, 0.18)),
    ]:
        add_patch_no_clip(ax, MplPolygon(
            [p1, p2, p3], closed=True, facecolor='white',
            edgecolor='none', linewidth=0, zorder=44, transform=t))

    for dx, dy in [(0, 1.4), (0, -1.4), (1.4, 0), (-1.4, 0)]:
        x0, y0 = pt(0, 0)
        x1, y1 = pt(dx, dy)
        ax.plot([x0, x1], [y0, y1], color='black', linewidth=0.4,
                transform=t, zorder=45, clip_on=False)

    add_patch_no_clip(ax, mpatches.Circle(
        (x, y), radius=size * 0.12, transform=t,
        facecolor='white', edgecolor='black',
        linewidth=0.8, zorder=45))

    offset_letra = size * 1.75
    for letra, dx, dy in [('N', 0, 1), ('S', 0, -1), ('E', 1, 0), ('O', -1, 0)]:
        ax.text(x + dx * offset_letra, y + dy * offset_letra, letra,
                transform=t, fontsize=8, fontweight='bold',
                ha='center', va='center', color='black',
                zorder=46, clip_on=False)

# =============================================================================
# FUNCIÓN PRINCIPAL: GENERAR UN MAPA
# =============================================================================
def generar_mapa(key, titulo, factor_anual, df_y, df_x, df_q, df_occ=None):

    sitios_A3    = set(df_y[df_y['modelo'] == 'A3']['j'].values)
    q_total_dict = dict(zip(df_q['i'], df_q['q']))
    total_q      = sum(q_total_dict.values())

    demanda_cubierta = set()
    for i in I_global:
        for j in sitios_A3:
            if phi.get((i, j), np.inf) < r_radio[i]:
                demanda_cubierta.add(i)
                break

    n_cub   = len(demanda_cubierta)
    n_total = len(I_global)

    q_cubierta = sum(q_total_dict.get(i, 0) for i in demanda_cubierta)
    pct_cov    = 100 * q_cubierta / total_q if total_q > 0 else 0

    if df_occ is not None:
        ovf_kg = df_occ['overflow_kg'].sum()
    else:
        ovf_kg = 0.0
    ovf_ta = ovf_kg * SEMANAS / KG_TON

    type_k_dict = {}
    if 'k' in df_y.columns:
        for _, row in df_y[df_y['modelo'] == 'A3'].iterrows():
            type_k_dict[row['j']] = int(row['k'])
    if df_occ is not None and 'type_k' in df_occ.columns:
        for _, row in df_occ.iterrows():
            type_k_dict[row['site_j']] = int(row['type_k'])

    kg_net_dict  = {}
    occ_pct_dict = {}

    if df_occ is not None and 'net_stored_kg' in df_occ.columns:
        for _, row in df_occ.iterrows():
            j        = row['site_j']
            net_kg   = row['net_stored_kg']
            ovf_bin  = row.get('overflow_kg', 0.0)
            type_k   = int(row['type_k'])
            cap      = CAPACITY.get(type_k, 1)
            real_occ = (net_kg + ovf_bin) / cap * 100 if cap > 0 else 0.0
            kg_net_dict[j]  = net_kg
            occ_pct_dict[j] = real_occ
    else:
        if not df_x.empty and 'modelo' in df_x.columns:
            df_x_A3 = df_x[df_x['modelo'] == 'A3']
            for j in sitios_A3:
                filas = df_x_A3[df_x_A3['j'] == j]
                kg    = sum(q_total_dict.get(row['i'], 0) * row['x']
                            for _, row in filas.iterrows())
                kg_net_dict[j] = kg
                type_k = type_k_dict.get(j, 3)
                cap    = CAPACITY.get(type_k, 1)
                occ_pct_dict[j] = kg / cap * 100 if cap > 0 else 0.0

    # ---- FIGURA ----
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_facecolor('white')

    for feat in manzanas_data['features']:
        geom  = feat['geometry']
        polys = ([geom['coordinates'][0]] if geom['type'] == 'Polygon'
                 else [p[0] for p in geom['coordinates']])
        for coords in polys:
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            ax.fill(xs, ys, facecolor='#f5f5f5', edgecolor='#555555',
                    linewidth=0.3, zorder=4)

    q_vals   = np.array([q_total_dict.get(i, 0) for i in I_global])
    p96      = np.percentile(q_vals, 96)
    q_min, q_max = q_vals.min(), q_vals.max()
    sizes = np.where(
        q_vals <= p96,
        8  + (q_vals - q_min) / (p96   - q_min + 1e-9) * 18,
        80 + (q_vals - p96)   / (q_max - p96   + 1e-9) * 270
    )
    colors_dem = [COLOR_ASIGNADO if i in demanda_cubierta else COLOR_NO_ASIGNADO
                  for i in I_global]
    dem_pts = (df_demandas.set_index('id_unico')
                          .reindex(I_global)[['longitud', 'latitud']].values)
    ax.scatter(dem_pts[:, 0], dem_pts[:, 1],
               c=colors_dem, s=sizes, alpha=0.75, zorder=10)

    sitios_info = []
    for j in sitios_A3:
        lon, lat = get_coords(j)
        if lon is None:
            continue
        sitios_info.append({
            'sitio'        : j,
            'lon'          : lon,
            'lat'          : lat,
            'type_k'       : type_k_dict.get(j, 3),
            'net_stored_kg': kg_net_dict.get(j, None),
            'occupancy_pct': occ_pct_dict.get(j, None),
        })

    sitios_info = calcular_offsets(sitios_info)

    for info in sitios_info:
        lon, lat   = info['lon'], info['lat']
        color      = COLOR_TIPO[info['type_k']]
        off        = info['offset']
        tlon, tlat = lon + off[0], lat + off[1]
        kg         = info['net_stored_kg']
        occ        = info['occupancy_pct']

        ax.scatter(lon, lat, c=color, s=75,
                   edgecolors='black', linewidth=0.8, zorder=20)

        if kg is not None:
            label_txt = (f"{int(round(kg))} kg\n({occ:.0f}%)"
                         if occ is not None else f"{int(round(kg))} kg")
            ax.plot([lon, tlon], [lat, tlat],
                    color='#333333', lw=1.0, zorder=22)
            ax.text(tlon, tlat, label_txt,
                    fontsize=7.5, fontweight='bold', color='black',
                    ha='center', va='center', zorder=25,
                    bbox=dict(boxstyle='square,pad=0.28',
                              facecolor='white',
                              edgecolor='#444444',
                              linewidth=1.0,
                              alpha=0.95))

    ax.set_xlabel('Longitude', fontsize=10)
    ax.set_ylabel('Latitude', fontsize=10)
    ax.set_xlim(-70.738, -70.665)
    ax.set_ylim(-33.490, -33.438)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
    ax.set_aspect('equal')

    ax.set_title(
        f"SL-RBLP  |  {titulo}  ({factor_anual:.2f} kg/hh/year)",
        fontsize=12, fontweight='bold', pad=8
    )

    ovf_text = (f"Overflow: {ovf_kg:.2f} kg/week  "
                f"\u2261  {ovf_ta:.2f} metric tonnes/year")
    ax.text(0.5, 0.015, ovf_text,
            transform=ax.transAxes,
            fontsize=10, ha='center', va='bottom',
            color='#C0392B', fontweight='bold',
            bbox=dict(facecolor='white', edgecolor='#C0392B',
                      boxstyle='round,pad=0.3', alpha=0.9),
            zorder=30)

    legend_elements = [
        Line2D([0],[0], marker='o', color='w',
               markerfacecolor=COLOR_ASIGNADO, markersize=7, alpha=0.85,
               label=f'Assigned demand (n={n_cub}, {pct_cov:.2f}%)'),
        Line2D([0],[0], marker='o', color='w',
               markerfacecolor=COLOR_NO_ASIGNADO, markersize=6, alpha=0.7,
               label=f'Unassigned demand (n={n_total - n_cub})'),
    ]
    tipos_presentes = sorted(set(info['type_k'] for info in sitios_info))
    for k in tipos_presentes:
        legend_elements.append(
            Line2D([0],[0], marker='o', color='w',
                   markerfacecolor=COLOR_TIPO[k],
                   markeredgecolor='black',
                   markersize=9,
                   label=LABEL_TIPO[k])
        )
    ax.legend(handles=legend_elements, loc='upper left', fontsize=8.5,
              framealpha=1, edgecolor='black', fancybox=False)

    # Rosa de los vientos
    dibujar_norte(ax, x=0.15, y=0.20, size=0.045)

    lat_c   = -33.47
    km_deg  = 111 * np.cos(np.radians(abs(lat_c)))
    sx, sy  = -70.736, -33.488
    for i in range(5):
        rect = plt.Rectangle(
            (sx + i / km_deg, sy), 1 / km_deg, 0.0015,
            facecolor='black' if i % 2 == 0 else 'white',
            edgecolor='black', linewidth=0.5, zorder=25)
        ax.add_patch(rect)
    for i in range(6):
        ax.text(sx + i / km_deg, sy - 0.0015, str(i), ha='center', fontsize=8)
    ax.text(sx + 5.3 / km_deg, sy + 0.0003, '(km)', fontsize=8)

    plt.tight_layout()
    return fig

# =============================================================================
# GENERAR PDF
# =============================================================================
print(f"\n{'Scenario':<30} | {'n_cub':>6} | {'Total':>6} | {'Coverage (kg%)':>14} | {'Overflow kg/w':>14}")
print("-" * 82)

with PdfPages(OUTPUT_PDF) as pdf:
    for key, titulo, factor_anual in ESCENARIOS:
        print(f"Generando: {titulo}...")

        df_y = pd.read_excel(INPUT_EXCEL, sheet_name=f'{key}_y')
        df_x = pd.read_excel(INPUT_EXCEL, sheet_name=f'{key}_x')
        df_q = pd.read_excel(INPUT_EXCEL, sheet_name=f'{key}_q')

        try:
            df_occ = pd.read_excel(INPUT_EXCEL, sheet_name=f'{key}_occ_A3')
            if df_occ['net_stored_kg'].sum() == 0:
                df_occ = None
                print(f"  '{key}_occ_A3' tiene todo en 0 - se usara fallback.")
        except Exception:
            df_occ = None
            print(f"  Hoja '{key}_occ_A3' no encontrada - se usara fallback.")

        fig = generar_mapa(key, titulo, factor_anual, df_y, df_x, df_q, df_occ)
        pdf.savefig(fig, dpi=200, bbox_inches='tight')
        plt.close(fig)
        print(f"  OK: {titulo}")

print(f"\nPDF guardado: {OUTPUT_PDF}")