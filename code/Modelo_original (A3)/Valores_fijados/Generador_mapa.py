# -*- coding: utf-8 -*-
"""
Mapa comparativo de ubicaciones seleccionadas por cada modelo
VERSIÓN v7 — Rosa corregida con set_clip_path(None) en cada patch
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import json
import pandas as pd

import Instancia

# =============================================================================
# COLORES POR MODELO
# =============================================================================
COLOR_A1  = '#E67E22'   # Naranja
COLOR_A2  = '#9B59B6'   # Morado
COLOR_A3  = '#2ECC71'   # Verde

COLOR_NO_ASIGNADO = '#5B9BD5'   # azul pastel

BOX_W, BOX_H = 0.0030, 0.0014
DISTANCIAS   = [0.0025, 0.0035, 0.0048, 0.006]
DIRS = [(0,1),(1,0),(0,-1),(-1,0),(0.7,0.7),(-0.7,0.7),(0.7,-0.7),(-0.7,-0.7)]

SEMANAS = 52
KG_TON  = 1000

plt.rcParams.update({'font.family': 'serif', 'font.size': 11})

# =============================================================================
# CARGAR DATOS
# =============================================================================
print("Cargando datos...")

with open('manzanas_estacion_central.geojson', 'r', encoding='utf-8') as f:
    manzanas_data = json.load(f)

df_candidatos = Instancia.df_candidatos
df_demandas   = Instancia.df_demandas
phi           = Instancia.phi
r             = Instancia.r
I             = Instancia.I
J             = Instancia.J

# =============================================================================
# EXTRAER SITIOS ACTIVADOS Y CAPACIDADES
# =============================================================================

df_y_A1  = pd.read_excel('mi_reporte_A1.xlsx', sheet_name='Variable_Y')
sitios_A1 = set(df_y_A1[df_y_A1['y[j,k]'] > 0.5]['J (Candidato)'].unique())

df_y_A2  = pd.read_excel('mi_reporte_A2.xlsx', sheet_name='Variable_Y')
sitios_A2 = set(df_y_A2[df_y_A2['y[j,k]'] > 0.5]['J (Candidato)'].unique())

df_A3_det = pd.read_excel('mi_reporte_A3.xlsx', sheet_name='Detalle Candidatos')
df_A3_act = df_A3_det[df_A3_det['Candidato_Activo'] == 'SI'].drop_duplicates('Candidato')
sitios_A3 = set(df_A3_act['Candidato'].unique())

df_A1D_det = pd.read_excel('mi_reporte_A1-D.xlsx', sheet_name='Detalle Candidatos')
df_A1D_act = df_A1D_det[df_A1D_det['Candidato_Activo'] == 'SI'].drop_duplicates('Candidato')

df_A2D_det = pd.read_excel('mi_reporte_A2-D.xlsx', sheet_name='Detalle Candidatos')
df_A2D_act = df_A2D_det[df_A2D_det['Candidato_Activo'] == 'SI'].drop_duplicates('Candidato')

todos_sitios = sitios_A1 | sitios_A2 | sitios_A3

ovf_A1D = df_A1D_det['Overflow'].sum()
ovf_A2D = df_A2D_det['Overflow'].sum()
ovf_A3  = df_A3_det['Overflow'].sum()

# =============================================================================
# KG RECIBIDOS Y CAPACIDAD POR BIN
# =============================================================================

def build_bin_info(df_act):
    info = {}
    for _, row in df_act.iterrows():
        j   = row['Candidato']
        kg  = row.get('Residuos_Recibidos', 0)
        cap = row.get('Capacidad_Contenedor', None)
        info[j] = (kg, cap)
    return info

bin_info_A1D = build_bin_info(df_A1D_act)
bin_info_A2D = build_bin_info(df_A2D_act)
bin_info_A3  = build_bin_info(df_A3_act)

# =============================================================================
# DEMANDA q POR PUNTO
# =============================================================================

VIVIENDAS_TOTALES = 65_017
FACTOR_SEMANAL    = 0.24

np.random.seed(42)
viviendas_arr = np.random.randint(5, 4317, len(I))
viviendas_arr = viviendas_arr * (VIVIENDAS_TOTALES / viviendas_arr.sum())
q_dict = {i: FACTOR_SEMANAL * viviendas_arr[idx] for idx, i in enumerate(I)}

# =============================================================================
# COBERTURA (solo para print informativo)
# =============================================================================

demanda_cubierta = set()
for i in I:
    for j in sitios_A3:
        if phi.get((i, j), np.inf) < r[i]:
            demanda_cubierta.add(i)
            break

n_cub   = len(demanda_cubierta)
n_total = len(I)
total_q    = sum(q_dict.values())
q_cubierta = sum(q_dict[i] for i in demanda_cubierta)
pct_cov    = 100 * q_cubierta / total_q

print(f"  Puntos totales: {n_total}")
print(f"  Puntos cubiertos: {n_cub}/{n_total}")
print(f"  Demanda cubierta: {q_cubierta:.1f} kg/sem  ({pct_cov:.2f}%)")
print(f"  Overflow A1-D: {ovf_A1D:.1f} kg/sem  ({ovf_A1D*SEMANAS/KG_TON:.2f} ton/año)")
print(f"  Overflow A2-D: {ovf_A2D:.1f} kg/sem  ({ovf_A2D*SEMANAS/KG_TON:.2f} ton/año)")
print(f"  Overflow A3:   {ovf_A3:.1f} kg/sem  ({ovf_A3*SEMANAS/KG_TON:.2f} ton/año)")

# =============================================================================
# FUNCIÓN: DIBUJAR CÍRCULO MULTI-MODELO (wedges)
# =============================================================================

def dibujar_bin(ax, lon, lat, modelos_presentes, radio_deg=0.0006):
    color_map = {'A1': COLOR_A1, 'A2': COLOR_A2, 'A3': COLOR_A3}
    n = len(modelos_presentes)
    sector = 360 / n
    theta_start = 90
    for modelo in modelos_presentes:
        wedge = mpatches.Wedge(
            center=(lon, lat),
            r=radio_deg,
            theta1=theta_start - sector,
            theta2=theta_start,
            facecolor=color_map[modelo],
            edgecolor='black',
            linewidth=0.6,
            zorder=20,
            transform=ax.transData,
        )
        ax.add_patch(wedge)
        theta_start -= sector

# =============================================================================
# ANTI-COLISIÓN DE CAJITAS
# =============================================================================

def solapan(ax_, ay, bx, by):
    return abs(ax_ - bx) < BOX_W * 1.1 and abs(ay - by) < BOX_H * 2.0

def tapa_bin(cx, cy, bx, by):
    return abs(cx - bx) < BOX_W * 0.8 and abs(cy - by) < BOX_H * 1.5

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
                       for k in range(N) if k != idx): continue
                mejor = (dx, dy); break
        if mejor is None:
            mejor = (0, DISTANCIAS[0])
        info['offset'] = mejor
        posiciones.append((lon + mejor[0], lat + mejor[1]))
    return sitios_info

# =============================================================================
# CONSTRUIR LISTA DE SITIOS
# =============================================================================

coord_map = {}
for _, row in df_candidatos.iterrows():
    coord_map[row['id_unico']] = (row['longitud'], row['latitud'])

sitios_info = []
for j in todos_sitios:
    lon, lat = coord_map.get(j, (None, None))
    if lon is None:
        continue

    modelos = []
    if j in sitios_A1: modelos.append('A1')
    if j in sitios_A2: modelos.append('A2')
    if j in sitios_A3: modelos.append('A3')

    if j in bin_info_A3:
        kg, cap = bin_info_A3[j]
    elif j in bin_info_A1D:
        kg, cap = bin_info_A1D[j]
    elif j in bin_info_A2D:
        kg, cap = bin_info_A2D[j]
    else:
        kg, cap = None, None

    occ_pct = (kg / cap * 100) if (kg is not None and cap and cap > 0) else None

    sitios_info.append({
        'sitio'   : j,
        'lon'     : lon,
        'lat'     : lat,
        'modelos' : modelos,
        'en_A3'   : j in sitios_A3,
        'kg'      : kg,
        'cap'     : cap,
        'occ_pct' : occ_pct,
    })

sitios_info = calcular_offsets(sitios_info)

# =============================================================================
# FUNCIÓN: ROSA DE LOS VIENTOS CLÁSICA
# =============================================================================

def add_patch_no_clip(ax, patch):
    """Añade un patch al eje sin ningún clipping."""
    ax.add_patch(patch)
    patch.set_clip_on(False)
    patch.set_clip_path(None)

def dibujar_norte(ax, x=0.15, y=0.20, size=0.055):
    from matplotlib.patches import Polygon as MplPolygon
    t = ax.transAxes

    def pt(dx, dy):
        return (x + dx * size, y + dy * size)

    # Punta larga N-S (gris oscuro)
    add_patch_no_clip(ax, MplPolygon(
        [pt(0, 1.4), pt(0.18, 0), pt(0, -1.4), pt(-0.18, 0)],
        closed=True, facecolor='#444444', edgecolor='black',
        linewidth=0.6, zorder=42, transform=t))

    # Punta larga E-O (gris claro)
    add_patch_no_clip(ax, MplPolygon(
        [pt(1.4, 0), pt(0, 0.18), pt(-1.4, 0), pt(0, -0.18)],
        closed=True, facecolor='#cccccc', edgecolor='black',
        linewidth=0.6, zorder=42, transform=t))

    # 4 puntas diagonales
    for p1, p2, p3 in [
        (pt(0, 0.18),  pt(0.85, 0.85),  pt(0.18, 0)),
        (pt(0.18, 0),  pt(0.85, -0.85), pt(0, -0.18)),
        (pt(0, -0.18), pt(-0.85, -0.85),pt(-0.18, 0)),
        (pt(-0.18, 0), pt(-0.85, 0.85), pt(0, 0.18)),
    ]:
        add_patch_no_clip(ax, MplPolygon(
            [p1, p2, p3], closed=True, facecolor='#888888',
            edgecolor='black', linewidth=0.5, zorder=43, transform=t))

    # Triángulos blancos internos (efecto bicolor)
    for p1, p2, p3 in [
        (pt(0, 1.4),  pt(0, 0), pt(-0.18, 0)),
        (pt(0, -1.4), pt(0, 0), pt(0.18, 0)),
        (pt(1.4, 0),  pt(0, 0), pt(0, -0.18)),
        (pt(-1.4, 0), pt(0, 0), pt(0, 0.18)),
    ]:
        add_patch_no_clip(ax, MplPolygon(
            [p1, p2, p3], closed=True, facecolor='white',
            edgecolor='none', linewidth=0, zorder=44, transform=t))
    
    # Líneas del centro a las puntas cardinales (reemplazan los bordes borrados)
    for dx, dy in [(0, 1.4), (0, -1.4), (1.4, 0), (-1.4, 0)]:
        x0, y0 = pt(0, 0)
        x1, y1 = pt(dx, dy)
        ax.plot([x0, x1], [y0, y1], color='black', linewidth=0.4,
                transform=t, zorder=45, clip_on=False)

    # Círculo central
    add_patch_no_clip(ax, mpatches.Circle(
        (x, y), radius=size * 0.12, transform=t,
        facecolor='white', edgecolor='black',
        linewidth=0.8, zorder=45))

    # Letras cardinales
    offset_letra = size * 1.75
    for letra, dx, dy in [('N', 0, 1), ('S', 0, -1), ('E', 1, 0), ('O', -1, 0)]:
        ax.text(x + dx * offset_letra, y + dy * offset_letra, letra,
                transform=t, fontsize=8, fontweight='bold',
                ha='center', va='center', color='black',
                zorder=46, clip_on=False)

# =============================================================================
# FIGURA
# =============================================================================

fig, ax = plt.subplots(figsize=(12, 10))
ax.set_facecolor('white')

# Manzanas
for feat in manzanas_data['features']:
    geom  = feat['geometry']
    polys = ([geom['coordinates'][0]] if geom['type'] == 'Polygon'
             else [p[0] for p in geom['coordinates']])
    for coords in polys:
        xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
        ax.fill(xs, ys, facecolor='#f5f5f5', edgecolor='#555555',
                linewidth=0.3, zorder=4)

# Puntos de demanda — todos en azul pastel
dem_pts = df_demandas[['longitud', 'latitud']].values
q_vals  = np.array([q_dict[i] for i in I])
p96     = np.percentile(q_vals, 96)
q_min, q_max = q_vals.min(), q_vals.max()
sizes = np.where(
    q_vals <= p96,
    8  + (q_vals - q_min) / (p96   - q_min + 1e-9) * 18,
    80 + (q_vals - p96)   / (q_max - p96   + 1e-9) * 270
)
ax.scatter(dem_pts[:, 0], dem_pts[:, 1],
           c=COLOR_NO_ASIGNADO, s=sizes, alpha=0.75, zorder=10)

# Bins con wedges y cajitas
RADIO_DEG = 0.0006

for info in sitios_info:
    lon, lat   = info['lon'], info['lat']
    off        = info['offset']
    tlon, tlat = lon + off[0], lat + off[1]
    kg         = info['kg']
    occ        = info['occ_pct']

    dibujar_bin(ax, lon, lat, info['modelos'], radio_deg=RADIO_DEG)

    if info['en_A3'] and kg is not None:
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

# Ejes y límites
ax.set_xlabel('Longitude', fontsize=10)
ax.set_ylabel('Latitude', fontsize=10)
ax.set_xlim(-70.738, -70.665)
ax.set_ylim(-33.490, -33.438)
ax.set_aspect('equal')

# Rosa de los vientos
dibujar_norte(ax, x=0.15, y=0.20, size=0.045)

# Título
ax.set_title(
    f"SL-RBLP  |  Baseline scenario  ({FACTOR_SEMANAL * SEMANAS:.2f} kg/hh/year)",
    fontsize=12, fontweight='bold', pad=8
)

# Overflow al pie
ovf_text = f"SL-RBLP overflow: {ovf_A3:.1f} kg/week  \u2261  {ovf_A3*SEMANAS/KG_TON:.2f} metric tonnes/year"
ax.text(0.5, 0.015, ovf_text,
        transform=ax.transAxes, fontsize=10, ha='center', va='bottom',
        color='#C0392B', fontweight='bold',
        bbox=dict(facecolor='white', edgecolor='#C0392B',
                  boxstyle='round,pad=0.3', alpha=0.9), zorder=30)

# Leyenda
legend_elements = [
    Line2D([0],[0], marker='o', color='w',
           markerfacecolor=COLOR_NO_ASIGNADO, markersize=6, alpha=0.7,
           label=f'Demand points (n={n_total})'),
    Line2D([0],[0], marker='o', color='w',
           markerfacecolor=COLOR_A1, markeredgecolor='black', markersize=9,
           label=f'SL-RBLP-A1-D (n={len(sitios_A1)})'),
    Line2D([0],[0], marker='o', color='w',
           markerfacecolor=COLOR_A2, markeredgecolor='black', markersize=9,
           label=f'SL-RBLP-A2-D (n={len(sitios_A2)})'),
    Line2D([0],[0], marker='o', color='w',
           markerfacecolor=COLOR_A3, markeredgecolor='black', markersize=9,
           label=f'SL-RBLP (n={len(sitios_A3)})'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=8.5,
          framealpha=1, edgecolor='black', fancybox=False)

# Barra de escala
lat_c  = -33.47
km_deg = 111 * np.cos(np.radians(abs(lat_c)))
sx, sy = -70.736, -33.488
for i in range(5):
    rect = plt.Rectangle((sx + i/km_deg, sy), 1/km_deg, 0.0015,
                          facecolor='black' if i % 2 == 0 else 'white',
                          edgecolor='black', linewidth=0.5, zorder=25)
    ax.add_patch(rect)
for i in range(6):
    ax.text(sx + i/km_deg, sy - 0.0015, str(i), ha='center', fontsize=8)
ax.text(sx + 5.3/km_deg, sy + 0.0003, '(km)', fontsize=8)

# =============================================================================
# GUARDAR
# =============================================================================
plt.tight_layout()
plt.savefig('figura_comparacion_ubicaciones.png', dpi=200,
            bbox_inches='tight', facecolor='white')
plt.savefig('figura_comparacion_ubicaciones.pdf',
            bbox_inches='tight', facecolor='white')
print("\n✓ figura_comparacion_ubicaciones.png/.pdf guardadas")
plt.show()