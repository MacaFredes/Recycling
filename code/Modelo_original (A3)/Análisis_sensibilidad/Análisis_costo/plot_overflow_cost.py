# -*- coding: utf-8 -*-
"""
GENERADOR DE GRÁFICOS - ANÁLISIS DE SENSIBILIDAD DE COSTO DE OVERFLOW
Lee sensitivity_overflow_cost.xlsx y genera sensitivity_overflow_cost.pdf

Edita solo este archivo para cambiar colores, estilos, etiquetas.
No requiere Gurobi.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages
import os

# =============================================================================
# PARÁMETROS
# =============================================================================
EXCEL_INPUT     = 'sensitivity_overflow_cost.xlsx'
PDF_OUTPUT      = 'sensitivity_overflow_cost.pdf'
C_DUMP_BASELINE = 0.213           # USD/kg
BASELINE_TON    = round(C_DUMP_BASELINE * 1000, 1)   # 213.0 USD/ton

COLOR_A1D = '#1f77b4'
COLOR_A2D = '#d62728'
COLOR_A3  = '#2ca02c'
TIPO_COLORS = {1: '#4e79a7', 2: '#f28e2b', 3: '#59a14f'}
TIPO_LABELS = {1: 'Type 1 (600 kg)', 2: 'Type 2 (900 kg)', 3: 'Type 3 (1,200 kg)'}
K = [1, 2, 3]

# =============================================================================
# LECTURA DE DATOS
# =============================================================================
if not os.path.exists(EXCEL_INPUT):
    raise FileNotFoundError(f"No se encontró '{EXCEL_INPUT}'.")

df       = pd.read_excel(EXCEL_INPUT, sheet_name='Results')
df_types = pd.read_excel(EXCEL_INPUT, sheet_name='Container_Types')

# =============================================================================
# ESTILO GLOBAL
# =============================================================================
plt.rcParams.update({
    'font.family': 'serif', 'font.size': 11,
    'axes.grid': True, 'grid.linestyle': '--', 'grid.alpha': 0.5,
})

vline_kw = dict(color='gray', linestyle=':', linewidth=1.5)
x_axis   = df['c_dump_usdton']

with PdfPages(PDF_OUTPUT) as pdf:

    # -------------------------------------------------------------------------
    # Figura 1: Overflow anual
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(x_axis, df['overflow_A1D_tpa'], 'o-', color=COLOR_A1D,
            linewidth=2, markersize=6, label='SL-RBLP-A1-D')
    ax.plot(x_axis, df['overflow_A2D_tpa'], 's-', color=COLOR_A2D,
            linewidth=2, markersize=6, label='SL-RBLP-A2-D')
    ax.plot(x_axis, df['overflow_A3_tpa'],  '^-', color=COLOR_A3,
            linewidth=2, markersize=6, label='SL-RBLP')
    ax.axvline(BASELINE_TON, **vline_kw,
               label=f'Baseline ($c^d$ = {BASELINE_TON:.0f} USD/ton)')
    ax.set_xlabel(r'Overflow unit cost, $c^d$ (USD/ton)')
    ax.set_ylabel('Annual overflow (metric tonnes/year)')
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
    ax.legend(fontsize=10)
    fig.tight_layout()
    pdf.savefig(fig, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("✓ Figura 1: overflow anual")

    # -------------------------------------------------------------------------
    # Figura 2: Bins por tipo y modelo (barras apiladas)
    # -------------------------------------------------------------------------
    x_ticks = df_types['c_dump_usdton'].values
    x_idx   = np.arange(len(x_ticks))
    bar_w   = 0.55
    bl_idx  = next((i for i, v in enumerate(x_ticks)
                    if abs(v - BASELINE_TON) < 1), None)

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
            ax.axvline(bl_idx, **vline_kw)
        if ax_i == 0:
            ax.set_ylabel('Number of bins')

    handles, labels = axes[2].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3,
               fontsize=9, framealpha=1, edgecolor='black',
               bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    pdf.savefig(fig, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("✓ Figura 2: bins por tipo y modelo")

print(f"\n✓ PDF guardado: {PDF_OUTPUT}")
