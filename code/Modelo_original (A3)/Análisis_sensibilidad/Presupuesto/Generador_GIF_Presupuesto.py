# -*- coding: utf-8 -*-
"""
GIF ANIMADO - Sensibilidad de Presupuesto | SL-RBLP
====================================================
Lee exclusivamente de sensitivity_budget_v2.xlsx.

Salidas:
  · PDF multipágina: mapa_sensibilidad_presupuesto.pdf
  · GIF animado:     mapa_sensibilidad_presupuesto.gif
  · TXT resumen:     coverage_summary.txt
"""

import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.backends.backend_pdf import PdfPages

import Instancia

# =============================================================================
# PARÁMETROS
# =============================================================================
EXCEL_FILE    = 'sensitivity_budget_v2.xlsx'
GEOJSON_FILE  = 'manzanas_estacion_central.geojson'
GIF_FILE      = 'mapa_sensibilidad_presupuesto.gif'
PDF_FILE      = 'mapa_sensibilidad_presupuesto.pdf'
COVERAGE_FILE = 'coverage_summary.txt'

SEMANAS   = 52
KG_TON    = 1000
VIDA_UTIL = 260

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

BOX_W = 0.0030
BOX_H = 0.0014

DIRS = [
    ( 0,  1),
    ( 1,  0),
    ( 0, -1),
    (-1,  0),
    ( 0.7,  0.7),
    (-0.7,  0.7),
    ( 0.7, -0.7),
    (-0.7, -0.7),
]
DISTANCIAS = [0.0025, 0.0035, 0.0048, 0.006]

# =============================================================================
# CARGAR DATOS ESTÁTICOS
# =============================================================================
print("Cargando datos...")

with open(GEOJSON_FILE, 'r', encoding='utf-8') as f:
    manzanas_data = json.load(f)

df_candidatos = Instancia.df_candidatos
df_demandas   = Instancia.df_demandas
phi           = Instancia.phi
r_cob         = Instancia.r
I             = Instancia.I
J             = Instancia.J
q             = Instancia.q

total_q = sum(q[i] for i in I)

# =============================================================================
# LEER EXCEL v2
# =============================================================================
print(f"Leyendo {EXCEL_FILE}...")
df_results  = pd.read_excel(EXCEL_FILE, sheet_name='Results')
df_loc      = pd.read_excel(EXCEL_FILE, sheet_name='Locations')
df_dem_asgn = pd.read_excel(EXCEL_FILE, sheet_name='Demand_Assignment')
df_occ      = pd.read_excel(EXCEL_FILE, sheet_name='Bin_Occupancy')

df_loc_a3  = df_loc[df_loc['model'] == 'A3'].copy()
df_dem_a3  = df_dem_asgn[df_dem_asgn['model'] == 'A3'].copy()
df_occ_a3  = df_occ[df_occ['model'] == 'A3'].copy()

budget_levels = sorted(df_loc_a3['budget'].unique())
print(f"  Niveles de presupuesto: {len(budget_levels)}")

# =============================================================================
# COORDENADAS
# =============================================================================
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
# PRE-CALCULAR DATOS POR FRAME
# =============================================================================
print("Pre-calculando datos por frame...")
print()
print(f"{'Budget (USD)':>14} | {'$/week':>8} | {'Assigned':>9} | {'Total':>6} | {'Coverage (kg%)':>14}")
print("-" * 65)

coverage_lines = []
coverage_lines.append(f"{'Budget (USD)':>14} | {'$/week':>8} | {'Assigned':>9} | {'Total':>6} | {'Coverage (kg%)':>14}")
coverage_lines.append("-" * 65)

frames_data = []

for B in budget_levels:
    B_total = round(B * VIDA_UTIL)

    locs_b = df_loc_a3[df_loc_a3['budget'] == B]
    occ_b  = df_occ_a3[df_occ_a3['budget'] == B]
    dem_b  = df_dem_a3[df_dem_a3['budget'] == B]

    overflow_row = df_results[np.abs(df_results['budget'] - B) < 0.01]
    ovf_kg = overflow_row['overflow_slrblp'].values[0] if len(overflow_row) else 0.0
    ovf_ta = ovf_kg * SEMANAS / KG_TON

    demanda_cubierta = set(dem_b['demand_i'].unique())

    q_cubierta   = sum(q[i] for i in demanda_cubierta)
    coverage_pct = 100 * q_cubierta / total_q

    q_vals = np.array([q[i] for i in I])
    p96    = np.percentile(q_vals, 96)
    q_min, q_max = q_vals.min(), q_vals.max()
    sizes = np.where(
        q_vals <= p96,
        8  + (q_vals - q_min) / (p96   - q_min + 1e-9) * 18,
        80 + (q_vals - p96)   / (q_max - p96   + 1e-9) * 270
    )
    colors_dem = [COLOR_ASIGNADO if i in demanda_cubierta else COLOR_NO_ASIGNADO
                  for i in I]
    dem_pts = df_demandas[['longitud', 'latitud']].values

    occ_dict = {}
    for _, row in occ_b.iterrows():
        j         = row['site_j']
        type_k    = int(row['type_k'])
        net_kg    = row['net_stored_kg']
        ovf_bin   = row.get('overflow_kg', 0.0)
        cap       = CAPACITY.get(type_k, net_kg if net_kg > 0 else 1)
        real_occ  = (net_kg + ovf_bin) / cap * 100 if cap > 0 else 0.0
        occ_dict[j] = {
            'type_k'       : type_k,
            'net_stored_kg': net_kg,
            'overflow_kg'  : ovf_bin,
            'occupancy_pct': real_occ,
        }

    sitios_info = []
    for _, row in locs_b.iterrows():
        j = row['site_j']
        lon, lat = get_coords(j)
        if lon is None:
            continue
        occ = occ_dict.get(j, {})
        sitios_info.append({
            'sitio'        : j,
            'lon'          : lon,
            'lat'          : lat,
            'type_k'       : occ.get('type_k', int(row['type_k'])),
            'net_stored_kg': occ.get('net_stored_kg', None),
            'occupancy_pct': occ.get('occupancy_pct', None),
        })

    sitios_info = calcular_offsets(sitios_info)

    n_asig  = len(demanda_cubierta)
    n_total = len(I)

    line = f"  USD {B_total:>8,} | {B:>8.2f} | {n_asig:>9} | {n_total:>6} | {coverage_pct:>13.2f}%"
    print(line)
    coverage_lines.append(line)

    frames_data.append({
        'B'           : B,
        'B_total'     : B_total,
        'ovf_kg'      : ovf_kg,
        'ovf_ta'      : ovf_ta,
        'sitios_info' : sitios_info,
        'dem_pts'     : dem_pts,
        'colors_dem'  : colors_dem,
        'sizes'       : sizes,
        'n_asig'      : n_asig,
        'n_total'     : n_total,
        'coverage_pct': coverage_pct,
        'q_cubierta'  : q_cubierta,
    })

