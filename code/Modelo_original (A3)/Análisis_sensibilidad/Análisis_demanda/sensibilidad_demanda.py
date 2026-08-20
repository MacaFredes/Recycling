# -*- coding: utf-8 -*-
"""
ANÁLISIS DE SENSIBILIDAD - DEMANDA  [VERSIÓN CORREGIDA v4]
=============================================================
Igual que v3, con Excel de salida enriquecido.

sensitivity_demand_solutions.xlsx ahora incluye por escenario
(low / baseline / high):

  {label}_y        → ubicaciones por modelo (j, k, type_k)       [ya existía]
  {label}_x        → asignación demanda por modelo (i, j, x, q_i, kg_assigned)
  {label}_q        → demanda por punto (i, q)                     [ya existía]
  {label}_occ_A3   → ocupación por bin de A3:
                       site_j, type_k, capacity_kg,
                       demand_assigned_kg, overflow_kg,
                       net_stored_kg, occupancy_pct
  {label}_occ_A1D  → ídem para ubicaciones de A1 evaluadas bajo A3
  {label}_occ_A2D  → ídem para ubicaciones de A2 evaluadas bajo A3
  {label}_costs    → desglose de costos del escenario:
                       obj_A1, obj_A2, obj_A3,
                       cost_A1D (real), cost_A2D (real),
                       overflow_A1D_kg, overflow_A2D_kg, overflow_A3_kg,
                       hidden_cost_A1D, hidden_cost_A2D,
                       overflow_A1D_tpa, overflow_A2D_tpa, overflow_A3_tpa,
                       hidden_cost_A1D_annual, hidden_cost_A2D_annual
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
import json
import Instancia

# =============================================================================
# PARÁMETROS
# =============================================================================
VIDA_UTIL         = 260
SEMANAS           = 52
KG_TON            = 1000
FACTOR_BASELINE   = 0.24
VIVIENDAS_TOTALES = 65_017
BUDGET_FIJO       = 5616 / VIDA_UTIL
FACTOR_BASELINE_ANUAL = round(FACTOR_BASELINE * SEMANAS, 2)

# =============================================================================
# UBICACIONES HARDCODEADAS — solo para el escenario ×1.00
# =============================================================================
UBICACIONES_A1_BASELINE = {
    ('punto_109', 1): 1, ('punto_114', 3): 1, ('punto_12',  3): 1,
    ('punto_22',  2): 1, ('punto_28',  3): 1, ('punto_38',  1): 1,
    ('punto_39',  1): 1, ('punto_50',  2): 1, ('punto_67',  3): 1,
    ('punto_75',  3): 1,
}
UBICACIONES_A2_BASELINE = {
    ('punto_114', 3): 1, ('punto_12',  3): 1, ('punto_23',  1): 1,
    ('punto_25',  1): 1, ('punto_26',  3): 1, ('punto_31',  1): 1,
    ('punto_41',  2): 1, ('punto_50',  2): 1, ('punto_67',  3): 1,
    ('punto_74',  3): 1,
}
UBICACIONES_A3_BASELINE = {
    ('punto_114', 3): 1, ('punto_12',  3): 1, ('punto_21',  1): 1,
    ('punto_24',  1): 1, ('punto_26',  3): 1, ('punto_31',  1): 1,
    ('punto_41',  2): 1, ('punto_52',  2): 1, ('punto_67',  3): 1,
    ('punto_75',  3): 1,
}
OBJ_A1_BASELINE = 872.99
OBJ_A2_BASELINE = 872.85
OBJ_A3_BASELINE = 885.89

def _bins_por_tipo_from_dict(ub_y, K):
    return {k: sum(1 for (j, kk) in ub_y if kk == k) for k in K}

# =============================================================================
# MULTIPLICADORES
# =============================================================================
MULTIPLICADORES = [0.83, 0.92, 1.00, 1.08, 1.17, 1.25]
FACTORES        = [round(FACTOR_BASELINE * m, 4) for m in MULTIPLICADORES]


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def calcular_q(factor, I):
    np.random.seed(42)
    viviendas = np.random.randint(5, 4317, len(I))
    viviendas = viviendas * (VIVIENDAS_TOTALES / viviendas.sum())
    return {i: round(factor * viviendas[idx], 2) for idx, i in enumerate(I)}


def _bins_por_tipo(ubicaciones_y, K):
    return {k: sum(1 for (j, kk) in ubicaciones_y if kk == k) for k in K}


def build_occ_df(ubicaciones_y, x_vals, z_vals, q, d, J, K):
    """
    Construye un DataFrame de ocupación por bin a partir de una solución.
    Funciona tanto para A3 propio como para A1-D / A2-D evaluados bajo A3.
    """
    rows = []
    for (j, k), v in ubicaciones_y.items():
        if v < 0.5:
            continue
        capacity_kg      = d.get((j, k), 0)
        demand_assigned  = sum(q.get(i, 0) * x_vals.get((i, j), 0)
                               for i in q)
        overflow_kg      = z_vals.get(j, 0.0)
        net_stored_kg    = demand_assigned - overflow_kg
        occupancy_pct    = (net_stored_kg / capacity_kg * 100
                            if capacity_kg > 0 else 0.0)
        rows.append({
            'site_j'           : j,
            'type_k'           : k,
            'capacity_kg'      : round(capacity_kg, 2),
            'demand_assigned_kg': round(demand_assigned, 2),
            'overflow_kg'      : round(overflow_kg, 4),
            'net_stored_kg'    : round(net_stored_kg, 2),
            'occupancy_pct'    : round(occupancy_pct, 2),
        })
    return pd.DataFrame(rows)


# =============================================================================
# MODELOS
# =============================================================================

def resolver_A1(B, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    m = gp.Model('A1')
    m.setParam("OutputFlag", 1)
    x = m.addVars(I, J, vtype=GRB.BINARY)
    y = m.addVars(J, K, vtype=GRB.BINARY)
    w = m.addVars(I, J, vtype=GRB.BINARY)
    costo_NR = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(w[i,j] for j in J)) for i in I)
    m.setObjective(costo_NR, GRB.MINIMIZE)
    Ji = {i: [j for j in J if r[i] > phi[i,j]] for i in I}
    m.addConstr(gp.quicksum(y[j,k] * f[j,k] for j in J for k in K) <= B)
    for i in I:
        m.addConstr(gp.quicksum(x[i,j] for j in J) <= 1)
        m.addConstr(gp.quicksum(x[i,j] for j in J if j not in Ji[i]) == 0)
        for j in Ji[i]:
            m.addConstr(x[i,j] <= gp.quicksum(y[j,k] for k in K))
            m.addConstr(gp.quicksum(y[j,k] for k in K) <=
                        gp.quicksum(x[i,jp] for jp in Ji[i] if phi[i,jp] <= phi[i,j]))
        for j in J:
            m.addConstr(w[i,j] <= x[i,j])
    for j in J:
        m.addConstr(gp.quicksum(y[j,k] for k in K) <= 1)
        m.addConstr(gp.quicksum(q[i] * w[i,j] for i in I) <=
                    gp.quicksum(d[j,k] * y[j,k] for k in K))
    m.setParam(GRB.Param.TimeLimit, 4000)
    m.setParam(GRB.Param.Cuts, 0)
    m.setParam(GRB.Param.Seed, 123)
    m.optimize()
    if m.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL] or m.SolCount == 0:
        return None
    if m.status in [GRB.TIME_LIMIT, GRB.SUBOPTIMAL] and m.MIPGap * 100 >= 2.5:
        return None
    ub_y = {(j,k): y[j,k].x for j in J for k in K if y[j,k].x > 0.5}
    return {
        'objective':     m.ObjVal,
        'ubicaciones_y': ub_y,
        'bins_abiertos': len(ub_y),
        'bins_por_tipo': _bins_por_tipo(ub_y, K),
        'x_vals':        {(i,j): w[i,j].x for i in I for j in J if w[i,j].x > 0.001},
    }


def resolver_A2(B, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    m = gp.Model('A2')
    m.setParam("OutputFlag", 1)
    x = m.addVars(I, J, vtype=GRB.BINARY)
    y = m.addVars(J, K, vtype=GRB.BINARY)
    w = m.addVars(I, J, vtype=GRB.CONTINUOUS, lb=0, ub=1)
    costo_NR = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(w[i,j] for j in J)) for i in I)
    m.setObjective(costo_NR, GRB.MINIMIZE)
    Ji = {i: [j for j in J if r[i] > phi[i,j]] for i in I}
    m.addConstr(gp.quicksum(y[j,k] * f[j,k] for j in J for k in K) <= B)
    for i in I:
        m.addConstr(gp.quicksum(x[i,j] for j in J) <= 1)
        m.addConstr(gp.quicksum(x[i,j] for j in J if j not in Ji[i]) == 0)
        for j in Ji[i]:
            m.addConstr(x[i,j] <= gp.quicksum(y[j,k] for k in K))
            m.addConstr(gp.quicksum(y[j,k] for k in K) <=
                        gp.quicksum(x[i,jp] for jp in Ji[i] if phi[i,jp] <= phi[i,j]))
        for j in J:
            m.addConstr(w[i,j] <= x[i,j])
    for j in J:
        m.addConstr(gp.quicksum(y[j,k] for k in K) <= 1)
        m.addConstr(gp.quicksum(q[i] * w[i,j] for i in I) <=
                    gp.quicksum(d[j,k] * y[j,k] for k in K))
    m.setParam(GRB.Param.TimeLimit, 4000)
    m.setParam(GRB.Param.Cuts, 0)
    m.setParam(GRB.Param.Seed, 123)
    m.optimize()
    if m.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL] or m.SolCount == 0:
        return None
    if m.status in [GRB.TIME_LIMIT, GRB.SUBOPTIMAL] and m.MIPGap * 100 >= 2.5:
        return None
    ub_y = {(j,k): y[j,k].x for j in J for k in K if y[j,k].x > 0.5}
    return {
        'objective':     m.ObjVal,
        'ubicaciones_y': ub_y,
        'bins_abiertos': len(ub_y),
        'bins_por_tipo': _bins_por_tipo(ub_y, K),
        'x_vals':        {(i,j): w[i,j].x for i in I for j in J if w[i,j].x > 0.001},
    }


def resolver_A3(B, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    m = gp.Model('A3')
    m.setParam("OutputFlag", 1)
    x = m.addVars(I, J, vtype=GRB.BINARY)
    y = m.addVars(J, K, vtype=GRB.BINARY)
    z = m.addVars(J, vtype=GRB.CONTINUOUS, lb=0)
    costo_dump = gp.quicksum(z[j] * c_dump[j] for j in J)
    costo_NR   = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(x[i,j] for j in J)) for i in I)
    m.setObjective(costo_dump + costo_NR, GRB.MINIMIZE)
    Ji = {i: [j for j in J if r[i] > phi[i,j]] for i in I}
    m.addConstr(gp.quicksum(y[j,k] * f[j,k] for j in J for k in K) <= B)
    for i in I:
        m.addConstr(gp.quicksum(x[i,j] for j in J) <= 1)
        m.addConstr(gp.quicksum(x[i,j] for j in J if j not in Ji[i]) == 0)
        for j in Ji[i]:
            m.addConstr(x[i,j] <= gp.quicksum(y[j,k] for k in K))
            m.addConstr(gp.quicksum(y[j,k] for k in K) <=
                        gp.quicksum(x[i,jp] for jp in Ji[i] if phi[i,jp] <= phi[i,j]))
    for j in J:
        m.addConstr(gp.quicksum(y[j,k] for k in K) <= 1)
        m.addConstr(gp.quicksum(q[i] * x[i,j] for i in I) <=
                    gp.quicksum(d[j,k] * y[j,k] for k in K) + z[j])
    m.setParam(GRB.Param.TimeLimit, 4000)
    m.setParam(GRB.Param.Cuts, 0)
    m.setParam(GRB.Param.Seed, 123)
    m.optimize()
    if m.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL] or m.SolCount == 0:
        return None
    if m.status in [GRB.TIME_LIMIT, GRB.SUBOPTIMAL] and m.MIPGap * 100 >= 2.5:
        return None
    ub_y = {(j,k): y[j,k].x for j in J for k in K if y[j,k].x > 0.5}
    return {
        'objective':     m.ObjVal,
        'ubicaciones_y': ub_y,
        'bins_abiertos': len(ub_y),
        'bins_por_tipo': _bins_por_tipo(ub_y, K),
        'overflow':      sum(z[j].x for j in J),
        'x_vals':        {(i,j): x[i,j].x for i in I for j in J if x[i,j].x > 0.001},
        'z_vals':        {j: z[j].x for j in J},
    }


def evaluar_en_A3(ubicaciones_y, B, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    """
    Evalúa ubicaciones fijas bajo demanda q usando el framework de A3.
    Ahora devuelve un dict completo con x_vals y z_vals para construir
    las hojas de ocupación en el Excel.
    """
    m = gp.Model('Eval')
    m.setParam("OutputFlag", 1)
    x = m.addVars(I, J, vtype=GRB.BINARY)
    y = m.addVars(J, K, vtype=GRB.BINARY)
    z = m.addVars(J, vtype=GRB.CONTINUOUS, lb=0)
    for j in J:
        for k in K:
            y[j,k].LB = ubicaciones_y.get((j,k), 0)
            y[j,k].UB = ubicaciones_y.get((j,k), 0)
    costo_dump = gp.quicksum(z[j] * c_dump[j] for j in J)
    costo_NR   = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(x[i,j] for j in J)) for i in I)
    m.setObjective(costo_dump + costo_NR, GRB.MINIMIZE)
    Ji = {i: [j for j in J if r[i] > phi[i,j]] for i in I}
    m.addConstr(gp.quicksum(y[j,k] * f[j,k] for j in J for k in K) <= B)
    for i in I:
        m.addConstr(gp.quicksum(x[i,j] for j in J) <= 1)
        m.addConstr(gp.quicksum(x[i,j] for j in J if j not in Ji[i]) == 0)
        for j in Ji[i]:
            m.addConstr(x[i,j] <= gp.quicksum(y[j,k] for k in K))
            m.addConstr(gp.quicksum(y[j,k] for k in K) <=
                        gp.quicksum(x[i,jp] for jp in Ji[i] if phi[i,jp] <= phi[i,j]))
    for j in J:
        m.addConstr(gp.quicksum(y[j,k] for k in K) <= 1)
        m.addConstr(gp.quicksum(q[i] * x[i,j] for i in I) <=
                    gp.quicksum(d[j,k] * y[j,k] for k in K) + z[j])
    m.setParam(GRB.Param.TimeLimit, 4000)
    m.setParam(GRB.Param.Seed, 123)
    m.optimize()
    if m.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL] or m.SolCount == 0:
        return None
    overflow_total = sum(z[j].x for j in J)
    return {
        'objective'  : m.ObjVal,
        'overflow'   : overflow_total,
        'x_vals'     : {(i,j): x[i,j].x for i in I for j in J if x[i,j].x > 0.001},
        'z_vals'     : {j: z[j].x for j in J if z[j].x > 1e-6},
    }


# =============================================================================
# FUNCIÓN: GENERAR MAPA PARA UN ESCENARIO (estilo unificado v4)
# =============================================================================

def generar_mapa_fig(sol_A1, sol_A2, sol_A3, eval_A1D, eval_A2D,
                     df_candidatos, df_demandas, q_escenario,
                     mult, label, phi, r, I, d, K):
    try:
        with open('manzanas_estacion_central.geojson', 'r', encoding='utf-8') as fg:
            manzanas_data = json.load(fg)
    except FileNotFoundError:
        print(f"  ⚠ manzanas_estacion_central.geojson no encontrado, mapa omitido.")
        return None

    # Colores por tipo de contenedor (igual que mapa de presupuesto)
    COLOR_TIPO = {1: '#E67E22', 2: '#9B59B6', 3: '#2ECC71'}
    LABEL_TIPO = {1: 'Small container', 2: 'Medium container', 3: 'Large container'}
    COLOR_ASIGNADO    = '#E74C3C'
    COLOR_NO_ASIGNADO = '#5B9BD5'
    BOX_W, BOX_H = 0.0030, 0.0014
    DISTANCIAS   = [0.0025, 0.0035, 0.0048, 0.006]
    DIRS = [(0,1),(1,0),(0,-1),(-1,0),(0.7,0.7),(-0.7,0.7),(0.7,-0.7),(-0.7,-0.7)]

    sitios_A3 = set(j for (j, k) in sol_A3['ubicaciones_y'])

    # Cobertura: punto i cubierto si hay un bin de A3 dentro de radio r[i]
    demanda_cubierta = set()
    for i in I:
        for j in sitios_A3:
            if phi.get((i, j), np.inf) < r[i]:
                demanda_cubierta.add(i)
                break

    n_cub   = len(demanda_cubierta)
    n_total = len(I)
    pct_cov = 100 * n_cub / n_total

    ovf_kg  = sol_A3.get('overflow', 0.0)
    ovf_ta  = ovf_kg * SEMANAS / KG_TON
    factor_anual = round(FACTOR_BASELINE * mult * SEMANAS, 2)

    # Construir lista de sitios con tipo y ocupación para cajitas
    x_vals_A3 = sol_A3.get('x_vals', {})
    z_vals_A3 = sol_A3.get('z_vals', {})
    sitios_info = []
    coord_map = {}
    for _, row in df_candidatos.iterrows():
        coord_map[row['id_unico']] = (row['longitud'], row['latitud'])

    for (j, k), v in sol_A3['ubicaciones_y'].items():
        if v < 0.5:
            continue
        lon, lat = coord_map.get(j, (None, None))
        if lon is None:
            continue
        capacity_kg     = d.get((j, k), 0)
        demand_assigned = sum(q_escenario.get(i, 0) * x_vals_A3.get((i, j), 0)
                              for i in q_escenario)
        overflow_kg     = z_vals_A3.get(j, 0.0)
        net_stored_kg   = demand_assigned - overflow_kg
        occ_pct         = net_stored_kg / capacity_kg * 100 if capacity_kg > 0 else 0
        sitios_info.append({
            'sitio'        : j,
            'lon'          : lon,
            'lat'          : lat,
            'type_k'       : k,
            'net_stored_kg': net_stored_kg,
            'occupancy_pct': occ_pct,
        })

    # Anti-colisión
    N        = len(sitios_info)
    bin_lons = np.array([s['lon'] for s in sitios_info])
    bin_lats = np.array([s['lat'] for s in sitios_info])

    def solapan(ax_, ay, bx, by):
        return abs(ax_ - bx) < BOX_W * 1.1 and abs(ay - by) < BOX_H * 2.0
    def tapa_bin(cx, cy, bx, by):
        return abs(cx - bx) < BOX_W * 0.8 and abs(cy - by) < BOX_H * 1.5
    def fuera_mapa(cx, cy):
        return cx < -70.737 or cx > -70.666 or cy < -33.488 or cy > -33.438

    RADIO = 0.012
    for info in sitios_info:
        info['densidad'] = sum(
            1 for other in sitios_info
            if other is not info
            and abs(other['lon'] - info['lon']) < RADIO
            and abs(other['lat'] - info['lat']) < RADIO
        )
    sitios_info.sort(key=lambda x: -x['densidad'])

    posiciones = []
    for idx, info in enumerate(sitios_info):
        lon, lat = info['lon'], info['lat']
        mejor = None
        for dist in DISTANCIAS:
            if mejor: break
            for dx_u, dy_u in DIRS:
                dx = dx_u * dist * 1.2; dy = dy_u * dist
                cx, cy = lon + dx, lat + dy
                if fuera_mapa(cx, cy): continue
                if any(solapan(cx, cy, px, py) for px, py in posiciones): continue
                if any(tapa_bin(cx, cy, bin_lons[k2], bin_lats[k2])
                       for k2 in range(N) if k2 != idx): continue
                mejor = (dx, dy); break
        if mejor is None:
            mejor = (0, DISTANCIAS[0])
        info['offset'] = mejor
        posiciones.append((lon + mejor[0], lat + mejor[1]))

    # ── FIGURA ──────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_facecolor('white')

    for feat in manzanas_data['features']:
        geom  = feat['geometry']
        polys = ([geom['coordinates'][0]] if geom['type'] == 'Polygon'
                 else [p[0] for p in geom['coordinates']])
        for coords in polys:
            xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
            ax.fill(xs, ys, facecolor='#f5f5f5', edgecolor='#555555',
                    linewidth=0.3, zorder=4)

    # Puntos de demanda
    q_vals = np.array([q_escenario.get(i, 0) for i in I])
    p96    = np.percentile(q_vals, 96)
    q_min, q_max = q_vals.min(), q_vals.max()
    sizes = np.where(
        q_vals <= p96,
        8  + (q_vals - q_min) / (p96   - q_min + 1e-9) * 18,
        80 + (q_vals - p96)   / (q_max - p96   + 1e-9) * 270
    )
    colors_dem = [COLOR_ASIGNADO if i in demanda_cubierta else COLOR_NO_ASIGNADO
                  for i in I]
    dem_pts = (df_demandas.set_index('id_unico').reindex(I)[['longitud','latitud']].values
               if 'id_unico' in df_demandas.columns
               else df_demandas[['longitud','latitud']].values)
    ax.scatter(dem_pts[:, 0], dem_pts[:, 1],
               c=colors_dem, s=sizes, alpha=0.75, zorder=10)

    # Bins A3
    for info in sitios_info:
        lon, lat   = info['lon'], info['lat']
        color      = COLOR_TIPO[info['type_k']]
        off        = info['offset']
        tlon, tlat = lon + off[0], lat + off[1]
        kg         = info['net_stored_kg']
        occ        = info['occupancy_pct']

        ax.scatter(lon, lat, c=color, s=75,
                   edgecolors='black', linewidth=0.8, zorder=20)
        label_txt = f"{int(round(kg))} kg\n({occ:.0f}%)"
        ax.plot([lon, tlon], [lat, tlat], color='#333333', lw=1.0, zorder=22)
        ax.text(tlon, tlat, label_txt,
                fontsize=7.5, fontweight='bold', color='black',
                ha='center', va='center', zorder=25,
                bbox=dict(boxstyle='square,pad=0.28', facecolor='white',
                          edgecolor='#444444', linewidth=1.0, alpha=0.95))

    ax.set_xlabel('Longitude', fontsize=10)
    ax.set_ylabel('Latitude', fontsize=10)
    ax.set_xlim(-70.738, -70.665)
    ax.set_ylim(-33.490, -33.438)
    ax.set_aspect('equal')

    ax.set_title(
        f"SL-RBLP  |  {label.capitalize()}  ({factor_anual} kg/hh/year)",
        fontsize=12, fontweight='bold', pad=8
    )

    ovf_text = (f"Overflow: {ovf_kg:.1f} kg/week  \u2261  {ovf_ta:.2f} ton/year")
    ax.text(0.5, 0.015, ovf_text,
            transform=ax.transAxes, fontsize=10, ha='center', va='bottom',
            color='#C0392B', fontweight='bold',
            bbox=dict(facecolor='white', edgecolor='#C0392B',
                      boxstyle='round,pad=0.3', alpha=0.9), zorder=30)

    # Leyenda
    legend_elements = [
        Line2D([0],[0], marker='o', color='w',
               markerfacecolor=COLOR_ASIGNADO, markersize=7, alpha=0.85,
               label=f'Assigned demand (n={n_cub}, {pct_cov:.2f}%)'),
        Line2D([0],[0], marker='o', color='w',
               markerfacecolor=COLOR_NO_ASIGNADO, markersize=6, alpha=0.7,
               label=f'Unassigned demand (n={n_total - n_cub})'),
    ]
    tipos_presentes = sorted(set(info['type_k'] for info in sitios_info))
    for k_t in tipos_presentes:
        legend_elements.append(
            Line2D([0],[0], marker='o', color='w',
                   markerfacecolor=COLOR_TIPO[k_t],
                   markeredgecolor='black', markersize=9,
                   label=LABEL_TIPO[k_t])
        )
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

    plt.tight_layout()
    return fig


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("DEMAND SENSITIVITY ANALYSIS  [VERSIÓN v4 — Excel enriquecido]")
    print(f"Baseline factor: {FACTOR_BASELINE} kg/hh/week = {FACTOR_BASELINE_ANUAL} kg/hh/year")
    print(f"Budget fijo: {BUDGET_FIJO:.4f} USD/week")
    print("=" * 70)

    I   = Instancia.I;   J   = Instancia.J;   K   = Instancia.K
    d   = Instancia.d;   phi = Instancia.phi;  r   = Instancia.r
    f   = Instancia.f;   c_dump = Instancia.c_dump;  c_nr = Instancia.c_nr
    df_candidatos = Instancia.df_candidatos
    df_demandas   = Instancia.df_demandas

    results = {
        'factor': [], 'multiplicador': [], 'factor_anual': [],
        'demanda_total_semanal': [],
        'overflow_A1D': [], 'overflow_A2D': [], 'overflow_A3': [],
        'cost_A1D': [], 'cost_A2D': [],
        'hc_A1D': [], 'hc_A2D': [],
        'obj_A1': [], 'obj_A2': [], 'obj_A3': [],
        'bins_A1': [], 'bins_A2': [], 'bins_A3': [],
    }
    types_results = {'factor': [], 'multiplicador': [], 'factor_anual': []}
    for k in K:
        types_results[f'A1_tipo{k}'] = []
        types_results[f'A2_tipo{k}'] = []
        types_results[f'A3_tipo{k}'] = []

    # Guarda todo para mapas y excel (todos los multiplicadores)
    soluciones_todas  = {}

    for idx, (factor, mult) in enumerate(zip(FACTORES, MULTIPLICADORES), 1):
        print(f"\n[{idx}/{len(FACTORES)}] Factor={factor:.4f}  ×{mult:.2f}  "
              f"({factor*SEMANAS:.2f} kg/hh/year)")

        q_esc = calcular_q(factor, I)
        demanda_total = sum(q_esc.values())
        ES_BASELINE = abs(mult - 1.00) < 0.001

        # ── A1 ────────────────────────────────────────────────────────────────
        if ES_BASELINE:
            sol_A1 = {
                'ubicaciones_y': UBICACIONES_A1_BASELINE,
                'objective':     OBJ_A1_BASELINE,
                'bins_abiertos': len(UBICACIONES_A1_BASELINE),
                'bins_por_tipo': _bins_por_tipo_from_dict(UBICACIONES_A1_BASELINE, K),
                'x_vals': {}, 'z_vals': {},
            }
        else:
            sol_A1 = resolver_A1(BUDGET_FIJO, I, J, K, d, phi, q_esc, r, f, c_dump, c_nr)
            if sol_A1 is None:
                print("  ❌ A1 falló"); continue
            sol_A1.setdefault('z_vals', {})
        print(f"  A1 → FO: {sol_A1['objective']:.2f}  tipos: {sol_A1['bins_por_tipo']}")

        # ── A2 ────────────────────────────────────────────────────────────────
        if ES_BASELINE:
            sol_A2 = {
                'ubicaciones_y': UBICACIONES_A2_BASELINE,
                'objective':     OBJ_A2_BASELINE,
                'bins_abiertos': len(UBICACIONES_A2_BASELINE),
                'bins_por_tipo': _bins_por_tipo_from_dict(UBICACIONES_A2_BASELINE, K),
                'x_vals': {}, 'z_vals': {},
            }
        else:
            sol_A2 = resolver_A2(BUDGET_FIJO, I, J, K, d, phi, q_esc, r, f, c_dump, c_nr)
            if sol_A2 is None:
                print("  ❌ A2 falló"); continue
            sol_A2.setdefault('z_vals', {})
        print(f"  A2 → FO: {sol_A2['objective']:.2f}  tipos: {sol_A2['bins_por_tipo']}")

        # ── A3 ────────────────────────────────────────────────────────────────
        if ES_BASELINE:
            sol_A3 = {
                'ubicaciones_y': UBICACIONES_A3_BASELINE,
                'objective':     OBJ_A3_BASELINE,
                'bins_abiertos': len(UBICACIONES_A3_BASELINE),
                'bins_por_tipo': _bins_por_tipo_from_dict(UBICACIONES_A3_BASELINE, K),
                'overflow':      183.66,
                'x_vals': {}, 'z_vals': {},
            }
        else:
            sol_A3 = resolver_A3(BUDGET_FIJO, I, J, K, d, phi, q_esc, r, f, c_dump, c_nr)
            if sol_A3 is None:
                print("   A3 falló"); continue
        print(f"  A3 → FO: {sol_A3['objective']:.2f}  overflow: {sol_A3['overflow']:.2f} kg")

        # ── Evaluaciones bajo A3 ──────────────────────────────────────────────
        eval_A1D = evaluar_en_A3(
            sol_A1['ubicaciones_y'], BUDGET_FIJO, I, J, K, d, phi, q_esc, r, f, c_dump, c_nr)
        if eval_A1D is None:
            print("   Eval A1-D falló"); continue

        eval_A2D = evaluar_en_A3(
            sol_A2['ubicaciones_y'], BUDGET_FIJO, I, J, K, d, phi, q_esc, r, f, c_dump, c_nr)
        if eval_A2D is None:
            print("   Eval A2-D falló"); continue

        hidden_A1 = eval_A1D['objective'] - sol_A1['objective']
        hidden_A2 = eval_A2D['objective'] - sol_A2['objective']
        print(f"  A1-D → overflow: {eval_A1D['overflow']:.2f} kg  hidden: {hidden_A1:.2f} USD/week")
        print(f"  A2-D → overflow: {eval_A2D['overflow']:.2f} kg  hidden: {hidden_A2:.2f} USD/week")

        # ── Guardar resultados ────────────────────────────────────────────────
        results['factor'].append(factor)
        results['multiplicador'].append(mult)
        results['factor_anual'].append(factor * SEMANAS)
        results['demanda_total_semanal'].append(demanda_total)
        results['overflow_A1D'].append(eval_A1D['overflow'])
        results['overflow_A2D'].append(eval_A2D['overflow'])
        results['overflow_A3'].append(sol_A3['overflow'])
        results['cost_A1D'].append(eval_A1D['objective'])
        results['cost_A2D'].append(eval_A2D['objective'])
        results['hc_A1D'].append(hidden_A1)
        results['hc_A2D'].append(hidden_A2)
        results['obj_A1'].append(sol_A1['objective'])
        results['obj_A2'].append(sol_A2['objective'])
        results['obj_A3'].append(sol_A3['objective'])
        results['bins_A1'].append(sol_A1['bins_abiertos'])
        results['bins_A2'].append(sol_A2['bins_abiertos'])
        results['bins_A3'].append(sol_A3['bins_abiertos'])

        types_results['factor'].append(factor)
        types_results['multiplicador'].append(mult)
        types_results['factor_anual'].append(factor * SEMANAS)
        for k in K:
            types_results[f'A1_tipo{k}'].append(sol_A1['bins_por_tipo'].get(k, 0))
            types_results[f'A2_tipo{k}'].append(sol_A2['bins_por_tipo'].get(k, 0))
            types_results[f'A3_tipo{k}'].append(sol_A3['bins_por_tipo'].get(k, 0))

        # Guardar todo para Excel enriquecido
        soluciones_todas[mult] = {
            'sol_A1': sol_A1, 'sol_A2': sol_A2, 'sol_A3': sol_A3,
            'eval_A1D': eval_A1D, 'eval_A2D': eval_A2D,
            'q_esc': q_esc,
            'hidden_A1': hidden_A1, 'hidden_A2': hidden_A2,
            'factor_anual': factor * SEMANAS,
        }

    df       = pd.DataFrame(results)
    df_types = pd.DataFrame(types_results)

    df['overflow_A1D_tpa'] = df['overflow_A1D'] * SEMANAS / KG_TON
    df['overflow_A2D_tpa'] = df['overflow_A2D'] * SEMANAS / KG_TON
    df['overflow_A3_tpa']  = df['overflow_A3']  * SEMANAS / KG_TON
    df['hc_A1D_anual']     = df['hc_A1D']       * SEMANAS
    df['hc_A2D_anual']     = df['hc_A2D']       * SEMANAS

    # =========================================================================
    # EXCEL PRINCIPAL
    # =========================================================================
    with pd.ExcelWriter('sensitivity_demand.xlsx', engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Results', index=False)
        df_types.to_excel(writer, sheet_name='Container_Types', index=False)
    print(f"\n✓ sensitivity_demand.xlsx guardado")

    # =========================================================================
    # EXCEL ENRIQUECIDO — soluciones + ocupación
    # =========================================================================
    MAPA_LABEL = {
        m: ("baseline" if abs(m - 1.0) < 0.01
            else "low"  if m < 1.0
            else "high")
        for m in MULTIPLICADORES
    }
    # Solo guardar mapas para escenarios extremos + baseline
    MULTS_MAPA = [m for m in MULTIPLICADORES
                  if abs(m - 1.0) < 0.01 or m == min(MULTIPLICADORES) or m == max(MULTIPLICADORES)]

    with pd.ExcelWriter('sensitivity_demand_solutions.xlsx', engine='openpyxl') as writer:
        for mult in MULTS_MAPA:
            if mult not in soluciones_todas:
                continue
            s     = soluciones_todas[mult]
            label = MAPA_LABEL[mult]
            sol_A1   = s['sol_A1'];   sol_A2 = s['sol_A2'];   sol_A3 = s['sol_A3']
            eval_A1D = s['eval_A1D']; eval_A2D = s['eval_A2D']
            q_esc    = s['q_esc']

            # {label}_y — ubicaciones por modelo con columna 'k' (type_k)
            rows_y = []
            for modelo, sol in [('A1', sol_A1), ('A2', sol_A2), ('A3', sol_A3)]:
                for (j, k), v in sol['ubicaciones_y'].items():
                    rows_y.append({'modelo': modelo, 'j': j, 'k': k, 'y': v})
            pd.DataFrame(rows_y).to_excel(writer, sheet_name=f'{label}_y', index=False)

            # {label}_x — asignación con kg y q_i
            rows_x = []
            for modelo, sol in [('A1', sol_A1), ('A2', sol_A2), ('A3', sol_A3)]:
                for (i, j), v in sol.get('x_vals', {}).items():
                    if v > 0.001:
                        rows_x.append({
                            'modelo': modelo, 'i': i, 'j': j,
                            'x': round(v, 4),
                            'q_i': round(q_esc.get(i, 0), 2),
                            'kg_assigned': round(q_esc.get(i, 0) * v, 4),
                        })
            pd.DataFrame(rows_x).to_excel(writer, sheet_name=f'{label}_x', index=False)

            # {label}_q
            pd.DataFrame([{'i': i, 'q': q} for i, q in q_esc.items()]).to_excel(
                writer, sheet_name=f'{label}_q', index=False)

            # {label}_occ_A3 — ocupación bins A3
            df_occ_A3 = build_occ_df(
                sol_A3['ubicaciones_y'], sol_A3.get('x_vals', {}),
                sol_A3.get('z_vals', {}), q_esc, d, J, K)
            df_occ_A3.to_excel(writer, sheet_name=f'{label}_occ_A3', index=False)

            # {label}_occ_A1D — ocupación cuando bins de A1 se evalúan bajo A3
            df_occ_A1D = build_occ_df(
                sol_A1['ubicaciones_y'], eval_A1D.get('x_vals', {}),
                eval_A1D.get('z_vals', {}), q_esc, d, J, K)
            df_occ_A1D.to_excel(writer, sheet_name=f'{label}_occ_A1D', index=False)

            # {label}_occ_A2D
            df_occ_A2D = build_occ_df(
                sol_A2['ubicaciones_y'], eval_A2D.get('x_vals', {}),
                eval_A2D.get('z_vals', {}), q_esc, d, J, K)
            df_occ_A2D.to_excel(writer, sheet_name=f'{label}_occ_A2D', index=False)

            # {label}_costs — desglose completo de costos
            overflow_A3 = sol_A3.get('overflow', 0.0)
            pd.DataFrame([{
                'scenario'              : label,
                'factor_anual'          : round(s['factor_anual'], 4),
                'obj_A1'                : round(sol_A1['objective'], 4),
                'obj_A2'                : round(sol_A2['objective'], 4),
                'obj_A3'                : round(sol_A3['objective'], 4),
                'cost_A1D_real'         : round(eval_A1D['objective'], 4),
                'cost_A2D_real'         : round(eval_A2D['objective'], 4),
                'overflow_A1D_kg_week'  : round(eval_A1D['overflow'], 4),
                'overflow_A2D_kg_week'  : round(eval_A2D['overflow'], 4),
                'overflow_A3_kg_week'   : round(overflow_A3, 4),
                'overflow_A1D_tpa'      : round(eval_A1D['overflow'] * SEMANAS / KG_TON, 4),
                'overflow_A2D_tpa'      : round(eval_A2D['overflow'] * SEMANAS / KG_TON, 4),
                'overflow_A3_tpa'       : round(overflow_A3 * SEMANAS / KG_TON, 4),
                'hidden_cost_A1D_week'  : round(s['hidden_A1'], 4),
                'hidden_cost_A2D_week'  : round(s['hidden_A2'], 4),
                'hidden_cost_A1D_annual': round(s['hidden_A1'] * SEMANAS, 2),
                'hidden_cost_A2D_annual': round(s['hidden_A2'] * SEMANAS, 2),
                'bins_A1'               : sol_A1['bins_abiertos'],
                'bins_A2'               : sol_A2['bins_abiertos'],
                'bins_A3'               : sol_A3['bins_abiertos'],
            }]).to_excel(writer, sheet_name=f'{label}_costs', index=False)

    print(f"✓ sensitivity_demand_solutions.xlsx guardado (hojas enriquecidas)")

    # =========================================================================
    # MAPAS PDF — estilo unificado
    # =========================================================================
    plt.rcParams.update({'font.family': 'serif', 'font.size': 11})
    with PdfPages('sensitivity_demand_maps.pdf') as pdf_maps:
        for mult in MULTS_MAPA:
            if mult not in soluciones_todas:
                continue
            s     = soluciones_todas[mult]
            label = ("baseline" if abs(mult - 1.0) < 0.01
                     else "low demand" if mult < 1.0 else "high demand")
            try:
                fig_mapa = generar_mapa_fig(
                    s['sol_A1'], s['sol_A2'], s['sol_A3'],
                    s['eval_A1D'], s['eval_A2D'],
                    df_candidatos, df_demandas, s['q_esc'],
                    mult, label, phi, r, I, d, K)
                if fig_mapa is not None:
                    pdf_maps.savefig(fig_mapa, dpi=200, bbox_inches='tight')
                    plt.close(fig_mapa)
                    print(f"  → Mapa '{label}' agregado")
            except Exception as e:
                print(f"  ⚠ Error mapa '{label}': {e}")
    print(f"✓ sensitivity_demand_maps.pdf guardado")

    # =========================================================================
    # FIGURAS ANALÍTICAS
    # =========================================================================
    plt.rcParams.update({
        'axes.grid': True, 'grid.linestyle': '--', 'grid.alpha': 0.5,
    })
    COLOR_A1D = '#1f77b4'; COLOR_A2D = '#d62728'; COLOR_A3 = '#2ca02c'
    x_axis   = df['factor_anual']
    x_label  = r'Annual glass generation rate, $g_i$ (kg per household per year)'
    vline_kw = dict(color='gray', linestyle=':', linewidth=1.5)

    with PdfPages('sensitivity_demand.pdf') as pdf:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x_axis, df['overflow_A1D_tpa'], 'o-', color=COLOR_A1D,
                linewidth=2, markersize=6, label='SL-RBLP-A1-D')
        ax.plot(x_axis, df['overflow_A2D_tpa'], 's-', color=COLOR_A2D,
                linewidth=2, markersize=6, label='SL-RBLP-A2-D')
        ax.plot(x_axis, df['overflow_A3_tpa'],  '^-', color=COLOR_A3,
                linewidth=2, markersize=6, label='SL-RBLP')
        ax.axvline(FACTOR_BASELINE_ANUAL, **vline_kw,
                   label=f'Baseline ({FACTOR_BASELINE_ANUAL} kg/hh/year)')
        ax.set_xlabel(x_label); ax.set_ylabel('Annual overflow (tons/year)')
        ax.legend(fontsize=10); fig.tight_layout()
        pdf.savefig(fig, dpi=300, bbox_inches='tight'); plt.close(fig)
        print("✓ Figura 1: overflow")

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x_axis, df['hc_A1D_anual'], 'o-', color=COLOR_A1D,
                linewidth=2, markersize=6, label='SL-RBLP-A1-D')
        ax.plot(x_axis, df['hc_A2D_anual'], 's-', color=COLOR_A2D,
                linewidth=2, markersize=6, label='SL-RBLP-A2-D')
        ax.axvline(FACTOR_BASELINE_ANUAL, **vline_kw,
                   label=f'Baseline ({FACTOR_BASELINE_ANUAL} kg/hh/year)')
        ax.set_xlabel(x_label); ax.set_ylabel('Annual hidden cost (USD/year)')
        ax.legend(fontsize=10); fig.tight_layout()
        pdf.savefig(fig, dpi=300, bbox_inches='tight'); plt.close(fig)
        print("✓ Figura 2: hidden cost")

        tipo_colors = {1: '#4e79a7', 2: '#f28e2b', 3: '#59a14f'}
        tipo_labels = {1: 'Type 1 (600 kg)', 2: 'Type 2 (900 kg)', 3: 'Type 3 (1,200 kg)'}
        x_ticks = df_types['factor_anual'].values
        x_idx   = np.arange(len(x_ticks))
        fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
        for ax_i, (modelo, lbl) in enumerate(
                [('A1', 'SL-RBLP-A1'), ('A2', 'SL-RBLP-A2'), ('A3', 'SL-RBLP')]):
            ax = axes[ax_i]
            bottom = np.zeros(len(x_ticks))
            for k in K:
                vals = df_types[f'{modelo}_tipo{k}'].values.astype(float)
                ax.bar(x_idx, vals, 0.55, bottom=bottom,
                       color=tipo_colors[k], label=tipo_labels[k])
                bottom += vals
            ax.set_xticks(x_idx)
            ax.set_xticklabels([f'{v:.1f}' for v in x_ticks],
                               rotation=45, ha='right', fontsize=9)
            ax.set_xlabel(x_label, fontsize=9); ax.set_title(lbl, fontsize=11)
            bl_idx = (list(x_ticks).index(FACTOR_BASELINE_ANUAL)
                      if FACTOR_BASELINE_ANUAL in x_ticks else None)
            if bl_idx is not None:
                ax.axvline(bl_idx, **vline_kw)
            if ax_i == 0: ax.set_ylabel('Number of bins')
            if ax_i == 2: ax.legend(fontsize=9, loc='upper left')
        fig.tight_layout()
        pdf.savefig(fig, dpi=300, bbox_inches='tight'); plt.close(fig)
        print("✓ Figura 3: bins por tipo")

    print(f"✓ sensitivity_demand.pdf guardado (3 figuras)")

    # =========================================================================
    # RESUMEN CONSOLA
    # =========================================================================
    print("\n" + "=" * 85)
    print(f"{'g_i(ann)':>9} {'×':>5} | "
          f"{'OF A1-D':>9} {'OF A2-D':>9} {'OF A3':>9} | "
          f"{'HC A1-D':>10} {'HC A2-D':>10} | A3 tipos")
    print("-" * 85)
    for _, row in df.iterrows():
        marca = " ←" if abs(row['multiplicador'] - 1.0) < 0.01 else ""
        ridx  = list(df['multiplicador']).index(row['multiplicador'])
        tipos = df_types.iloc[ridx]
        tipos_str = '  '.join(f"T{k}:{int(tipos[f'A3_tipo{k}'])}" for k in K)
        print(f"  {row['factor_anual']:>7.2f}  ×{row['multiplicador']:.2f} | "
              f"{row['overflow_A1D_tpa']:>9.2f} {row['overflow_A2D_tpa']:>9.2f} "
              f"{row['overflow_A3_tpa']:>9.2f} | "
              f"${row['hc_A1D_anual']:>9,.0f} ${row['hc_A2D_anual']:>9,.0f} | "
              f"{tipos_str}{marca}")
    print("=" * 85)

    return df, df_types


if __name__ == "__main__":
    df_results, df_types = main()