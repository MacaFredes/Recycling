# -*- coding: utf-8 -*-
"""
PLOTTING — Sensibilidad de Demanda
===================================
Lee sensitivity_demand.xlsx y regenera sensitivity_demand.pdf
con 2 figuras. NO requiere Gurobi ni correr la optimización.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# =============================================================================
# PARÁMETROS
# =============================================================================
INPUT_EXCEL        = 'sensitivity_demand.xlsx'
OUTPUT_PDF         = 'sensitivity_demand.pdf'
FACTOR_BASELINE_ANUAL = 12.48   # kg/hh/year

plt.rcParams.update({
    'font.family'  : 'serif',
    'font.size'    : 11,
    'axes.grid'    : True,
    'grid.linestyle': '--',
    'grid.alpha'   : 0.5,
})

COLOR_A1D = '#1f77b4'
COLOR_A2D = '#d62728'
COLOR_A3  = '#2ca02c'

x_label  = 'Annual glass generation rate (kg per household per year)'
vline_kw = dict(color='gray', linestyle=':', linewidth=1.5)

# =============================================================================
# LEER DATOS
# =============================================================================
df       = pd.read_excel(INPUT_EXCEL, sheet_name='Results')
df_types = pd.read_excel(INPUT_EXCEL, sheet_name='Container_Types')

K        = [1, 2, 3]
x_axis   = df['factor_anual']
x_ticks  = df_types['factor_anual'].values
x_idx    = np.arange(len(x_ticks))

# =============================================================================
# GENERAR PDF
# =============================================================================
with PdfPages(OUTPUT_PDF) as pdf:

    # ── Figura 1: Overflow anual ──────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(x_axis, df['overflow_A1D_tpa'], 'o-', color=COLOR_A1D,
            linewidth=2, markersize=6, label='SL-RBLP-A1-D')
    ax.plot(x_axis, df['overflow_A2D_tpa'], 's-', color=COLOR_A2D,
            linewidth=2, markersize=6, label='SL-RBLP-A2-D')
    ax.plot(x_axis, df['overflow_A3_tpa'],  '^-', color=COLOR_A3,
            linewidth=2, markersize=6, label='SL-RBLP')
    ax.axvline(FACTOR_BASELINE_ANUAL, **vline_kw,
               label=f'Baseline ({FACTOR_BASELINE_ANUAL} kg/hh/year)')
    ax.set_xlabel(x_label)
    ax.set_ylabel('Annual overflow (metric tonnes/year)')
    ax.legend(fontsize=10)
    fig.tight_layout()
    pdf.savefig(fig, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("✓ Figura 1: overflow")

    # ── Figura 2: Bins por tipo y modelo ─────────────────────────────────────
    tipo_colors = {1: '#4e79a7', 2: '#f28e2b', 3: '#59a14f'}
    tipo_labels = {1: 'Type 1 (600 kg)', 2: 'Type 2 (900 kg)', 3: 'Type 3 (1,200 kg)'}
    bar_w = 0.55

    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    for ax_i, (modelo, lbl) in enumerate(
            [('A1', 'SL-RBLP-A1'), ('A2', 'SL-RBLP-A2'), ('A3', 'SL-RBLP')]):
        ax = axes[ax_i]
        bottom = np.zeros(len(x_ticks))
        for k in K:
            vals = df_types[f'{modelo}_tipo{k}'].values.astype(float)
            ax.bar(x_idx, vals, bar_w, bottom=bottom,
                   color=tipo_colors[k], label=tipo_labels[k])
            bottom += vals
        ax.set_xticks(x_idx)
        ax.set_xticklabels([f'{v:.2f}' for v in x_ticks],
                           rotation=45, ha='right', fontsize=9)
        ax.set_xlabel(x_label, fontsize=9)
        ax.set_title(lbl, fontsize=11)
        bl_idx = list(x_ticks).index(FACTOR_BASELINE_ANUAL) \
                 if FACTOR_BASELINE_ANUAL in x_ticks else None
        if bl_idx is not None:
            ax.axvline(bl_idx, **vline_kw)
        if ax_i == 0:
            ax.set_ylabel('Number of bins')
        if ax_i == 2:
            ax.legend(fontsize=9, loc='upper left')
    fig.tight_layout()
    pdf.savefig(fig, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("✓ Figura 2: bins por tipo")

print(f"\n✓ PDF guardado: {OUTPUT_PDF}  (2 páginas)")