print()
print(f"  {len(frames_data)} frames listos.")

with open(COVERAGE_FILE, 'w', encoding='utf-8') as f:
    f.write("Coverage Summary — SL-RBLP Budget Sensitivity\n")
    f.write("=" * 65 + "\n")
    for line in coverage_lines:
        f.write(line + "\n")
print(f"✓ Resumen de cobertura guardado: {COVERAGE_FILE}")

# =============================================================================
# FUNCIÓN DE DIBUJO DE UN FRAME
# =============================================================================
def dibujar_frame(ax, fd):
    ax.cla()
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

    ax.scatter(fd['dem_pts'][:, 0], fd['dem_pts'][:, 1],
               c=fd['colors_dem'], s=fd['sizes'], alpha=0.75, zorder=10)

    for info in fd['sitios_info']:
        lon, lat   = info['lon'], info['lat']
        color      = COLOR_TIPO[info['type_k']]
        off        = info['offset']
        tlon, tlat = lon + off[0], lat + off[1]
        kg         = info['net_stored_kg']
        occ        = info['occupancy_pct']

        ax.scatter(lon, lat, c=color, s=75,
                   edgecolors='black', linewidth=0.8, zorder=20)

        if kg is not None:
            label = f"{int(round(kg))} kg\n({occ:.0f}%)"
            ax.plot([lon, tlon], [lat, tlat],
                    color='#333333', lw=1.0, zorder=22)
            ax.text(tlon, tlat, label,
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
    ax.set_aspect('equal')

    ax.set_title(
        f"SL-RBLP  |  Budget: USD {fd['B_total']:,}  (${fd['B']:.2f}/week)",
        fontsize=12, fontweight='bold', pad=8
    )

    ovf_text = (f"Overflow: {fd['ovf_kg']:.2f} kg/week  "
                f"\u2261  {fd['ovf_ta']:.2f} metric tonnes/year")
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
               label=f'Assigned demand (n={fd["n_asig"]}, {fd["coverage_pct"]:.2f}%)'),
        Line2D([0],[0], marker='o', color='w',
               markerfacecolor=COLOR_NO_ASIGNADO, markersize=6, alpha=0.7,
               label=f'Unassigned demand (n={fd["n_total"] - fd["n_asig"]})'),
    ]
    for k in sorted(COLOR_TIPO.keys()):
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

    lat_c  = -33.47
    km_deg = 111 * np.cos(np.radians(abs(lat_c)))
    sx, sy = -70.736, -33.488
    for i in range(5):
        rect = plt.Rectangle(
            (sx + i/km_deg, sy), 1/km_deg, 0.0015,
            facecolor='black' if i % 2 == 0 else 'white',
            edgecolor='black', linewidth=0.5, zorder=25)
        ax.add_patch(rect)
    for i in range(6):
        ax.text(sx + i/km_deg, sy - 0.0015, str(i), ha='center', fontsize=8)
    ax.text(sx + 5.3/km_deg, sy + 0.0003, '(km)', fontsize=8)


# =============================================================================
# GUARDAR PDF
# =============================================================================
print(f"\nGenerando PDF: {PDF_FILE} ...")
with PdfPages(PDF_FILE) as pdf:
    for fd in frames_data:
        fig, ax = plt.subplots(figsize=(12, 10))
        dibujar_frame(ax, fd)
        fig.tight_layout()
        pdf.savefig(fig, dpi=200, bbox_inches='tight')
        plt.close(fig)
        print(f"  ✓ Budget USD {fd['B_total']:,}  ({fd['coverage_pct']:.2f}%)")
print(f"✓ PDF guardado: {PDF_FILE}  ({len(frames_data)} páginas)")

# =============================================================================
# GIF
# =============================================================================
print(f"\nGenerando GIF: {GIF_FILE} ...")
fig_anim, ax_anim = plt.subplots(figsize=(12, 10))

def update(frame_idx):
    dibujar_frame(ax_anim, frames_data[frame_idx])
    fig_anim.tight_layout()
    return []

INTERVAL_MS = 2500
anim = FuncAnimation(fig_anim, update, frames=len(frames_data),
                     interval=INTERVAL_MS, repeat=True, blit=False)
writer = PillowWriter(fps=1000 / INTERVAL_MS)
anim.save(GIF_FILE, writer=writer, dpi=120)
print(f"✓ GIF guardado: {GIF_FILE}")

plt.show()