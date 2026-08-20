import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# FUNCION PRINCIPAL
# ============================================================================

def generar_resultados(model, x, y, w, q, I, J, K, d, f, c_nr, phi, r,
                       df_demandas, df_candidatos, 
                       nombre_archivo="reporte_resultados.pdf"):
    """
    Genera reporte PDF + Excel con resultados del modelo RBLP.
    
    MODIFICADO: Ahora usa w[i,j] (proporción utilizada)
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
    # EXTRAER COSTOS Y TIEMPO
    # ========================================================================
    
    try:
        costo_instalacion = sum(y[j,k].x * f[j,k] for j in J for k in K)
        
        # Costo no reciclar (nueva fórmula con w)
        costo_no_reciclar = sum(q[i] * c_nr[i] * (1 - sum(w[i,j].x for j in J)) for i in I)
        
        print(f"\nDESGLOSE DE COSTOS:")
        print(f"  - Instalación: ${costo_instalacion:,.2f}")
        print(f"  - No Reciclar: ${costo_no_reciclar:,.2f}")
        print(f"  - TOTAL F.O: ${model.ObjVal:,.2f}")
    except Exception as e:
        print(f"ERROR al calcular costos: {e}")
        costo_instalacion = costo_no_reciclar = 0
    
    # Extraer tiempo de ejecución y gap
    try:
        tiempo_ejecucion = model.Runtime  # En segundos
        gap = model.MIPGap * 100 if hasattr(model, 'MIPGap') else 0  # En porcentaje
    except:
        tiempo_ejecucion = 0
        gap = 0
    
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
                # CORREGIDO: residuos_recibidos = suma ponderada por w[i,j]
                residuos_recibidos = sum(w[i,j].x * q[i] for i in I)
            except:
                residuos_recibidos = 0
            
            try:
                # Residuos depositados y regresados usando w[i,j]
                residuos_depositados = sum(w[i,j].x * q[i] for i in I)
                # CORREGIDO: solo contar regresados de demandas asignadas a este sitio
                residuos_regresados = sum((1 - w[i,j].x) * q[i] * x[i,j].x for i in I)
            except:
                residuos_depositados = 0
                residuos_regresados = 0
            
            coords = df_candidatos[df_candidatos['id_unico'] == j]
            if len(coords) > 0:
                lat = coords['latitud'].values[0]
                lon = coords['longitud'].values[0]
            else:
                lat, lon = None, None
            
            # Residuos efectivamente reciclados = depositados
            utilizacion = (residuos_depositados / capacidad_sitio * 100) if capacidad_sitio > 0 else 0
            
            sitios_activados.append({
                'sitio': j,
                'tipo_contenedor': contenedor_instalado,
                'capacidad': capacidad_sitio,
                'costo_fijo': costo_fijo_sitio,
                'residuos_recibidos': residuos_recibidos,
                'residuos_depositados': residuos_depositados,
                'residuos_regresados': residuos_regresados,
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
    
    # CORREGIDO: Calcular desde los datos originales para consistencia
    total_regresados = sum(q[i] * (1 - sum(w[i,j].x for j in J)) for i in I)
    residuos_reciclados_efectivos = sum(q[i] * sum(w[i,j].x for j in J) for i in I)
    
    estadisticas = {
        'es_optima': es_optima,
        'status': model.Status,
        'status_msg': status_msg,
        'funcion_objetivo': model.ObjVal,
        'costo_instalacion': costo_instalacion,
        'costo_no_reciclar': costo_no_reciclar,
        'tiempo_ejecucion': tiempo_ejecucion,
        'gap': gap,
        'total_sitios_activados': len(df_sitios),
        'total_residuos': sum(q[i] for i in I),
        'residuos_reciclados': residuos_reciclados_efectivos,
        'residuos_regresados': total_regresados,
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
    # GENERAR PDF
    # ========================================================================
    
    print(f"\nGenerando PDF: {nombre_archivo}")
    
    with PdfPages(nombre_archivo) as pdf:
        _generar_pagina_resumen(pdf, estadisticas, df_sitios, d)
        _generar_mapa_sitios_activados(pdf, df_sitios, df_demandas, d)
        _generar_mapa_regresados(pdf, df_sitios, df_candidatos)
        _generar_mapa_asignaciones(pdf, df_asignaciones, df_sitios)
        
        d_pdf = pdf.infodict()
        d_pdf['Title'] = 'Reporte de Resultados - Modelo RBLP'
        d_pdf['Author'] = 'Sistema de Optimizacion'
        d_pdf['CreationDate'] = datetime.now()
    
    # ========================================================================
    # GENERAR EXCEL
    # ========================================================================
    
    try:
        nombre_excel = nombre_archivo.replace('.pdf', '.xlsx')
        generar_excel_detallado(df_sitios, df_asignaciones, x, y, w, q, I, J, K, d,
                               estadisticas, phi, r, nombre_archivo=nombre_excel)
    except Exception as e:
        print(f"\nError generando Excel: {e}")
        import traceback
        traceback.print_exc()
    
    return (estadisticas['funcion_objetivo'], df_sitios, estadisticas['residuos_regresados'], estadisticas)


# ============================================================================
# FUNCIONES AUXILIARES PARA PDF
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
Tiempo de ejecución: {stats['tiempo_ejecucion']:.2f} segundos
Gap: {stats['gap']:.2f}%

------------------------------------------------------------------
 COSTOS (USD)
------------------------------------------------------------------
   Instalación:          ${stats['costo_instalacion']:>15,.2f}
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
   Regresados:           {stats['residuos_regresados']:>12,.2f} kg
   Tasa reciclaje:       {stats['tasa_reciclaje']:>12,.2f} %

------------------------------------------------------------------
 EFICIENCIA
------------------------------------------------------------------
   Utilización promedio: {stats['utilizacion_promedio']:.2f}%
"""
    
    if len(df_sitios) > 0:
        sitio_max = df_sitios.loc[df_sitios['residuos_depositados'].idxmax(), 'sitio']
        max_carga = df_sitios['residuos_depositados'].max()
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
            'residuos_depositados': 'sum',
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


