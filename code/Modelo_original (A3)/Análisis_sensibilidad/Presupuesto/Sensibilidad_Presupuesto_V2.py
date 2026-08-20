# -*- coding: utf-8 -*-
"""
ANÁLISIS DE SENSIBILIDAD - VERSIÓN v5 (V2 del script principal)
Cambios respecto a v4:
  1) Retorna variables x[i,j] y z[j] de TODOS los solvers y evaluaciones
  2) Hoja "Locations"        → sitios abiertos por modelo y nivel de presupuesto
  3) Hoja "Demand_Assignment"→ asignación completa i→j por modelo (base para GIF consola)
  4) Hoja "Bin_Occupancy"    → demanda asignada, capacidad y % ocupación por bin abierto
  5) Hoja "Results_AD"       → costos y overflow de A1-D y A2-D con el mismo detalle que Results
  6) Resumen de consola expandido: demanda asignada total por modelo por escenario
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages
import Instancia

# =============================================================================
# PARÁMETROS DE CONVERSIÓN
# =============================================================================
VIDA_UTIL   = 260   # semanas (5 años)
SEMANAS     = 52
KG_TON      = 1000

BUDGET_BASELINE_SEMANAL = 5616 / 260   # ≈ 21.6 USD/semana
BUDGET_BASELINE_TOTAL   = 5616         # USD (para línea vertical en gráfico)

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _bins_por_tipo(ubicaciones_y, K):
    """Cuenta contenedores instalados por tipo k."""
    return {k: sum(1 for (j, kk) in ubicaciones_y if kk == k) for k in K}


def _registrar_locations(budget, model_name, ubicaciones_y):
    """
    Devuelve lista de dicts para la hoja Locations.
    Columnas: budget, model, site_j, type_k
    """
    rows = []
    for (j, k), val in ubicaciones_y.items():
        if val > 0.5:
            rows.append({'budget': budget, 'model': model_name,
                         'site_j': j, 'type_k': k})
    return rows


def _registrar_demand(budget, model_name, x_vals, I, J):
    """
    Devuelve lista de dicts para la hoja Demand_Assignment.
    Solo guarda pares (i, j) con asignación > 0.001 para no inflar el Excel.
    Columnas: budget, model, demand_i, site_j, assignment
    """
    rows = []
    for i in I:
        for j in J:
            val = x_vals.get((i, j), 0.0)
            if val > 0.001:
                rows.append({'budget': budget, 'model': model_name,
                             'demand_i': i, 'site_j': j, 'assignment': round(val, 6)})
    return rows


def _registrar_occupancy(budget, model_name, ubicaciones_y, x_vals, z_vals,
                         I, J, K, d, q):
    """
    Devuelve lista de dicts para la hoja Bin_Occupancy.
    Columnas: budget, model, site_j, type_k, capacity_kg,
              assigned_demand_kg, overflow_kg, occupancy_pct
    """
    rows = []
    for (j, k), yval in ubicaciones_y.items():
        if yval < 0.5:
            continue
        capacity   = d.get((j, k), 0)
        assigned   = sum(q[i] * x_vals.get((i, j), 0.0) for i in I)
        overflow   = z_vals.get(j, 0.0)
        net_stored = assigned - overflow          # lo que realmente quedó en el bin
        occ_pct    = (net_stored / capacity * 100) if capacity > 0 else 0.0
        rows.append({
            'budget'           : budget,
            'model'            : model_name,
            'site_j'           : j,
            'type_k'           : k,
            'capacity_kg'      : round(capacity, 4),
            'assigned_demand_kg': round(assigned, 4),
            'overflow_kg'      : round(overflow, 4),
            'net_stored_kg'    : round(net_stored, 4),
            'occupancy_pct'    : round(occ_pct, 2),
        })
    return rows


# =============================================================================
# FUNCIONES DE RESOLUCIÓN  (ahora retornan x_vals y z_vals también)
# =============================================================================

def resolver_A1(presupuesto, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    m = gp.Model('A1')
    m.setParam("OutputFlag", 1)

    x = m.addVars(I, J, vtype=GRB.BINARY)
    y = m.addVars(J, K, vtype=GRB.BINARY)
    w = m.addVars(I, J, vtype=GRB.BINARY)

    costo_NR = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(w[i,j] for j in J)) for i in I)
    m.setObjective(costo_NR, GRB.MINIMIZE)

    Ji = {i: [j for j in J if r[i] > phi[i,j]] for i in I}
    m.addConstr(gp.quicksum(y[j,k] * f[j,k] for j in J for k in K) <= presupuesto)

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

    m.setParam(GRB.Param.TimeLimit, 2500)
    m.setParam(GRB.Param.Cuts, 0)
    m.setParam(GRB.Param.Seed, 123)
    m.optimize()

    if m.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL] or m.SolCount == 0:
        return None
    if m.status in [GRB.TIME_LIMIT, GRB.SUBOPTIMAL] and m.MIPGap * 100 >= 2.0:
        return None

    ub_y   = {(j,k): y[j,k].x for j in J for k in K if y[j,k].x > 0.5}
    x_vals = {(i,j): x[i,j].x for i in I for j in J if x[i,j].x > 0.001}
    # A1 no tiene z; overflow se calcula en evaluar_en_A3 → z_vals vacío aquí
    return {
        'objective'    : m.ObjVal,
        'ubicaciones_y': ub_y,
        'bins_abiertos': len(ub_y),
        'bins_por_tipo': _bins_por_tipo(ub_y, K),
        'recycled'     : sum(q[i] * sum(x[i,j].x for j in J) for i in I),
        'x_vals'       : x_vals,
        'z_vals'       : {},   # A1 no modela overflow
    }


def resolver_A2(presupuesto, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    m = gp.Model('A2')
    m.setParam("OutputFlag", 1)

    x = m.addVars(I, J, vtype=GRB.BINARY)
    y = m.addVars(J, K, vtype=GRB.BINARY)
    w = m.addVars(I, J, vtype=GRB.CONTINUOUS, lb=0, ub=1)

    costo_NR = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(w[i,j] for j in J)) for i in I)
    m.setObjective(costo_NR, GRB.MINIMIZE)

    Ji = {i: [j for j in J if r[i] > phi[i,j]] for i in I}
    m.addConstr(gp.quicksum(y[j,k] * f[j,k] for j in J for k in K) <= presupuesto)

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

    m.setParam(GRB.Param.TimeLimit, 2500)
    m.setParam(GRB.Param.Cuts, 0)
    m.setParam(GRB.Param.Seed, 123)
    m.optimize()

    if m.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL] or m.SolCount == 0:
        return None
    if m.status in [GRB.TIME_LIMIT, GRB.SUBOPTIMAL] and m.MIPGap * 100 >= 2.0:
        return None

    ub_y   = {(j,k): y[j,k].x for j in J for k in K if y[j,k].x > 0.5}
    x_vals = {(i,j): x[i,j].x for i in I for j in J if x[i,j].x > 0.001}
    return {
        'objective'    : m.ObjVal,
        'ubicaciones_y': ub_y,
        'bins_abiertos': len(ub_y),
        'bins_por_tipo': _bins_por_tipo(ub_y, K),
        'recycled'     : sum(q[i] * sum(x[i,j].x for j in J) for i in I),
        'x_vals'       : x_vals,
        'z_vals'       : {},   # A2 no modela overflow
    }


def resolver_A3(presupuesto, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    m = gp.Model('A3')
    m.setParam("OutputFlag", 1)

    x = m.addVars(I, J, vtype=GRB.BINARY)
    y = m.addVars(J, K, vtype=GRB.BINARY)
    z = m.addVars(J, vtype=GRB.CONTINUOUS, lb=0)

    costo_dump = gp.quicksum(z[j] * c_dump[j] for j in J)
    costo_NR   = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(x[i,j] for j in J)) for i in I)
    m.setObjective(costo_dump + costo_NR, GRB.MINIMIZE)

    Ji = {i: [j for j in J if r[i] > phi[i,j]] for i in I}
    m.addConstr(gp.quicksum(y[j,k] * f[j,k] for j in J for k in K) <= presupuesto)

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

    m.setParam(GRB.Param.TimeLimit, 2500)
    m.setParam(GRB.Param.Cuts, 0)
    m.setParam(GRB.Param.Seed, 123)
    m.optimize()

    if m.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL] or m.SolCount == 0:
        return None
    if m.status in [GRB.TIME_LIMIT, GRB.SUBOPTIMAL] and m.MIPGap * 100 >= 2.0:
        return None

    ub_y         = {(j,k): y[j,k].x for j in J for k in K if y[j,k].x > 0.5}
    x_vals       = {(i,j): x[i,j].x for i in I for j in J if x[i,j].x > 0.001}
    z_vals       = {j: z[j].x for j in J if z[j].x > 0.001}
    overflow_total = sum(z[j].x for j in J)
    return {
        'objective'    : m.ObjVal,
        'ubicaciones_y': ub_y,
        'bins_abiertos': len(ub_y),
        'bins_por_tipo': _bins_por_tipo(ub_y, K),
        'recycled'     : sum(q[i] * sum(x[i,j].x for j in J) for i in I) - overflow_total,
        'overflow'     : overflow_total,
        'x_vals'       : x_vals,
        'z_vals'       : z_vals,
    }


def evaluar_en_A3(ubicaciones_y, presupuesto, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    """
    Evalúa solución fija bajo lógica A3 (overflow explícito).
    Retorna: (obj, overflow_total, recycled, x_vals, z_vals)
    """
    m = gp.Model('Eval_A3')
    m.setParam("OutputFlag", 1)

    x = m.addVars(I, J, vtype=GRB.BINARY)
    y = m.addVars(J, K, vtype=GRB.BINARY)
    z = m.addVars(J, vtype=GRB.CONTINUOUS, lb=0)

    costo_dump = gp.quicksum(z[j] * c_dump[j] for j in J)
    costo_NR   = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(x[i,j] for j in J)) for i in I)
    m.setObjective(costo_dump + costo_NR, GRB.MINIMIZE)

    # Fijar ubicaciones
    for j in J:
        for k in K:
            y[j,k].LB = ubicaciones_y.get((j,k), 0)
            y[j,k].UB = ubicaciones_y.get((j,k), 0)

    Ji = {i: [j for j in J if r[i] > phi[i,j]] for i in I}
    m.addConstr(gp.quicksum(y[j,k] * f[j,k] for j in J for k in K) <= presupuesto)

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

    m.setParam(GRB.Param.TimeLimit, 2500)
    m.setParam(GRB.Param.Cuts, 0)
    m.setParam(GRB.Param.Seed, 123)
    m.optimize()

    if m.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL] or m.SolCount == 0:
        return None, None, None, {}, {}

    overflow_total = sum(z[j].x for j in J)
    recycled       = sum(q[i] * sum(x[i,j].x for j in J) for i in I) - overflow_total
    x_vals         = {(i,j): x[i,j].x for i in I for j in J if x[i,j].x > 0.001}
    z_vals         = {j: z[j].x for j in J if z[j].x > 0.001}
    return m.ObjVal, overflow_total, recycled, x_vals, z_vals


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("=" * 70)
    print("BUDGET SENSITIVITY ANALYSIS v5")
    print("=" * 70)

    I = Instancia.I
    J = Instancia.J
    K = Instancia.K
    d = Instancia.d
    phi = Instancia.phi
    q = Instancia.q
    r = Instancia.r
    f = Instancia.f
    c_dump = Instancia.c_dump
    c_nr   = Instancia.c_nr
    print(f"✓ Instancia: {len(I)} demandas, {len(J)} candidatos, {len(K)} tipos")

    budget_values = [19.8, 20.4, 21.0, 21.6,
                     22.9, 24.2, 25.5, 26.8, 28.1, 29.4, 30.7, 32.0]
    print(f"✓ Presupuestos (USD/sem): {budget_values}")
    print(f"  → Baseline = {BUDGET_BASELINE_SEMANAL:.4f} USD/sem  ({BUDGET_BASELINE_TOTAL} USD total)")

    # =========================================================================
    # UBICACIONES HARDCODEADAS PARA EL ESCENARIO BASELINE (B = 21.6 USD/sem)
    # =========================================================================
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
    OBJ_A1_BASELINE  = 872.99
    OBJ_A2_BASELINE  = 872.85
    OBJ_A3_BASELINE  = 885.89
    OVF_A3_BASELINE  = 183.66   # kg/semana

    # =========================================================================
    # ESTRUCTURAS DE RESULTADOS
    # =========================================================================
    results = {
        'budget': [],
        'cost_binary_reported': [], 'bins_binary': [],
        'cost_binary_real': [], 'overflow_binary_real': [], 'hidden_cost_binary': [],
        'cost_fractional_reported': [], 'bins_fractional': [],
        'cost_fractional_real': [], 'overflow_fractional_real': [], 'hidden_cost_fractional': [],
        'cost_slrblp': [], 'bins_slrblp': [], 'overflow_slrblp': [],
        # Demanda total asignada (kg/sem) por modelo
        'demand_assigned_a1': [], 'demand_assigned_a1d': [],
        'demand_assigned_a2': [], 'demand_assigned_a2d': [],
        'demand_assigned_a3': [],
    }

    types_results = {'budget': []}
    for modelo in ['A1', 'A2', 'A3']:
        for k in K:
            types_results[f'{modelo}_tipo{k}'] = []

    # Listas acumuladas para hojas adicionales
    all_locations   = []   # → hoja Locations
    all_demand_asgn = []   # → hoja Demand_Assignment
    all_occupancy   = []   # → hoja Bin_Occupancy

    # =========================================================================
    # LOOP PRINCIPAL
    # =========================================================================
    for idx, B in enumerate(budget_values, 1):
        B_total = round(B * VIDA_UTIL)
        ES_BASELINE = abs(B - BUDGET_BASELINE_SEMANAL) < 0.01
        print(f"\n[{idx}/{len(budget_values)}] Budget: {B:.4f} USD/sem  ({B_total} USD total)"
              + ("  ← BASELINE (hardcoded)" if ES_BASELINE else ""))

        # ------------------------------------------------------------------
        # RESOLUCIÓN / HARDCODE BASELINE
        # ------------------------------------------------------------------
        if ES_BASELINE:
            sol_A1 = {'objective': OBJ_A1_BASELINE, 'ubicaciones_y': UBICACIONES_A1_BASELINE,
                      'bins_abiertos': len(UBICACIONES_A1_BASELINE),
                      'bins_por_tipo': _bins_por_tipo(UBICACIONES_A1_BASELINE, K),
                      'x_vals': {}, 'z_vals': {}}
            sol_A2 = {'objective': OBJ_A2_BASELINE, 'ubicaciones_y': UBICACIONES_A2_BASELINE,
                      'bins_abiertos': len(UBICACIONES_A2_BASELINE),
                      'bins_por_tipo': _bins_por_tipo(UBICACIONES_A2_BASELINE, K),
                      'x_vals': {}, 'z_vals': {}}
            sol_A3 = {'objective': OBJ_A3_BASELINE, 'ubicaciones_y': UBICACIONES_A3_BASELINE,
                      'bins_abiertos': len(UBICACIONES_A3_BASELINE),
                      'bins_por_tipo': _bins_por_tipo(UBICACIONES_A3_BASELINE, K),
                      'overflow': OVF_A3_BASELINE,
                      'x_vals': {}, 'z_vals': {}}
            print(f"  A1 → hardcoded  tipos: {sol_A1['bins_por_tipo']}")
            print(f"  A2 → hardcoded  tipos: {sol_A2['bins_por_tipo']}")
            print(f"  A3 → hardcoded  overflow: {sol_A3['overflow']:.2f} kg")

            # Para el baseline, necesitamos correr evaluar_en_A3 igual
            # (x_vals del baseline se obtienen de la evaluación A3 que viene abajo)
        else:
            sol_A1 = resolver_A1(B, I, J, K, d, phi, q, r, f, c_dump, c_nr)
            if sol_A1 is None:
                print("  ❌ A1 falló, saltando."); continue
            print(f"  A1  → Bins: {sol_A1['bins_abiertos']}  tipos: {sol_A1['bins_por_tipo']}")

            sol_A2 = resolver_A2(B, I, J, K, d, phi, q, r, f, c_dump, c_nr)
            if sol_A2 is None:
                print("  ❌ A2 falló, saltando."); continue
            print(f"  A2  → Bins: {sol_A2['bins_abiertos']}  tipos: {sol_A2['bins_por_tipo']}")

            sol_A3 = resolver_A3(B, I, J, K, d, phi, q, r, f, c_dump, c_nr)
            if sol_A3 is None:
                print("  ❌ A3 falló, saltando."); continue
            print(f"  A3  → Bins: {sol_A3['bins_abiertos']}  overflow: {sol_A3['overflow']:.2f} kg  tipos: {sol_A3['bins_por_tipo']}")

        # ------------------------------------------------------------------
        # EVALUACIONES A1-D y A2-D
        # ------------------------------------------------------------------
        cost_A1_real, overflow_A1_real, _, x_vals_a1d, z_vals_a1d = evaluar_en_A3(
            sol_A1['ubicaciones_y'], B, I, J, K, d, phi, q, r, f, c_dump, c_nr)
        if cost_A1_real is None:
            print("  ❌ Evaluación A1-D falló, saltando."); continue
        hidden_A1 = cost_A1_real - sol_A1['objective']
        print(f"  A1-D → overflow: {overflow_A1_real:.2f} kg  hidden cost: {hidden_A1:.2f} USD")

        cost_A2_real, overflow_A2_real, _, x_vals_a2d, z_vals_a2d = evaluar_en_A3(
            sol_A2['ubicaciones_y'], B, I, J, K, d, phi, q, r, f, c_dump, c_nr)
        if cost_A2_real is None:
            print("  ❌ Evaluación A2-D falló, saltando."); continue
        hidden_A2 = cost_A2_real - sol_A2['objective']
        print(f"  A2-D → overflow: {overflow_A2_real:.2f} kg  hidden cost: {hidden_A2:.2f} USD")

        # Para baseline: recuperar x_vals de A3 también via evaluación
        if ES_BASELINE:
            _, _, _, x_vals_a3_eval, z_vals_a3_eval = evaluar_en_A3(
                sol_A3['ubicaciones_y'], B, I, J, K, d, phi, q, r, f, c_dump, c_nr)
            sol_A3['x_vals'] = x_vals_a3_eval
            sol_A3['z_vals'] = z_vals_a3_eval
            # A1/A2 propios también necesitan x_vals → ya están en a1d/a2d con mismas ubicaciones
            sol_A1['x_vals'] = x_vals_a1d
            sol_A2['x_vals'] = x_vals_a2d

        # ------------------------------------------------------------------
        # DEMANDA ASIGNADA TOTAL (kg/sem)
        # ------------------------------------------------------------------
        dem_a1  = sum(q[i] * v for (i,j), v in sol_A1['x_vals'].items())
        dem_a1d = sum(q[i] * v for (i,j), v in x_vals_a1d.items())
        dem_a2  = sum(q[i] * v for (i,j), v in sol_A2['x_vals'].items())
        dem_a2d = sum(q[i] * v for (i,j), v in x_vals_a2d.items())
        dem_a3  = sum(q[i] * v for (i,j), v in sol_A3['x_vals'].items())

        # ------------------------------------------------------------------
        # ACUMULAR EN ESTRUCTURAS
        # ------------------------------------------------------------------
        # Results principal
        results['budget'].append(B)
        results['cost_binary_reported'].append(sol_A1['objective'])
        results['bins_binary'].append(sol_A1['bins_abiertos'])
        results['cost_binary_real'].append(cost_A1_real)
        results['overflow_binary_real'].append(overflow_A1_real)
        results['hidden_cost_binary'].append(hidden_A1)
        results['cost_fractional_reported'].append(sol_A2['objective'])
        results['bins_fractional'].append(sol_A2['bins_abiertos'])
        results['cost_fractional_real'].append(cost_A2_real)
        results['overflow_fractional_real'].append(overflow_A2_real)
        results['hidden_cost_fractional'].append(hidden_A2)
        results['cost_slrblp'].append(sol_A3['objective'])
        results['bins_slrblp'].append(sol_A3['bins_abiertos'])
        results['overflow_slrblp'].append(sol_A3['overflow'])
        results['demand_assigned_a1'].append(round(dem_a1, 4))
        results['demand_assigned_a1d'].append(round(dem_a1d, 4))
        results['demand_assigned_a2'].append(round(dem_a2, 4))
        results['demand_assigned_a2d'].append(round(dem_a2d, 4))
        results['demand_assigned_a3'].append(round(dem_a3, 4))

        # Tipos de contenedor
        types_results['budget'].append(B)
        for k in K:
            types_results[f'A1_tipo{k}'].append(sol_A1['bins_por_tipo'].get(k, 0))
            types_results[f'A2_tipo{k}'].append(sol_A2['bins_por_tipo'].get(k, 0))
            types_results[f'A3_tipo{k}'].append(sol_A3['bins_por_tipo'].get(k, 0))

        # Locations (sitios abiertos)
        all_locations += _registrar_locations(B, 'A1',   sol_A1['ubicaciones_y'])
        all_locations += _registrar_locations(B, 'A1-D', sol_A1['ubicaciones_y'])   # mismas ubicaciones
        all_locations += _registrar_locations(B, 'A2',   sol_A2['ubicaciones_y'])
        all_locations += _registrar_locations(B, 'A2-D', sol_A2['ubicaciones_y'])
        all_locations += _registrar_locations(B, 'A3',   sol_A3['ubicaciones_y'])

        # Demand Assignment
        all_demand_asgn += _registrar_demand(B, 'A1',   sol_A1['x_vals'], I, J)
        all_demand_asgn += _registrar_demand(B, 'A1-D', x_vals_a1d,       I, J)
        all_demand_asgn += _registrar_demand(B, 'A2',   sol_A2['x_vals'], I, J)
        all_demand_asgn += _registrar_demand(B, 'A2-D', x_vals_a2d,       I, J)
        all_demand_asgn += _registrar_demand(B, 'A3',   sol_A3['x_vals'], I, J)

        # Bin Occupancy
        all_occupancy += _registrar_occupancy(B, 'A1',   sol_A1['ubicaciones_y'], sol_A1['x_vals'], {},           I, J, K, d, q)
        all_occupancy += _registrar_occupancy(B, 'A1-D', sol_A1['ubicaciones_y'], x_vals_a1d,       z_vals_a1d,   I, J, K, d, q)
        all_occupancy += _registrar_occupancy(B, 'A2',   sol_A2['ubicaciones_y'], sol_A2['x_vals'], {},           I, J, K, d, q)
        all_occupancy += _registrar_occupancy(B, 'A2-D', sol_A2['ubicaciones_y'], x_vals_a2d,       z_vals_a2d,   I, J, K, d, q)
        all_occupancy += _registrar_occupancy(B, 'A3',   sol_A3['ubicaciones_y'], sol_A3['x_vals'], sol_A3['z_vals'], I, J, K, d, q)

    # =========================================================================
    # DataFrames y conversiones
    # =========================================================================
    df       = pd.DataFrame(results)
    df_types = pd.DataFrame(types_results)
    df_loc   = pd.DataFrame(all_locations)
    df_dem   = pd.DataFrame(all_demand_asgn)
    df_occ   = pd.DataFrame(all_occupancy)

    df['budget_total']        = df['budget'] * VIDA_UTIL
    df['overflow_a1d_tpa']    = df['overflow_binary_real']     * SEMANAS / KG_TON
    df['overflow_a2d_tpa']    = df['overflow_fractional_real'] * SEMANAS / KG_TON
    df['overflow_slrblp_tpa'] = df['overflow_slrblp']          * SEMANAS / KG_TON
    df['hc_binary_anual']     = df['hidden_cost_binary']        * SEMANAS
    df['hc_fractional_anual'] = df['hidden_cost_fractional']    * SEMANAS

    df_types['budget_total'] = df_types['budget'] * VIDA_UTIL

    # =========================================================================
    # EXCEL (5 hojas)
    # =========================================================================
    excel_file = 'sensitivity_budget_v2.xlsx'
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        df.to_excel(writer,       sheet_name='Results',           index=False)
        df_types.to_excel(writer, sheet_name='Container_Types',   index=False)
        df_loc.to_excel(writer,   sheet_name='Locations',         index=False)
        df_dem.to_excel(writer,   sheet_name='Demand_Assignment', index=False)
        df_occ.to_excel(writer,   sheet_name='Bin_Occupancy',     index=False)

    print(f"\n✓ Excel guardado: {excel_file}")
    print(f"  → Hojas: Results | Container_Types | Locations | Demand_Assignment | Bin_Occupancy")
    print(f"  → Filas aprox:  Locations={len(df_loc)}  Demand_Assignment={len(df_dem)}  Bin_Occupancy={len(df_occ)}")

    # =========================================================================
    # FIGURA 1: Overflow comparison
    # =========================================================================
    plt.rcParams.update({
        'font.family'  : 'serif',
        'font.size'    : 11,
        'axes.grid'    : True,
        'grid.linestyle': '--',
        'grid.alpha'   : 0.5,
    })

    COLOR_BINARY     = '#1f77b4'
    COLOR_FRACTIONAL = '#d62728'
    COLOR_SLRBLP     = '#2ca02c'

    pdf_file = 'sensitivity_budget_v2.pdf'
    with PdfPages(pdf_file) as pdf:
        fig, ax = plt.subplots(figsize=(10, 6))
        x = df['budget_total']
        ax.plot(x, df['overflow_a1d_tpa'],    'o-', color=COLOR_BINARY,
                linewidth=2, markersize=6, label='SL-RBLP-A1-D')
        ax.plot(x, df['overflow_a2d_tpa'],    's-', color=COLOR_FRACTIONAL,
                linewidth=2, markersize=6, label='SL-RBLP-A2-D')
        ax.plot(x, df['overflow_slrblp_tpa'], '^-', color=COLOR_SLRBLP,
                linewidth=2, markersize=6, label='SL-RBLP')
        ax.axvline(BUDGET_BASELINE_TOTAL, color='gray', linestyle=':', linewidth=1.5,
                   label=f'Baseline (USD {BUDGET_BASELINE_TOTAL:,})')
        ax.set_xlabel('Total Budget (USD)')
        ax.set_ylabel('Annual Overflow (tons/year)')
        ax.set_title('Overflow Comparison by Budget Level')
        ax.legend()
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'${v:,.0f}'))
        fig.tight_layout()
        pdf.savefig(fig, dpi=300, bbox_inches='tight')
        plt.close(fig)

    print(f"✓ PDF guardado: {pdf_file}")

    # =========================================================================
    # RESUMEN EN CONSOLA (expandido)
    # =========================================================================
    print("\n" + "=" * 100)
    print(f"{'Budget':>12} | {'Bins':>5} | {'Ovf A3 (t/a)':>12} | "
          f"{'Red A1-D':>8} | {'Red A2-D':>8} | "
          f"{'Dem A1 (kg)':>11} | {'Dem A2 (kg)':>11} | {'Dem A3 (kg)':>11}")
    print("-" * 100)
    for _, row in df.iterrows():
        red_a1 = ((row['overflow_a1d_tpa'] - row['overflow_slrblp_tpa']) /
                  row['overflow_a1d_tpa'] * 100) if row['overflow_a1d_tpa'] > 0 else 0
        red_a2 = ((row['overflow_a2d_tpa'] - row['overflow_slrblp_tpa']) /
                  row['overflow_a2d_tpa'] * 100) if row['overflow_a2d_tpa'] > 0 else 0
        marca = " ← baseline" if abs(row['budget'] - BUDGET_BASELINE_SEMANAL) < 0.01 else ""
        print(f"  ${row['budget_total']:>9,.0f} | {int(row['bins_slrblp']):>5} | "
              f"{row['overflow_slrblp_tpa']:>12.1f} | "
              f"{red_a1:>7.1f}% | {red_a2:>7.1f}% | "
              f"{row['demand_assigned_a1']:>11.1f} | "
              f"{row['demand_assigned_a2']:>11.1f} | "
              f"{row['demand_assigned_a3']:>11.1f}{marca}")
    print("=" * 100)

    return df, df_types, df_loc, df_dem, df_occ


if __name__ == "__main__":
    df_results, df_types, df_loc, df_dem, df_occ = main()
