import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# FUNCION PRINCIPAL - MODIFICADA PARA INCLUIR phi y r
# ============================================================================

def generar_resultados(model, x, y, z, q, I, J, K, d, f, c_dump, c_nr, phi, r,
                       df_demandas, df_candidatos, 
                       nombre_archivo="reporte_resultados.pdf"):
    """
    Genera reporte PDF + Excel con resultados del modelo RBLP.
    
    NUEVO: Ahora incluye phi y r para generar la hoja 3 del Excel
    """
    
    # ========================================================================
    # VERIFICAR STATUS DEL MODELO
    # ========================================================================
    
    status_dict = {
        1: "LOADED", 2: "OPTIMAL", 3: "INFEASIBLE", 4: "INF_OR_UNBD",
        5: "UNBOUNDED", 6: "CUTOFF", 7: "ITERATION_LIMIT", 8: "NODE_LIMIT",
        9: "TIME_LIMIT", 10: "SOLUTION_LIMIT", 11: "INTERRUPTED",
        12: "NUMERIC", 13: "SUBOPTIMAL", 14: "INPROGRESS", 15: "USER_OBJ_LIMIT"
    }
    
    status_msg = status_dict.get(model.Status, f"Desconocido ({model.Status})")
    tiene_solucion = model.Status in [2, 9, 13]
    
    if not tiene_solucion:
        print("\n" + "="*80)
        print("ERROR: NO HAY SOLUCION DISPONIBLE")
        print("="*80)
        print(f"Status: {model.Status} - {status_msg}")
        return None, None, None, None
    
    es_optima = (model.Status == 2)
    
    print("\n" + "="*80)
    print("EXTRAYENDO RESULTADOS DEL MODELO")
    print("="*80)
    print(f"Status: {status_msg}")
    
    # ========================================================================
    # EXTRAER COSTOS
    # ========================================================================
    
    try:
        costo_instalacion = sum(y[j,k].x * f[j,k] for j in J for k in K)
        costo_overflow = sum(z[j].x * c_dump[j] for j in J)
        costo_no_reciclar = sum(q[i] * c_nr[i] * (1 - sum(x[i,j].x for j in J)) for i in I)
        
        print(f"\nDESGLOSE DE COSTOS:")
        print(f"  - Instalación: ${costo_instalacion:,.2f}")
        print(f"  - Overflow: ${costo_overflow:,.2f}")
        print(f"  - No Reciclar: ${costo_no_reciclar:,.2f}")
        print(f"  - TOTAL F.O: ${model.ObjVal:,.2f}")
    except Exception as e:
        print(f"ERROR al calcular costos: {e}")
        costo_instalacion = costo_overflow = costo_no_reciclar = 0
    
    # ========================================================================
    # EXTRAER SITIOS ACTIVADOS
    # ========================================================================
    
    sitios_activados = []
    
    for j in J:
        contenedor_instalado = None
        capacidad_sitio = 0
        costo_fijo_sitio = 0
        
        for k in K:
            try:
                if y[j,k].x > 0.5:
                    contenedor_instalado = k
                    capacidad_sitio = d[j,k]
                    costo_fijo_sitio = f[j,k]
                    break
            except:
                continue
        
        if contenedor_instalado is not None:
            try:
                residuos_recibidos = sum(q[i] * x[i,j].x for i in I)
            except:
                residuos_recibidos = 0
            
            try:
                overflow = z[j].x if z[j].x > 1e-6 else 0
            except:
                overflow = 0
            
            coords = df_candidatos[df_candidatos['id_unico'] == j]
            if len(coords) > 0:
                lat = coords['latitud'].values[0]
                lon = coords['longitud'].values[0]
            else:
                lat, lon = None, None
            
            utilizacion = (residuos_recibidos / capacidad_sitio * 100) if capacidad_sitio > 0 else 0
            
            sitios_activados.append({
                'sitio': j,
                'tipo_contenedor': contenedor_instalado,
                'capacidad': capacidad_sitio,
                'costo_fijo': costo_fijo_sitio,
                'residuos_recibidos': residuos_recibidos,
                'overflow': overflow,
                'utilizacion': utilizacion,
                'latitud': lat,
                'longitud': lon
            })
    
    df_sitios = pd.DataFrame(sitios_activados)
    
    print(f"\nSITIOS ACTIVADOS: {len(df_sitios)}")
    
    # ========================================================================
    # EXTRAER ASIGNACIONES
    # ========================================================================
    
    asignaciones = []
    for i in I:
        for j in J:
            try:
                if x[i,j].x > 0.5:
                    coords_i = df_demandas[df_demandas['id_unico'] == i]
                    coords_j = df_candidatos[df_candidatos['id_unico'] == j]
                    
                    if len(coords_i) > 0 and len(coords_j) > 0:
                        asignaciones.append({
                            'demanda': i,
                            'sitio': j,
                            'cantidad': q[i],
                            'lat_demanda': coords_i['latitud'].values[0],
                            'lon_demanda': coords_i['longitud'].values[0],
                            'lat_sitio': coords_j['latitud'].values[0],
                            'lon_sitio': coords_j['longitud'].values[0]
                        })
            except:
                continue
    
    df_asignaciones = pd.DataFrame(asignaciones)
    
    # ========================================================================
    # ESTADISTICAS
    # ========================================================================
    
    estadisticas = {
        'es_optima': es_optima,
        'status': model.Status,
        'status_msg': status_msg,
        'funcion_objetivo': model.ObjVal,
        'costo_instalacion': costo_instalacion,
        'costo_overflow': costo_overflow,
        'costo_no_reciclar': costo_no_reciclar,
        'total_sitios_activados': len(df_sitios),
        'total_residuos': sum(q[i] for i in I),
        'residuos_reciclados': df_sitios['residuos_recibidos'].sum() if len(df_sitios) > 0 else 0,
        'overflow_total': df_sitios['overflow'].sum() if len(df_sitios) > 0 else 0,
        'tasa_reciclaje': 0,
        'contenedores_por_tipo': {},
        'utilizacion_promedio': df_sitios['utilizacion'].mean() if len(df_sitios) > 0 else 0
    }
    
    if estadisticas['total_residuos'] > 0:
        estadisticas['tasa_reciclaje'] = (estadisticas['residuos_reciclados'] / 
                                          estadisticas['total_residuos']) * 100
    
    for k in K:
        count = len(df_sitios[df_sitios['tipo_contenedor'] == k])
        estadisticas['contenedores_por_tipo'][k] = count
    
    # ========================================================================
    # GENERAR PDF (MANTIENE ORIGINAL)
    # ========================================================================
    
    print(f"\nGenerando PDF: {nombre_archivo}")
    
    with PdfPages(nombre_archivo) as pdf:
        _generar_pagina_resumen(pdf, estadisticas, df_sitios, d)
        _generar_mapa_sitios_activados(pdf, df_sitios, df_demandas, d)
        _generar_mapa_overflow(pdf, df_sitios, df_candidatos)
        _generar_mapa_asignaciones(pdf, df_asignaciones, df_sitios)
        
        d_pdf = pdf.infodict()
        d_pdf['Title'] = 'Reporte de Resultados - Modelo RBLP'
        d_pdf['Author'] = 'Sistema de Optimizacion'
        d_pdf['CreationDate'] = datetime.now()
    
    # ========================================================================
    # GENERAR EXCEL (MODIFICADO - 3 HOJAS)
    # ========================================================================
    
    try:
        nombre_excel = nombre_archivo.replace('.pdf', '.xlsx')
        generar_excel_detallado(df_sitios, df_asignaciones, x, y, z, q, I, J, K, d,
                               estadisticas, phi, r, nombre_archivo=nombre_excel)
    except Exception as e:
        print(f"\nError generando Excel: {e}")
        import traceback
        traceback.print_exc()
    
    return (estadisticas['funcion_objetivo'], df_sitios, estadisticas['overflow_total'], estadisticas)


