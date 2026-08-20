# -*- coding: utf-8 -*-
"""
ANÁLISIS DE SENSIBILIDAD - COSTO DE OVERFLOW (c_o)  [VERSIÓN CORREGIDA]
Varía el parámetro c_dump (USD/kg de overflow) manteniendo todo lo demás fijo.
Baseline: c_dump = (177 * 1.10) / 1000 = 0.1947 USD/kg

CORRECCIÓN: A1 y A2 se resuelven UNA SOLA VEZ con el c_dump baseline.
Sus ubicaciones quedan FIJAS para todos los escenarios, garantizando que
la evaluación en ×1.00 reproduzca exactamente los resultados del baseline.

Outputs:
  1) sensitivity_overflow_cost.xlsx  → hojas Results, Container_Types
  2) sensitivity_overflow_cost.pdf   → Figura overflow + figura hidden cost + figura bin types
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import Instancia

# =============================================================================
# PARÁMETROS DE CONVERSIÓN Y BASELINE
# =============================================================================
VIDA_UTIL = 260   # semanas (5 años)
SEMANAS   = 52
KG_TON    = 1000

# c_dump baseline (nuevo: Rodriguez Sepúlveda, c_NR=0.142, c_dump=0.213)
C_DUMP_BASELINE = 0.213   # USD/kg

# Presupuesto y demanda fijos (baseline del paper)
BUDGET_FIJO = 5616 / VIDA_UTIL   # ≈ 21.6 USD/semana

# Eje x para gráficos: c^d en USD/ton (más legible)
C_DUMP_BASELINE_TON = C_DUMP_BASELINE * 1000   # 213.0 USD/ton

# =============================================================================
# NIVELES DE c_dump: ×0.50, ×0.75, ×1.00, ×1.25, ×1.50
# =============================================================================
MULTIPLICADORES = [0.50, 0.75, 1.00, 1.25, 1.50]
C_DUMP_VALORES  = [round(C_DUMP_BASELINE * m, 6) for m in MULTIPLICADORES]

# =============================================================================
# FUNCIONES DE RESOLUCIÓN
# =============================================================================

def _bins_por_tipo(ubicaciones_y, K):
    return {k: sum(1 for (j, kk) in ubicaciones_y if kk == k) for k in K}


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
        'objective': m.ObjVal, 'ubicaciones_y': ub_y,
        'bins_abiertos': len(ub_y), 'bins_por_tipo': _bins_por_tipo(ub_y, K),
        'x_vals': {(i,j): w[i,j].x for i in I for j in J},
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
        'objective': m.ObjVal, 'ubicaciones_y': ub_y,
        'bins_abiertos': len(ub_y), 'bins_por_tipo': _bins_por_tipo(ub_y, K),
        'x_vals': {(i,j): w[i,j].x for i in I for j in J},
    }


def resolver_A3(B, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    """c_dump ya viene modificado según el multiplicador."""
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
    overflow_total = sum(z[j].x for j in J)
    return {
        'objective': m.ObjVal, 'ubicaciones_y': ub_y,
        'bins_abiertos': len(ub_y), 'bins_por_tipo': _bins_por_tipo(ub_y, K),
        'overflow': overflow_total,
        'z_vals': {j: z[j].x for j in J},
    }


def evaluar_en_A3(ubicaciones_y, B, I, J, K, d, phi, q, r, f, c_dump, c_nr):
    """Evalúa solución fija bajo condiciones realistas con c_dump del escenario."""
    m = gp.Model('Eval_A3')
    m.setParam("OutputFlag", 1)
    x = m.addVars(I, J, vtype=GRB.BINARY)
    y = m.addVars(J, K, vtype=GRB.BINARY)
    z = m.addVars(J, vtype=GRB.CONTINUOUS, lb=0)
    costo_dump = gp.quicksum(z[j] * c_dump[j] for j in J)
    costo_NR   = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(x[i,j] for j in J)) for i in I)
    m.setObjective(costo_dump + costo_NR, GRB.MINIMIZE)
    for j in J:
        for k in K:
            y[j,k].LB = ubicaciones_y.get((j,k), 0)
            y[j,k].UB = ubicaciones_y.get((j,k), 0)
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
        return None, None
    overflow_total = sum(z[j].x for j in J)
    return m.ObjVal, overflow_total


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("OVERFLOW COST SENSITIVITY ANALYSIS  [VERSIÓN CORREGIDA]")
    print(f"Baseline: c_dump = {C_DUMP_BASELINE:.4f} USD/kg ({C_DUMP_BASELINE_TON:.1f} USD/ton)")
    print(f"Budget fijo: {BUDGET_FIJO:.4f} USD/week ({BUDGET_FIJO*VIDA_UTIL:.0f} USD total)")
    print("=" * 70)

    I   = Instancia.I
    J   = Instancia.J
    K   = Instancia.K
    d   = Instancia.d
    phi = Instancia.phi
    r   = Instancia.r
    f   = Instancia.f
    c_nr = Instancia.c_nr
    q    = Instancia.q
    df_candidatos = Instancia.df_candidatos

    print(f"Instancia: {len(I)} demandas, {len(J)} candidatos, {len(K)} tipos de bin")
    print(f"c_dump valores a evaluar: {[round(v*1000,1) for v in C_DUMP_VALORES]} USD/ton")

    # =========================================================================
    # PASO 1: Ubicaciones de A1 y A2 HARDCODEADAS desde mi_reporte_A1/A2.xlsx
    # (costos c_NR=0.142, c_dump=0.213)
    # Garantiza que el escenario ×1.00 reproduzca exactamente los resultados
    # de la tabla baseline del paper.
    # =========================================================================
    print("\n" + "=" * 70)
    print("PASO 1: Fijando ubicaciones de A1 y A2 baseline (hardcoded)")
    print("=" * 70)

    ubicaciones_A1_fijas = {
        ('punto_109', 1): 1, ('punto_114', 3): 1, ('punto_12',  3): 1,
        ('punto_22',  2): 1, ('punto_28',  3): 1, ('punto_38',  1): 1,
        ('punto_39',  1): 1, ('punto_50',  2): 1, ('punto_67',  3): 1,
        ('punto_75',  3): 1,
    }
    obj_A1_baseline = 872.99   # USD/semana (de mi_reporte_A1.xlsx)

    ubicaciones_A2_fijas = {
        ('punto_114', 3): 1, ('punto_12',  3): 1, ('punto_23',  1): 1,
        ('punto_25',  1): 1, ('punto_26',  3): 1, ('punto_31',  1): 1,
        ('punto_41',  2): 1, ('punto_50',  2): 1, ('punto_67',  3): 1,
        ('punto_74',  3): 1,
    }
    obj_A2_baseline = 872.85   # USD/semana (de mi_reporte_A2.xlsx)

    bins_A1_tipos = {}
    for (j, k_t) in ubicaciones_A1_fijas:
        bins_A1_tipos[k_t] = bins_A1_tipos.get(k_t, 0) + 1
    bins_A2_tipos = {}
    for (j, k_t) in ubicaciones_A2_fijas:
        bins_A2_tipos[k_t] = bins_A2_tipos.get(k_t, 0) + 1

    print(f"  A1 → {len(ubicaciones_A1_fijas)} bins  tipos: {bins_A1_tipos}  obj: {obj_A1_baseline} USD/sem")
    print(f"  A2 → {len(ubicaciones_A2_fijas)} bins  tipos: {bins_A2_tipos}  obj: {obj_A2_baseline} USD/sem")
    print(f"  ✓ Ubicaciones A1 y A2 fijadas. Se usarán para TODOS los escenarios.")


    # =========================================================================
    # PASO 2: Loop sobre multiplicadores
    # A3 se re-optimiza en cada escenario (su objetivo SÍ depende de c_dump).
    # A1 y A2 solo se re-evalúan con ubicaciones fijas.
    # =========================================================================
    results = {
        'c_dump_usdkg': [], 'c_dump_usdton': [], 'multiplicador': [],
        'bins_A1': [], 'bins_A2': [], 'bins_A3': [],
        'overflow_A1D': [], 'overflow_A2D': [], 'overflow_A3': [],
        'hc_A1D': [], 'hc_A2D': [],
        'obj_A3': [],
    }
    types_results = {'c_dump_usdton': [], 'multiplicador': []}
    for modelo in ['A1', 'A2', 'A3']:
        for k in K:
            types_results[f'{modelo}_tipo{k}'] = []

    print("\n" + "=" * 70)
    print("PASO 2: Loop de sensibilidad")
    print("=" * 70)

    for idx, (c_val, mult) in enumerate(zip(C_DUMP_VALORES, MULTIPLICADORES), 1):
        print(f"\n[{idx}/{len(MULTIPLICADORES)}] c_dump = {c_val:.4f} USD/kg "
              f"({c_val*1000:.1f} USD/ton) (×{mult:.2f})")

        c_dump_esc = {j: c_val for j in J}

        # --- A1-D: evaluación con ubicaciones FIJAS del baseline ---
        # El objetivo "planeado" de A1 siempre es el baseline (no depende de c_dump)
        cost_A1_real, overflow_A1_real = evaluar_en_A3(
            ubicaciones_A1_fijas, BUDGET_FIJO, I, J, K, d, phi, q, r, f,
            c_dump_esc, c_nr)
        if cost_A1_real is None:
            print("  ❌ Eval A1 falló"); continue

        # El costo "planeado" de A1 con el c_dump del escenario actual
        # (simula lo que el planificador tradicional habría estimado bajo este c_o)
        hidden_A1 = cost_A1_real - obj_A1_baseline
        print(f"  A1-D → overflow: {overflow_A1_real:.2f} kg  "
              f"hidden (vs baseline obj): {hidden_A1:.4f} USD/week")

        # --- A2-D: evaluación con ubicaciones FIJAS del baseline ---
        cost_A2_real, overflow_A2_real = evaluar_en_A3(
            ubicaciones_A2_fijas, BUDGET_FIJO, I, J, K, d, phi, q, r, f,
            c_dump_esc, c_nr)
        if cost_A2_real is None:
            print("  ❌ Eval A2 falló"); continue

        hidden_A2 = cost_A2_real - obj_A2_baseline
        print(f"  A2-D → overflow: {overflow_A2_real:.2f} kg  "
              f"hidden (vs baseline obj): {hidden_A2:.4f} USD/week")

        # --- A3: re-optimizado con el c_dump del escenario (sí cambia su solución) ---
        sol_A3 = resolver_A3(BUDGET_FIJO, I, J, K, d, phi, q, r, f,
                              c_dump_esc, c_nr)
        if sol_A3 is None:
            print("  ❌ A3 falló"); continue
        print(f"  A3 → bins: {sol_A3['bins_abiertos']}  "
              f"overflow: {sol_A3['overflow']:.2f} kg  "
              f"tipos: {sol_A3['bins_por_tipo']}")

        # Guardar
        # A1: bins_abiertos y bins_por_tipo derivados de ubicaciones_A1_fijas hardcodeadas
        bins_A1_tipos = {}
        for (j, k_t), v in ubicaciones_A1_fijas.items():
            bins_A1_tipos[k_t] = bins_A1_tipos.get(k_t, 0) + 1
        bins_A1_total = len(ubicaciones_A1_fijas)

        results['c_dump_usdkg'].append(c_val)
        results['c_dump_usdton'].append(round(c_val * 1000, 1))
        results['multiplicador'].append(mult)
        results['bins_A1'].append(bins_A1_total)
        results['bins_A2'].append(len(ubicaciones_A2_fijas))
        results['bins_A3'].append(sol_A3['bins_abiertos'])
        results['overflow_A1D'].append(overflow_A1_real)
        results['overflow_A2D'].append(overflow_A2_real)
        results['overflow_A3'].append(sol_A3['overflow'])
        results['hc_A1D'].append(hidden_A1)
        results['hc_A2D'].append(hidden_A2)
        results['obj_A3'].append(sol_A3['objective'])

        types_results['c_dump_usdton'].append(round(c_val * 1000, 1))
        types_results['multiplicador'].append(mult)
        for k in K:
            types_results[f'A1_tipo{k}'].append(bins_A1_tipos.get(k, 0))
            types_results[f'A2_tipo{k}'].append(bins_A2_tipos.get(k, 0))
            types_results[f'A3_tipo{k}'].append(sol_A3['bins_por_tipo'].get(k, 0))

    df = pd.DataFrame(results)
    df_types = pd.DataFrame(types_results)

    # =========================================================================
    # CONVERSIONES ANUALES
    # =========================================================================
    df['overflow_A1D_tpa'] = df['overflow_A1D'] * SEMANAS / KG_TON
    df['overflow_A2D_tpa'] = df['overflow_A2D'] * SEMANAS / KG_TON
    df['overflow_A3_tpa']  = df['overflow_A3']  * SEMANAS / KG_TON
    df['hc_A1D_anual']     = df['hc_A1D']       * SEMANAS
    df['hc_A2D_anual']     = df['hc_A2D']       * SEMANAS

    # =========================================================================
    # EXCEL
    # =========================================================================
    excel_file = 'sensitivity_overflow_cost.xlsx'
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Results', index=False)
        df_types.to_excel(writer, sheet_name='Container_Types', index=False)
    print(f"\n✓ Excel guardado: {excel_file}")

    # =========================================================================
    # PDF CON FIGURAS
    # =========================================================================
    plt.rcParams.update({
        'font.family': 'serif', 'font.size': 11,
        'axes.grid': True, 'grid.linestyle': '--', 'grid.alpha': 0.5,
    })
    COLOR_A1D = '#1f77b4'
    COLOR_A2D = '#d62728'
    COLOR_A3  = '#2ca02c'

    x_axis = df['c_dump_usdton']
    baseline_ton = round(C_DUMP_BASELINE * 1000, 1)

    pdf_file = 'sensitivity_overflow_cost.pdf'
    with PdfPages(pdf_file) as pdf:

        # --- Figura 1: Overflow comparison ---
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x_axis, df['overflow_A1D_tpa'], 'o-', color=COLOR_A1D,
                linewidth=2, markersize=6, label='SL-RBLP-A1-D')
        ax.plot(x_axis, df['overflow_A2D_tpa'], 's-', color=COLOR_A2D,
                linewidth=2, markersize=6, label='SL-RBLP-A2-D')
        ax.plot(x_axis, df['overflow_A3_tpa'],  '^-', color=COLOR_A3,
                linewidth=2, markersize=6, label='SL-RBLP')
        ax.axvline(baseline_ton, color='gray', linestyle=':', linewidth=1.5,
                   label=f'Baseline ($c^d$ = {baseline_ton:.0f} USD/ton)')
        ax.set_xlabel(r'Overflow unit cost, $c^d$ (USD/ton)')
        ax.set_ylabel('Annual overflow (tons/year)')
        ax.yaxis.set_major_formatter(plt.matplotlib.ticker.FormatStrFormatter('%.2f'))
        ax.legend(fontsize=10)
        fig.tight_layout()
        pdf.savefig(fig, dpi=300, bbox_inches='tight')
        plt.close(fig)

        # --- Figura 2: Bins por tipo y modelo (barras apiladas) ---
        import numpy as np
        TIPO_COLORS = {1: '#4e79a7', 2: '#f28e2b', 3: '#59a14f'}
        TIPO_LABELS = {1: 'Type 1 (600 kg)', 2: 'Type 2 (900 kg)', 3: 'Type 3 (1,200 kg)'}
        x_ticks = df_types['c_dump_usdton'].values
        x_idx   = np.arange(len(x_ticks))
        bar_w   = 0.55
        bl_idx  = next((i for i, v in enumerate(x_ticks)
                        if abs(v - baseline_ton) < 1), None)

        fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
        for ax_i, (modelo, lbl) in enumerate(
                [('A1', 'SL-RBLP-A1'), ('A2', 'SL-RBLP-A2'), ('A3', 'SL-RBLP')]):
            ax = axes[ax_i]
            bottom = np.zeros(len(x_ticks))
            for k in K:
                col  = f'{modelo}_tipo{k}'
                vals = df_types[col].values.astype(float) if col in df_types.columns \
                       else np.zeros(len(x_ticks))
                bars = ax.bar(x_idx, vals, bar_w, bottom=bottom,
                              color=TIPO_COLORS[k], label=TIPO_LABELS[k])
                for bar, val, bot in zip(bars, vals, bottom):
                    if val >= 1:
                        ax.text(bar.get_x() + bar.get_width() / 2, bot + val / 2,
                                str(int(val)), ha='center', va='center',
                                fontsize=9, fontweight='bold', color='white')
                bottom += vals
            ax.set_xticks(x_idx)
            ax.set_xticklabels([f'{v:.0f}' for v in x_ticks],
                               rotation=45, ha='right', fontsize=9)
            ax.set_xlabel(r'$c^d$ (USD/ton)', fontsize=9)
            ax.set_title(lbl, fontsize=11)
            if bl_idx is not None:
                ax.axvline(bl_idx, color='gray', linestyle=':', linewidth=1.5)
            if ax_i == 0:
                ax.set_ylabel('Number of bins')

        handles, labels = axes[2].get_legend_handles_labels()
        fig.legend(handles, labels, loc='lower center', ncol=3,
                   fontsize=9, framealpha=1, edgecolor='black',
                   bbox_to_anchor=(0.5, -0.08))
        fig.tight_layout()
        pdf.savefig(fig, dpi=300, bbox_inches='tight')
        plt.close(fig)

    print(f"✓ PDF guardado: {pdf_file}  (2 figuras: overflow, bin types)")

    # =========================================================================
    # RESUMEN EN CONSOLA
    # =========================================================================
    print("\n" + "=" * 75)
    print(f"{'c^d (USD/ton)':>14} {'×':>5} {'A3 Bins':>7} | "
          f"{'OF A1-D':>9} {'OF A2-D':>9} {'OF A3':>9} | "
          f"{'HC A1-D':>9} {'HC A2-D':>9}")
    print("-" * 75)
    for _, row in df.iterrows():
        marca = " ← baseline" if abs(row['multiplicador'] - 1.0) < 0.01 else ""
        print(f"  {row['c_dump_usdton']:>12.1f}  ×{row['multiplicador']:.2f}  "
              f"{int(row['bins_A3']):>7} | "
              f"{row['overflow_A1D_tpa']:>9.1f} {row['overflow_A2D_tpa']:>9.1f} "
              f"{row['overflow_A3_tpa']:>9.1f} | "
              f"${row['hc_A1D_anual']:>8,.0f} ${row['hc_A2D_anual']:>8,.0f}{marca}")
    print("=" * 75)

    return df, df_types


if __name__ == "__main__":
    df_results, df_types = main()