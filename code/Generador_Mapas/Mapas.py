# -*- coding: utf-8 -*-
"""
Mapa de Estación Central con ZONAS COLOREADAS
==============================================
v17: Rosa de los vientos añadida
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.path import Path
from matplotlib.patches import Polygon as MplPolygon
import numpy as np
import json
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon as ShapelyPolygon, MultiPolygon
from shapely.ops import unary_union

# =============================================================================
# CARGAR DATOS
# =============================================================================

print("Cargando datos...")

with open('manzanas_estacion_central.geojson', 'r', encoding='utf-8') as f:
    manzanas_data = json.load(f)

tree = ET.parse('Estación Central Case Study.kml')
root = tree.getroot()

demandas = []
candidatos = []
zona_coords = None

for pm in root.findall('.//{http://www.opengis.net/kml/2.2}Placemark'):
    name_elem = pm.find('{http://www.opengis.net/kml/2.2}n')
    if name_elem is None:
        name_elem = pm.find('{http://www.opengis.net/kml/2.2}name')
    pm_name = name_elem.text if name_elem is not None else ''
    
    point = pm.find('.//{http://www.opengis.net/kml/2.2}Point/{http://www.opengis.net/kml/2.2}coordinates')
    if point is not None:
        coords = point.text.strip().split(',')
        lon, lat = float(coords[0]), float(coords[1])
        if 'loc_' in pm_name.lower():
            candidatos.append([lon, lat])
        elif 'punto' in pm_name.lower():
            demandas.append([lon, lat])
        else:
            demandas.append([lon, lat])
    
    polygon = pm.find('.//{http://www.opengis.net/kml/2.2}Polygon//{http://www.opengis.net/kml/2.2}coordinates')
    if polygon is not None and pm_name == 'Zona':
        coords_raw = polygon.text.strip()
        coords_list = []
        for c in coords_raw.split():
            parts = c.split(',')
            if len(parts) >= 2:
                coords_list.append([float(parts[0]), float(parts[1])])
        zona_coords = np.array(coords_list)

dem_points  = np.array(demandas)
cand_points = np.array(candidatos)

print(f"  Manzanas: {len(manzanas_data['features'])}")
print(f"  Demandas: {len(demandas)}")
print(f"  Candidatos: {len(candidatos)}")

# =============================================================================
# DEFINIR ZONAS
# =============================================================================

zona_amarilla = [
    (-70.693, -33.443), (-70.670, -33.443), (-70.670, -33.448),
    (-70.685, -33.451), (-70.693, -33.449), (-70.693, -33.443),
]

zona_roja = [
    (-70.706, -33.4513), (-70.702, -33.452), (-70.701, -33.4548),
    (-70.692, -33.4508), (-70.691, -33.454), (-70.708, -33.458),
    (-70.706, -33.4513),
]

zona_verde_medio = [
    (-70.701, -33.463), (-70.702, -33.470), (-70.702, -33.4734),
    (-70.6976, -33.474), (-70.697, -33.461), (-70.700, -33.463),
]

zona_blanca_extra = [
    (-70.720, -33.474), (-70.721, -33.4727), (-70.718, -33.4706),
    (-70.712, -33.4679), (-70.7122, -33.469), (-70.720, -33.474),
]

zona_verde_auxiliar = [
    (-70.71213, -33.468), (-70.707, -33.4655), (-70.7077, -33.47244),
    (-70.71361, -33.4716), (-70.7134, -33.4699), (-70.71256, -33.47008),
    (-70.71213, -33.468),
]

# =============================================================================
# CREAR PATHS
# =============================================================================

path_amarillo    = Path(zona_amarilla)
path_rojo        = Path(zona_roja)
path_verde_medio = Path(zona_verde_medio)
path_blanca_extra= Path(zona_blanca_extra)
path_zona_estudio= Path(zona_coords) if zona_coords is not None else None

from shapely.geometry import Point
demandas_points = [Point(lon, lat) for lon, lat in demandas]

def get_centroid(geometry):
    if geometry['type'] == 'Polygon':
        coords = geometry['coordinates'][0]
    elif geometry['type'] == 'MultiPolygon':
        coords = geometry['coordinates'][0][0]
    else:
        return None, None
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return np.mean(xs), np.mean(ys)

def get_shapely_polygon(geometry):
    try:
        if geometry['type'] == 'Polygon':
            return ShapelyPolygon(geometry['coordinates'][0])
        elif geometry['type'] == 'MultiPolygon':
            polys = [ShapelyPolygon(p[0]) for p in geometry['coordinates']]
            return MultiPolygon(polys)
    except:
        return None
    return None

def manzana_contiene_demanda(shapely_poly, demandas_points):
    if shapely_poly is None:
        return False
    for pt in demandas_points:
        if shapely_poly.contains(pt):
            return True
    return False

# =============================================================================
# FUNCIÓN PARA RELLENAR SIN HUECOS
# =============================================================================

def rellenar_sin_huecos(geom, color, ax, zorder=4.5):
    if geom.geom_type == 'Polygon':
        xs, ys = geom.exterior.xy
        ax.fill(xs, ys, facecolor=color, edgecolor='none', zorder=zorder)
    elif geom.geom_type == 'MultiPolygon':
        for poly in geom.geoms:
            xs, ys = poly.exterior.xy
            ax.fill(xs, ys, facecolor=color, edgecolor='none', zorder=zorder)

# =============================================================================
# CLASIFICAR MANZANAS
# =============================================================================

print("Clasificando manzanas...")

manzanas_amarillas      = []
manzanas_rojas          = []
manzanas_verde_medio    = []
manzanas_zona_estudio   = []
manzanas_verdes_exterior= []
manzanas_clasificadas   = []

poly_verde_aux = ShapelyPolygon(zona_verde_auxiliar)

for feat in manzanas_data['features']:
    geom = feat['geometry']
    cx, cy = get_centroid(geom)
    shapely_poly = get_shapely_polygon(geom)

    if cx is not None:
        if path_amarillo.contains_point((cx, cy)):
            facecolor = '#f4d03f'
            if shapely_poly: manzanas_amarillas.append(shapely_poly)
        elif path_rojo.contains_point((cx, cy)):
            facecolor = '#e6a89c'
            if shapely_poly: manzanas_rojas.append(shapely_poly)
        elif path_verde_medio.contains_point((cx, cy)):
            facecolor = '#a8d5a2'
            if shapely_poly: manzanas_verde_medio.append(shapely_poly)
        elif manzana_contiene_demanda(shapely_poly, demandas_points):
            facecolor = '#f5f5f5'
            if shapely_poly: manzanas_zona_estudio.append(shapely_poly)
        elif path_blanca_extra.contains_point((cx, cy)):
            facecolor = '#f5f5f5'
            if shapely_poly: manzanas_zona_estudio.append(shapely_poly)
        elif path_zona_estudio is not None and path_zona_estudio.contains_point((cx, cy)):
            facecolor = '#f5f5f5'
            if shapely_poly: manzanas_zona_estudio.append(shapely_poly)
        else:
            facecolor = '#a8d5a2'
            if shapely_poly: manzanas_verdes_exterior.append(shapely_poly)
    else:
        facecolor = '#a8d5a2'
        if shapely_poly: manzanas_verdes_exterior.append(shapely_poly)

    manzanas_clasificadas.append((geom, facecolor))

print(f"  Amarillas: {len(manzanas_amarillas)}")
print(f"  Rojas: {len(manzanas_rojas)}")
print(f"  Verde medio: {len(manzanas_verde_medio)}")
print(f"  Zona estudio: {len(manzanas_zona_estudio)}")
print(f"  Verde exterior: {len(manzanas_verdes_exterior)}")

# =============================================================================
# FUNCIÓN: ROSA DE LOS VIENTOS
# =============================================================================

def add_patch_no_clip(ax, patch):
    ax.add_patch(patch)
    patch.set_clip_on(False)
    patch.set_clip_path(None)

def dibujar_norte(ax, x=0.15, y=0.20, size=0.055): 
    """
    Rosa de los vientos clásica con 8 puntas y letras N/S/E/O.
    x, y: centro en coordenadas de ejes (0-1). size: tamaño relativo.
    """
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

    # Triángulos blancos internos (sin borde para evitar artefactos)
    for p1, p2, p3 in [
        (pt(0, 1.4),  pt(0, 0), pt(-0.18, 0)),
        (pt(0, -1.4), pt(0, 0), pt(0.18, 0)),
        (pt(1.4, 0),  pt(0, 0), pt(0, -0.18)),
        (pt(-1.4, 0), pt(0, 0), pt(0, 0.18)),
    ]:
        add_patch_no_clip(ax, MplPolygon(
            [p1, p2, p3], closed=True, facecolor='white',
            edgecolor='none', linewidth=0, zorder=44, transform=t))

    # Líneas del centro a las puntas cardinales
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
# CREAR FIGURA
# =============================================================================

print("Generando mapa...")

fig, ax = plt.subplots(figsize=(12, 10))
ax.set_facecolor('white')

# -------------------------------------------------------------------------
# PASO 1: RELLENO DE MANZANAS (sin borde)
# -------------------------------------------------------------------------

for geom, facecolor in manzanas_clasificadas:
    if geom['type'] == 'Polygon':
        coords = geom['coordinates'][0]
        xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
        ax.fill(xs, ys, facecolor=facecolor, edgecolor='none', zorder=4)
    elif geom['type'] == 'MultiPolygon':
        for poly in geom['coordinates']:
            coords = poly[0]
            xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
            ax.fill(xs, ys, facecolor=facecolor, edgecolor='none', zorder=4)

# -------------------------------------------------------------------------
# PASO 1.1–1.4: RELLENAR HUECOS INTERNOS POR ZONA
# -------------------------------------------------------------------------

for manzanas, color, bsize in [
    (manzanas_amarillas,       '#f4d03f', 0.0003),
    (manzanas_rojas,           '#e6a89c', 0.0003),
    (manzanas_verde_medio,     '#a8d5a2', 0.0003),
    (manzanas_verdes_exterior, '#a8d5a2', 0.00015),
]:
    if manzanas:
        union   = unary_union(manzanas)
        cerrado = union.buffer(bsize).buffer(-bsize)
        rellenar_sin_huecos(cerrado, color, ax, zorder=4.5)

# -------------------------------------------------------------------------
# PASO 1.4b: PARCHES MANUALES
# -------------------------------------------------------------------------

zona_parche_1 = [
    (-70.711, -33.471), (-70.709, -33.4715), (-70.709, -33.47239),
    (-70.711, -33.472), (-70.711, -33.471),
]
zona_parche_2 = [
    (-70.707, -33.451), (-70.705, -33.451), (-70.705, -33.452),
    (-70.707, -33.452), (-70.707, -33.451),
]

for zona_parche in [zona_parche_1, zona_parche_2]:
    poly_parche = ShapelyPolygon(zona_parche)
    manzanas_en_parche = [m for m in manzanas_verdes_exterior
                          if poly_parche.intersects(m)]
    if manzanas_en_parche:
        parche_union  = unary_union(manzanas_en_parche)
        parche_cerrado= parche_union.buffer(0.0007).buffer(-0.0007)
        rellenar_sin_huecos(parche_cerrado, '#a8d5a2', ax, zorder=4.6)

# -------------------------------------------------------------------------
# PASO 1.5: PARCHE VERDE AUXILIAR
# -------------------------------------------------------------------------

for feat in manzanas_data['features']:
    shapely_poly = get_shapely_polygon(feat['geometry'])
    if shapely_poly and poly_verde_aux.intersects(shapely_poly):
        interseccion = poly_verde_aux.intersection(shapely_poly)
        if not interseccion.is_empty:
            if interseccion.geom_type == 'Polygon':
                xs, ys = interseccion.exterior.xy
                ax.fill(xs, ys, facecolor='#a8d5a2', edgecolor='none', zorder=5)
            elif interseccion.geom_type == 'MultiPolygon':
                for poly in interseccion.geoms:
                    xs, ys = poly.exterior.xy
                    ax.fill(xs, ys, facecolor='#a8d5a2', edgecolor='none', zorder=5)

# -------------------------------------------------------------------------
# PASO 1.6: BORDES DE MANZANAS
# -------------------------------------------------------------------------

for geom, _ in manzanas_clasificadas:
    if geom['type'] == 'Polygon':
        coords = geom['coordinates'][0]
        xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
        ax.plot(xs, ys, color='#555555', linewidth=0.25, zorder=6)
    elif geom['type'] == 'MultiPolygon':
        for poly in geom['coordinates']:
            coords = poly[0]
            xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
            ax.plot(xs, ys, color='#555555', linewidth=0.25, zorder=6)

# -------------------------------------------------------------------------
# PASO 2: PUNTOS DE DEMANDA Y CANDIDATOS
# -------------------------------------------------------------------------

VIVIENDAS_TOTALES = 65_017
FACTOR_SEMANAL    = 0.24

np.random.seed(42)
viviendas_por_bloque = np.random.randint(5, 4317, len(dem_points))
viviendas_por_bloque = viviendas_por_bloque * (VIVIENDAS_TOTALES / viviendas_por_bloque.sum())
q_demanda = FACTOR_SEMANAL * viviendas_por_bloque

# Sin deduplicación: usar todos los 593 puntos
dem_points_unicos = dem_points
q_demanda_unicos  = q_demanda

q_min, q_max = q_demanda_unicos.min(), q_demanda_unicos.max()
percentil_96 = np.percentile(q_demanda_unicos, 96)

tamaños_escalados = np.where(
    q_demanda_unicos <= percentil_96,
    8  + (q_demanda_unicos - q_min) / (percentil_96 - q_min + 1e-9) * 18,
    80 + (q_demanda_unicos - percentil_96) / (q_max - percentil_96 + 1e-9) * 270
)

ax.scatter(dem_points_unicos[:, 0], dem_points_unicos[:, 1],
           c='#5B9BD5', s=tamaños_escalados, alpha=0.7, zorder=15)
ax.scatter(cand_points[:, 0], cand_points[:, 1],
           c='#d32f2f', s=30, alpha=0.95, zorder=20)

# =============================================================================
# CONFIGURACIÓN EJES
# =============================================================================

ax.set_xlabel('Longitude', fontsize=11)
ax.set_ylabel('Latitude',  fontsize=11)
ax.set_xlim(-70.738, -70.665)
ax.set_ylim(-33.490, -33.438)
ax.set_aspect('equal')

# =============================================================================
# ROSA DE LOS VIENTOS
# =============================================================================

dibujar_norte(ax, x=0.15, y=0.23, size=0.045)

# =============================================================================
# LEYENDA
# =============================================================================

legend_elements = [
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#d32f2f',
           markersize=8, label='Candidate Locations'),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#5B9BD5',
       markersize=6, alpha=0.7, label=f'Demand points (n={len(dem_points_unicos)+2})'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=10,
          framealpha=1, edgecolor='black', fancybox=False)

# =============================================================================
# BARRA DE ESCALA
# =============================================================================

lat_center    = -33.47
km_per_deg    = 111 * np.cos(np.radians(abs(lat_center)))
scale_start   = -70.736
scale_y       = -33.486

for i in range(5):
    width = 1 / km_per_deg
    rect  = plt.Rectangle((scale_start + i*width, scale_y), width, 0.0015,
                           facecolor='black' if i % 2 == 0 else 'white',
                           edgecolor='black', linewidth=0.5, zorder=25)
    ax.add_patch(rect)
for i in range(6):
    ax.text(scale_start + i/km_per_deg, scale_y - 0.0015, str(i),
            ha='center', fontsize=9)
ax.text(scale_start + 5.3/km_per_deg, scale_y + 0.0003, '(km)', fontsize=9)

# =============================================================================
# GUARDAR
# =============================================================================

print(f"  Demandas leídas: {len(demandas)}") 

plt.tight_layout()
plt.savefig('mapa_estacion_central_colores.png', dpi=200,
            bbox_inches='tight', facecolor='white')
plt.savefig('mapa_estacion_central_colores.pdf',
            bbox_inches='tight', facecolor='white')
print("\n✓ mapa_estacion_central_colores.png/.pdf guardados")
plt.show()