def _generar_mapa_regresados(pdf, df_sitios, df_candidatos):
    """Pagina 3: Residuos Regresados"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8))
    fig.suptitle('ANÁLISIS DE RESIDUOS REGRESADOS', fontsize=14, fontweight='bold')
    
    ax1.scatter(df_candidatos['longitud'], df_candidatos['latitud'],
                c='lightgray', s=50, alpha=0.4, label='No activados')
    
    if len(df_sitios) > 0:
        df_sin = df_sitios[df_sitios['residuos_regresados'] < 0.01]
        df_con = df_sitios[df_sitios['residuos_regresados'] >= 0.01]
        
        if len(df_sin) > 0:
            ax1.scatter(df_sin['longitud'], df_sin['latitud'],
                       c='green', s=200, alpha=0.6,
                       label=f'Sin regresados ({len(df_sin)})', zorder=5)
        
        if len(df_con) > 0:
            ax1.scatter(df_con['longitud'], df_con['latitud'],
                       c='red', s=200, alpha=0.8,
                       label=f'Con regresados ({len(df_con)})', zorder=5)
    
    ax1.set_xlabel('Longitud')
    ax1.set_ylabel('Latitud')
    ax1.set_title('Mapa de Residuos Regresados')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    ax2.axis('off')
    stats_text = "ESTADÍSTICAS DE RESIDUOS REGRESADOS\n\n"
    if len(df_sitios) > 0:
        total_regresados = df_sitios['residuos_regresados'].sum()
        sitios_regresados = len(df_sitios[df_sitios['residuos_regresados'] >= 0.01])
        stats_text += f"Total regresados: {total_regresados:.2f} kg\n"
        stats_text += f"Sitios afectados: {sitios_regresados}\n"
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
# FUNCIÓN EXCEL - 5 HOJAS
# ============================================================================

def generar_excel_detallado(df_sitios, df_asignaciones, x, y, w, q, I, J, K, d, 
                           estadisticas, phi, r, nombre_archivo="resultados.xlsx"):
    """
    Genera Excel con 5 hojas:
    1. Resumen
    2. Detalle Candidatos
    3. Residuos Regresados
    4. Tiempo y Gap
    5. Variable Y
    """
    
    print(f"\nGenerando Excel: {nombre_archivo}")
    
    # Construir Ji para cada sitio de demanda
    Ji = {}
    for i in I:
        Ji[i] = []
        for j in J:
            if r[i] > phi[i,j]:
                Ji[i].append(j)
    
    with pd.ExcelWriter(nombre_archivo, engine='openpyxl') as writer:
        
        # ====================================================================
        # HOJA 1: RESUMEN
        # ====================================================================
        
        residuos_no_reciclados = estadisticas['total_residuos'] - estadisticas['residuos_reciclados']
        
        resumen_data = {
            'Indicador': [
                'Función Objetivo (USD)',
                'Costo Instalación (USD)',
                'Costo No Reciclar (USD)',
                '',
                'Sitios Activados',
                'Total Residuos (kg)',
                'Reciclados (kg)',
                'NO Reciclados (kg)',
                'Tasa Reciclaje (%)',
                '',
                'Status',
                'Óptima'
            ],
            'Valor': [
                f"${estadisticas['funcion_objetivo']:,.2f}",
                f"${estadisticas['costo_instalacion']:,.2f}",
                f"${estadisticas['costo_no_reciclar']:,.2f}",
                '',
                estadisticas['total_sitios_activados'],
                f"{estadisticas['total_residuos']:,.2f}",
                f"{estadisticas['residuos_reciclados']:,.2f}",
                f"{residuos_no_reciclados:,.2f}",
                f"{estadisticas['tasa_reciclaje']:.2f}",
                '',
                estadisticas['status_msg'],
                'SI' if estadisticas['es_optima'] else 'NO'
            ]
        }
        
        df_resumen = pd.DataFrame(resumen_data)
        df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
        
        # ====================================================================
        # HOJA 2: DETALLE CANDIDATOS
        # ====================================================================
        
        detalle_candidatos = []
        
        for j in J:
            for k in K:
                try:
                    if y[j,k].x > 0.5:
                        # CORREGIDO: Total recibidos = suma ponderada por w[i,j]
                        residuos_recibidos = sum(w[i,j].x * q[i] for i in I)
                        capacidad = d[j,k]
                        
                        demandas_asignadas = [i for i in I if x[i,j].x > 0.5]
                        
                        if demandas_asignadas:
                            for i in demandas_asignadas:
                                proporcion_usada = w[i,j].x if (i, j) in w else 0
                                detalle_candidatos.append({
                                    'Candidato': j,
                                    'Candidato_Activo': 'SI',
                                    'Demanda_Asignada': i,
                                    'Residuos_Demanda': round(q[i], 2),
                                    'Proporcion_Depositada': round(proporcion_usada, 4),
                                    'Depositados_kg': round(proporcion_usada * q[i], 2),
                                    'Regresados_kg': round((1 - proporcion_usada) * q[i], 2),
                                    'Tipo_Contenedor': k,
                                    'Capacidad_Contenedor': capacidad,
                                    'Total_Recibidos': round(residuos_recibidos, 2)
                                })
                        else:
                            detalle_candidatos.append({
                                'Candidato': j,
                                'Candidato_Activo': 'SI',
                                'Demanda_Asignada': 'Ninguna',
                                'Residuos_Demanda': 0,
                                'Proporcion_Depositada': 0,
                                'Depositados_kg': 0,
                                'Regresados_kg': 0,
                                'Tipo_Contenedor': k,
                                'Capacidad_Contenedor': capacidad,
                                'Total_Recibidos': round(residuos_recibidos, 2)
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
                    'Proporcion_Depositada': 0,
                    'Depositados_kg': 0,
                    'Regresados_kg': 0,
                    'Tipo_Contenedor': 'N/A',
                    'Capacidad_Contenedor': 0,
                    'Total_Recibidos': 0
                })
        
        df_detalle = pd.DataFrame(detalle_candidatos)
        df_detalle = df_detalle.sort_values(['Candidato_Activo', 'Candidato'], 
                                             ascending=[False, True])
        df_detalle.to_excel(writer, sheet_name='Detalle Candidatos', index=False)
        
        # ====================================================================
        # HOJA 3: RESIDUOS REGRESADOS
        # ====================================================================
        
        residuos_regresados_data = []
        
        for i in I:
            # Calcular total de residuos regresados desde este sitio i
            total_regresado_i = q[i] * (1 - sum(w[i,j].x for j in J))
            
            # Solo incluir si hay residuos regresados significativos
            if total_regresado_i > 0.01:
                # Calcular también lo depositado
                total_depositado_i = q[i] * sum(w[i,j].x for j in J)
                
                # Identificar a qué sitios j fue asignado
                sitios_visitados = []
                proporciones = []
                for j in J:
                    if x[i,j].x > 0.5:
                        sitios_visitados.append(j)
                        proporciones.append(f"{w[i,j].x:.2%}")
                
                # Candidatos disponibles para este sitio i
                candidatos_disponibles = Ji.get(i, [])
                
                # De esos candidatos, ¿cuáles están ocupados?
                sitios_ocupados = []
                for j in candidatos_disponibles:
                    if any(y[j,k].x > 0.5 for k in K):
                        sitios_ocupados.append(j)
                
                residuos_regresados_data.append({
                    'Sitio_Demanda': i,
                    'Sitios_Visitados': ', '.join(map(str, sitios_visitados)) if sitios_visitados else 'Ninguno',
                    'Proporcion_Depositada': ', '.join(proporciones) if proporciones else 'N/A',
                    'Cantidad_Regresada_kg': round(total_regresado_i, 2),
                    'Cantidad_Depositada_kg': round(total_depositado_i, 2),
                    'Demanda_Original_kg': round(q[i], 2),
                    'Sitios_Candidatos': ', '.join(map(str, candidatos_disponibles)) if candidatos_disponibles else 'Ninguno',
                    'Sitios_Ocupados': ', '.join(map(str, sitios_ocupados)) if sitios_ocupados else 'Ninguno',
                    'Num_Candidatos': len(candidatos_disponibles),
                    'Num_Ocupados': len(sitios_ocupados)
                })
        
        df_regresados = pd.DataFrame(residuos_regresados_data)
        
        if len(df_regresados) > 0:
            df_regresados = df_regresados.sort_values('Cantidad_Regresada_kg', ascending=False)
            
            total_row = pd.DataFrame({
                'Sitio_Demanda': ['TOTAL'],
                'Sitios_Visitados': [''],
                'Proporcion_Depositada': [''],
                'Cantidad_Regresada_kg': [df_regresados['Cantidad_Regresada_kg'].sum()],
                'Cantidad_Depositada_kg': [df_regresados['Cantidad_Depositada_kg'].sum()],
                'Demanda_Original_kg': [df_regresados['Demanda_Original_kg'].sum()],
                'Sitios_Candidatos': [''],
                'Sitios_Ocupados': [''],
                'Num_Candidatos': [''],
                'Num_Ocupados': ['']
            })
            df_regresados = pd.concat([df_regresados, total_row], ignore_index=True)
        
        df_regresados.to_excel(writer, sheet_name='Residuos_Regresados', index=False)
        
        # ====================================================================
        # HOJA 4: TIEMPO Y GAP
        # ====================================================================
        
        tiempo_gap_data = {
            'Métrica': [
                'Tiempo de Ejecución (segundos)',
                'Gap (%)',
                'Status',
                'Solución Óptima'
            ],
            'Valor': [
                f"{estadisticas['tiempo_ejecucion']:.2f}",
                f"{estadisticas['gap']:.4f}",
                estadisticas['status_msg'],
                'SI' if estadisticas['es_optima'] else 'NO'
            ]
        }
        
        df_tiempo_gap = pd.DataFrame(tiempo_gap_data)
        df_tiempo_gap.to_excel(writer, sheet_name='Tiempo_Gap', index=False)
        
        # ====================================================================
        # HOJA 5: VARIABLE Y
        # ====================================================================
        
        variable_y_data = []
        
        for j in J:
            for k in K:
                try:
                    valor = y[j,k].x
                    variable_y_data.append({
                        'J (Candidato)': j,
                        'K (Tipo_Contenedor)': k,
                        'y[j,k]': round(valor, 6)
                    })
                except:
                    variable_y_data.append({
                        'J (Candidato)': j,
                        'K (Tipo_Contenedor)': k,
                        'y[j,k]': 0
                    })
        
        df_variable_y = pd.DataFrame(variable_y_data)
        df_variable_y = df_variable_y.sort_values(['J (Candidato)', 'K (Tipo_Contenedor)'])
        df_variable_y.to_excel(writer, sheet_name='Variable_Y', index=False)
        
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
    
    print(f"Excel generado: 5 hojas creadas")
    
    # ====================================================================
    # VERIFICACIÓN DE CONSISTENCIA
    # ====================================================================
    print(f"\nVERIFICACIÓN DE CONSISTENCIA:")
    print(f"  NO Reciclados en Resumen: {estadisticas['residuos_regresados']:.2f} kg")
    if len(df_regresados) > 0:
        total_hoja3 = df_regresados[df_regresados['Sitio_Demanda'] == 'TOTAL']['Cantidad_Regresada_kg'].values[0]
        print(f"  NO Reciclados en Hoja 3:  {total_hoja3:.2f} kg")
        diferencia = abs(estadisticas['residuos_regresados'] - total_hoja3)
        if diferencia < 0.01:
            print("  ✓ Las cifras coinciden correctamente")
        else:
            print(f"  ⚠ ADVERTENCIA: Diferencia de {diferencia:.2f} kg")


# ============================================================================
# FIN
# ============================================================================

if __name__ == "__main__":
    print("Módulo Resultados cargado correctamente")
    print("Uso: F_O, df_sitios, regresados, stats = generar_resultados(...)")