# ============================================================================
# FUNCIONES AUXILIARES PARA PDF (SIN CAMBIOS)
# ============================================================================

def _generar_pagina_resumen(pdf, stats, df_sitios, d):
    """Pagina 1: Resumen ejecutivo"""
    fig = plt.figure(figsize=(11, 8.5))
    
    if stats['es_optima']:
        titulo = 'REPORTE DE RESULTADOS - MODELO RBLP\n(SOLUCION OPTIMA)'
    else:
        titulo = f'REPORTE DE RESULTADOS - MODELO RBLP\n({stats["status_msg"]})'
    
    fig.suptitle(titulo, fontsize=14, fontweight='bold', y=0.98)
    ax = fig.add_subplot(111)
    ax.axis('off')
    
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    capacidades_unicas = {}
    if len(df_sitios) > 0:
        for k in sorted(df_sitios['tipo_contenedor'].unique()):
            cap = df_sitios[df_sitios['tipo_contenedor'] == k]['capacidad'].iloc[0]
            capacidades_unicas[k] = cap
    
    texto = f"""
==================================================================
                     RESUMEN EJECUTIVO                           
==================================================================

Fecha: {fecha}
Status: {stats['status_msg']}

------------------------------------------------------------------
 COSTOS (USD)
------------------------------------------------------------------
   Instalación:          ${stats['costo_instalacion']:>15,.2f}
   Overflow:             ${stats['costo_overflow']:>15,.2f}
   No Reciclar:          ${stats['costo_no_reciclar']:>15,.2f}
   ----------------------------------------------------------
   TOTAL:                ${stats['funcion_objetivo']:>15,.2f}

------------------------------------------------------------------
 INFRAESTRUCTURA
------------------------------------------------------------------
   Sitios activados: {stats['total_sitios_activados']}
   
   Contenedores por tipo:
"""
    
    tipo_nombres = {1: "Pequeño", 2: "Mediano", 3: "Grande"}
    for k in sorted(stats['contenedores_por_tipo'].keys()):
        count = stats['contenedores_por_tipo'][k]
        cap = capacidades_unicas.get(k, '?')
        nombre = tipo_nombres.get(k, f"Tipo {k}")
        texto += f"      - Tipo {k} ({nombre}, {cap} kg): {count}\n"
    
    texto += f"""
------------------------------------------------------------------
 GESTIÓN DE RESIDUOS
------------------------------------------------------------------
   Total generado:       {stats['total_residuos']:>12,.2f} kg
   Reciclado:            {stats['residuos_reciclados']:>12,.2f} kg
   Tasa reciclaje:       {stats['tasa_reciclaje']:>12,.2f} %
   Overflow total:       {stats['overflow_total']:>12,.2f} kg

------------------------------------------------------------------
 EFICIENCIA
------------------------------------------------------------------
   Utilización promedio: {stats['utilizacion_promedio']:.2f}%
"""
    
    if len(df_sitios) > 0:
        sitio_max = df_sitios.loc[df_sitios['residuos_recibidos'].idxmax(), 'sitio']
        max_carga = df_sitios['residuos_recibidos'].max()
        texto += f"   Sitio con mayor carga: {sitio_max} ({max_carga:,.2f} kg)\n"
    
    texto += """
==================================================================
  Ver Excel para detalles
==================================================================
"""
    
    ax.text(0.05, 0.95, texto, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


def _generar_mapa_sitios_activados(pdf, df_sitios, df_demandas, d):
    """Pagina 2: Mapa de sitios"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8))
    fig.suptitle('SITIOS ACTIVADOS', fontsize=14, fontweight='bold')
    
    ax1.scatter(df_demandas['longitud'], df_demandas['latitud'],
                c='lightblue', s=30, alpha=0.3, label='Demandas')
    
    if len(df_sitios) > 0:
        colores = {1: '#FFD700', 2: '#FFA500', 3: '#FF4500'}
        nombres = {1: 'Pequeño', 2: 'Mediano', 3: 'Grande'}
        
        for k in sorted(colores.keys()):
            df_k = df_sitios[df_sitios['tipo_contenedor'] == k]
            if len(df_k) > 0:
                tamanos = 200
                cap = df_k['capacidad'].iloc[0]
                ax1.scatter(df_k['longitud'], df_k['latitud'],
                           c=colores[k], s=tamanos, alpha=0.7,
                           edgecolors='black', linewidth=2,
                           label=f'Tipo {k}: {nombres[k]} ({cap} kg)', zorder=5)
    
    ax1.set_xlabel('Longitud')
    ax1.set_ylabel('Latitud')
    ax1.set_title('Ubicación de Contenedores')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Gráfico de barras
    if len(df_sitios) > 0:
        tipos = df_sitios.groupby('tipo_contenedor').agg({
            'residuos_recibidos': 'sum',
            'sitio': 'count'
        }).reset_index()
        tipos.columns = ['tipo', 'total_residuos', 'cantidad']
        
        ax2.bar(tipos['tipo'], tipos['cantidad'], color='steelblue', alpha=0.8)
        ax2.set_xlabel('Tipo de Contenedor')
        ax2.set_ylabel('Cantidad')
        ax2.set_title('Distribución por Tipo')
        ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


def _generar_mapa_overflow(pdf, df_sitios, df_candidatos):
    """Pagina 3: Overflow"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8))
    fig.suptitle('ANÁLISIS DE OVERFLOW', fontsize=14, fontweight='bold')
    
    ax1.scatter(df_candidatos['longitud'], df_candidatos['latitud'],
                c='lightgray', s=50, alpha=0.4, label='No activados')
    
    if len(df_sitios) > 0:
        df_sin = df_sitios[df_sitios['overflow'] == 0]
        df_con = df_sitios[df_sitios['overflow'] > 0]
        
        if len(df_sin) > 0:
            ax1.scatter(df_sin['longitud'], df_sin['latitud'],
                       c='green', s=200, alpha=0.6,
                       label=f'Sin overflow ({len(df_sin)})', zorder=5)
        
        if len(df_con) > 0:
            ax1.scatter(df_con['longitud'], df_con['latitud'],
                       c='red', s=200, alpha=0.8,
                       label=f'Con overflow ({len(df_con)})', zorder=5)
    
    ax1.set_xlabel('Longitud')
    ax1.set_ylabel('Latitud')
    ax1.set_title('Mapa de Overflow')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    ax2.axis('off')
    stats_text = "ESTADÍSTICAS DE OVERFLOW\n\n"
    if len(df_sitios) > 0:
        total_overflow = df_sitios['overflow'].sum()
        sitios_overflow = len(df_sitios[df_sitios['overflow'] > 0])
        stats_text += f"Total overflow: {total_overflow:.2f} kg\n"
        stats_text += f"Sitios afectados: {sitios_overflow}\n"
    ax2.text(0.1, 0.9, stats_text, transform=ax2.transAxes,
            fontsize=10, verticalalignment='top', fontfamily='monospace')
    
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


def _generar_mapa_asignaciones(pdf, df_asignaciones, df_sitios):
    """Pagina 4: Asignaciones"""
    fig, ax = plt.subplots(figsize=(12, 10))
    fig.suptitle('RED DE ASIGNACIONES', fontsize=14, fontweight='bold')
    
    if len(df_asignaciones) > 0 and len(df_sitios) > 0:
        for _, row in df_asignaciones.iterrows():
            ax.plot([row['lon_demanda'], row['lon_sitio']],
                   [row['lat_demanda'], row['lat_sitio']],
                   'gray', alpha=0.2, linewidth=0.5, zorder=1)
        
        ax.scatter(df_asignaciones['lon_demanda'], 
                  df_asignaciones['lat_demanda'],
                  c='lightblue', s=20, alpha=0.5, 
                  label=f'Demandas ({len(df_asignaciones)})', zorder=2)
        
        colores = {1: '#FFD700', 2: '#FFA500', 3: '#FF4500'}
        for k in [1, 2, 3]:
            df_k = df_sitios[df_sitios['tipo_contenedor'] == k]
            if len(df_k) > 0:
                ax.scatter(df_k['longitud'], df_k['latitud'],
                          c=colores[k], s=300, alpha=0.8,
                          edgecolors='black', linewidth=2,
                          label=f'Tipo {k}', zorder=5)
    
    ax.set_xlabel('Longitud')
    ax.set_ylabel('Latitud')
    ax.set_title(f'{len(df_asignaciones)} Asignaciones')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


# ============================================================================
# FUNCIÓN EXCEL MODIFICADA - 3 HOJAS
# ============================================================================

def generar_excel_detallado(df_sitios, df_asignaciones, x, y, z, q, I, J, K, d, 
                           estadisticas, phi, r, nombre_archivo="resultados.xlsx"):
    """
    Genera Excel con 3 hojas:
    1. Resumen
    2. Detalle Candidatos (modificado)
    3. Sitios No Reciclaron (nuevo)
    """
    
    print(f"\nGenerando Excel: {nombre_archivo}")
    
    Ji = {}
    for i in I:
        Ji[i] = []
        for j in J:
            if r[i] > phi[i,j] :
                Ji[i].append(j)
    
    with pd.ExcelWriter(nombre_archivo, engine='openpyxl') as writer:
        
        # ====================================================================
        # HOJA 1: RESUMEN
        # ====================================================================
        
        resumen_data = {
            'Indicador': [
                'Función Objetivo (USD)',
                'Costo Instalación (USD)',
                'Costo Overflow (USD)',
                'Costo No Reciclar (USD)',
                '',
                'Sitios Activados',
                'Total Residuos (kg)',
                'Reciclados (kg)',
                'NO Reciclados (kg)',
                'Tasa Reciclaje (%)',
                'Overflow Total (kg)',
                '',
                'Status',
                'Óptima'
            ],
            'Valor': [
                f"${estadisticas['funcion_objetivo']:,.2f}",
                f"${estadisticas['costo_instalacion']:,.2f}",
                f"${estadisticas['costo_overflow']:,.2f}",
                f"${estadisticas['costo_no_reciclar']:,.2f}",
                '',
                estadisticas['total_sitios_activados'],
                f"{estadisticas['total_residuos']:,.2f}",
                f"{estadisticas['residuos_reciclados']:,.2f}",
                f"{estadisticas['total_residuos'] - estadisticas['residuos_reciclados']:,.2f}",
                f"{estadisticas['tasa_reciclaje']:.2f}",
                f"{estadisticas['overflow_total']:,.2f}",
                '',
                estadisticas['status_msg'],
                'SI' if estadisticas['es_optima'] else 'NO'
            ]
        }
        
        df_resumen = pd.DataFrame(resumen_data)
        df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
        
        # ====================================================================
        # HOJA 2: DETALLE CANDIDATOS (MODIFICADO)
        # ====================================================================
        
        detalle_candidatos = []
        
        for j in J:
            for k in K:
                try:
                    if y[j,k].x > 0.5:
                        residuos_recibidos = sum(q[i] * x[i,j].x for i in I)
                        capacidad = d[j,k]
                        overflow = max(residuos_recibidos - capacidad, 0)
                        
                        demandas_asignadas = [i for i in I if x[i,j].x > 0.5]
                        
                        if demandas_asignadas:
                            for i in demandas_asignadas:
                                detalle_candidatos.append({
                                    'Candidato': j,
                                    'Candidato_Activo': 'SI',
                                    'Demanda_Asignada': i,
                                    'Residuos_Demanda': round(q[i], 2),
                                    'Tipo_Contenedor': k,
                                    'Capacidad_Contenedor': capacidad,
                                    'Residuos_Recibidos': round(residuos_recibidos, 2),
                                    'Overflow': round(overflow, 2)
                                })
                        else:
                            detalle_candidatos.append({
                                'Candidato': j,
                                'Candidato_Activo': 'SI',
                                'Demanda_Asignada': 'Ninguna',
                                'Residuos_Demanda': 0,
                                'Tipo_Contenedor': k,
                                'Capacidad_Contenedor': capacidad,
                                'Residuos_Recibidos': round(residuos_recibidos, 2),
                                'Overflow': round(overflow, 2)
                            })
                except:
                    continue
        
        # Candidatos NO activados
        for j in J:
            activado = any(y[j,k].x > 0.5 for k in K)
            if not activado:
                detalle_candidatos.append({
                    'Candidato': j,
                    'Candidato_Activo': 'NO',
                    'Demanda_Asignada': 'N/A',
                    'Residuos_Demanda': 0,
                    'Tipo_Contenedor': 'N/A',
                    'Capacidad_Contenedor': 0,
                    'Residuos_Recibidos': 0,
                    'Overflow': 0
                })
        
        df_detalle = pd.DataFrame(detalle_candidatos)
        df_detalle = df_detalle.sort_values(['Candidato_Activo', 'Candidato'], 
                                             ascending=[False, True])
        df_detalle.to_excel(writer, sheet_name='Detalle Candidatos', index=False)
        
        # ====================================================================
        # HOJA 3: SITIOS NO RECICLARON (CORREGIDO)
        # ====================================================================
        
        # Primero: identificar sitios que NO reciclan
        sitios_no_RN = []
        for i in I:
            if sum(x[i,j].x for j in J) < 0.5:  # No recicla en ningún sitio
                sitios_no_RN.append(i)
        
        # Crear diccionario de candidatos
        candidatos_en_radio = {}
        for i in sitios_no_RN:
            candidatos_en_radio[i] = Ji[i]
        
        # Segundo: construir la tabla
        sitios_no_reciclaron = []
        
        for i in sitios_no_RN:
            # De esos candidatos, ¿cuáles están ocupados (tienen contenedor)?
            sitios_ocupados = []
            for j in candidatos_en_radio[i]:
                if any(y[j,k].x > 0.5 for k in K):
                    sitios_ocupados.append(j)
            
            sitios_no_reciclaron.append({
                'Sitio_NR': i,
                'Demanda_kg': round(q[i], 2),
                'Sitios_Candidatos': ', '.join(candidatos_en_radio[i]) if candidatos_en_radio[i] else 'Ninguno',
                'Sitios_Ocupados': ', '.join(sitios_ocupados) if sitios_ocupados else 'Ninguno',
                'Num_Candidatos': len(candidatos_en_radio[i]),
                'Num_Ocupados': len(sitios_ocupados)
            })
        
        df_no_reciclaron = pd.DataFrame(sitios_no_reciclaron)
        
        if len(df_no_reciclaron) > 0:
            df_no_reciclaron = df_no_reciclaron.sort_values('Demanda_kg', ascending=False)
            
            total_row = pd.DataFrame({
                'Sitio_NR': ['TOTAL'],
                'Demanda_kg': [df_no_reciclaron['Demanda_kg'].sum()],
                'Sitios_Candidatos': [''],
                'Sitios_Ocupados': [''],
                'Num_Candidatos': [''],
                'Num_Ocupados': ['']
            })
            df_no_reciclaron = pd.concat([df_no_reciclaron, total_row], ignore_index=True)
        
        df_no_reciclaron.to_excel(writer, sheet_name='Sitios No Reciclaron', index=False)
        
        # ====================================================================
        # FORMATEAR
        # ====================================================================
        
        from openpyxl.styles import Font, PatternFill, Alignment
        
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            for cell in worksheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center")
    
    print(f"Excel generado: 3 hojas creadas")


# ============================================================================
# FIN
# ============================================================================

if __name__ == "__main__":
    print("Módulo Resultados cargado correctamente")
    print("Uso: F_O, df_sitios, overflow, stats = generar_resultados(...)")