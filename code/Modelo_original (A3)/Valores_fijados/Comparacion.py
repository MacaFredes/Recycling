# -*- coding: utf-8 -*-
# Evaluación de soluciones A1 y A2 con overflow permitido (A1-D, A2-D)
# Este script toma las ubicaciones optimizadas por A1 y A2, las fija en el modelo A3,
# y evalúa qué pasa cuando se permite overflow.

import gurobipy as gp
from gurobipy import GRB
import pandas as pd

# Importar instancias
import Instancia
import Resultados

def cargar_solucion_y_desde_excel(archivo_excel):
    """
    Lee las variables Y desde el Excel y las devuelve en formato diccionario.
    """
    df_y = pd.read_excel(archivo_excel, sheet_name='Variable_Y')
    
    # Guardamos todas las Y (tanto 0 como 1)
    y_fixed = {}
    for idx, row in df_y.iterrows():
        candidato = row['J (Candidato)']
        tipo_k = int(row['K (Tipo_Contenedor)'])  # Asegurar que K sea int
        valor = row['y[j,k]']
        
        # Guardamos el valor fijo (1 si > 0.5, sino 0)
        y_fixed[(candidato, tipo_k)] = 1 if valor > 0.5 else 0
    
    # Mostrar resumen
    activados = sum(1 for v in y_fixed.values() if v == 1)
    print(f"  Cargadas {len(y_fixed)} variables Y ({activados} activadas)")
    
    return y_fixed


def evaluar_con_overflow(y_solucion, nombre_output="evaluacion"):
    """
    Evalúa una solución dada (Y fijas) permitiendo overflow.
    Usa la estructura exacta del modelo A3.
    
    Args:
        y_solucion: dict con {(j,k): valor} donde valor es 0 o 1
        nombre_output: nombre del archivo de salida
    
    Returns:
        Resultados del modelo con overflow
    """
    
    # Cargar datos (igual que en modelo A3)
    J = Instancia.J  
    I = Instancia.I  
    K = Instancia.K  
    d = Instancia.d  
    phi = Instancia.phi 
    q = Instancia.q 
    r = Instancia.r 
    f = Instancia.f 
    c_dump = Instancia.c_dump 
    c_nr = Instancia.c_nr 
    p = Instancia.p 
    df_candidatos = Instancia.df_candidatos
    
    print(f"\n{'='*60}")
    print(f"EVALUANDO: {nombre_output}")
    print(f"{'='*60}")
    print("DATOS CARGADOS")
    
    # Crear modelo (igual que A3)
    m = gp.Model(f'Evaluacion_{nombre_output}')
    
    # Variables (igual que A3)
    print("Iniciando variables")
    x = m.addVars(I, J, vtype=GRB.BINARY, lb=0)
    y = m.addVars(J, K, vtype=GRB.BINARY, lb=0)  # Las creamos como variables...
    z = m.addVars(J, vtype=GRB.CONTINUOUS, lb=0)  # Overflow (igual que A3)
    print("Finalizando variables")
    
    # CLAVE: Fijar las Y según la solución dada
    print("Fijando variables Y...")
    for (j, k) in y_solucion.keys():
        m.addConstr(y[j, k] == y_solucion[(j, k)])  # Fijamos cada Y
    
    n_activados = sum(y_solucion.values())
    print(f"  -> {n_activados} contenedores fijados como activados")
    
    # Función objetivo (igual que A3)
    costo_dump = gp.quicksum(z[j] * c_dump[j] for j in J)
    costo_NR = gp.quicksum(q[i] * c_nr[i] * (1 - gp.quicksum(x[i,j] for j in J)) for i in I)
    
    m.setObjective(costo_dump + costo_NR, GRB.MINIMIZE)
    
    # Restricciones (igual que A3)
    print("Iniciando restricciones")
    
    Ji = {}
    for i in I:
        Ji[i] = []
        for j in J:
            if r[i] > phi[i,j]:
                Ji[i].append(j)
    
    # Restricción de presupuesto (aunque ya está fija, la mantenemos)
    m.addConstr(gp.quicksum(y[j,k] * f[j,k] for j in J for k in K) <= p)
    
    for i in I:
        m.addConstr(gp.quicksum(x[i,j] for j in J) <= 1)
        m.addConstr(gp.quicksum(x[i,j] for j in J if j not in Ji[i]) == 0)
        
        for j in Ji[i]:
            m.addConstr(x[i,j] <= gp.quicksum(y[j,k] for k in K))
            m.addConstr(gp.quicksum(y[j,k] for k in K) <= gp.quicksum(x[i,jp] for jp in Ji[i] 
                                      if phi[i,jp] <= phi[i,j]))
    
    for j in J:
        m.addConstr(gp.quicksum(y[j,k] for k in K) <= 1)
        # Balance con overflow (igual que A3)
        m.addConstr(gp.quicksum(q[i]*x[i,j] for i in I) <= gp.quicksum(d[j,k]*y[j,k] for k in K) + z[j])
    
    print("Finaliza restricciones")
    
    # Parámetros de solver (igual que A3)
    m.setParam(GRB.Param.TimeLimit, 2500)
    m.setParam(GRB.Param.Cuts, 0)
    m.setParam(GRB.Param.Seed, 123)
    
    # Resolver
    m.optimize()
    
    # Reportar resultados
    if m.status == GRB.OPTIMAL or m.status == GRB.TIME_LIMIT:
        print(f"\n{'='*60}")
        print(f"RESULTADOS {nombre_output}")
        print(f"{'='*60}")
        
        # Calcular componentes del costo
        costo_dump_val = sum(z[j].x * c_dump[j] for j in J)
        costo_NR_val = sum(q[i] * c_nr[i] * (1 - sum(x[i,j].x for j in J)) for i in I)
        costo_inst_val = sum(y[j,k].x * f[j,k] for j in J for k in K)
        
        overflow_kg = sum(z[j].x for j in J)
        no_recicla_kg = sum(q[i] * (1 - sum(x[i,j].x for j in J)) for i in I)
        recicla_kg = sum(q[i] * sum(x[i,j].x for j in J) for i in I)
        
        print(f"Función Objetivo: ${m.objVal:.2f}")
        print(f"  - Costo instalación: ${costo_inst_val:.2f}")
        print(f"  - Costo overflow: ${costo_dump_val:.2f}")
        print(f"  - Costo no reciclar: ${costo_NR_val:.2f}")
        print(f"\nCantidades:")
        print(f"  - Reciclado: {recicla_kg:.2f} kg")
        print(f"  - NO reciclado: {no_recicla_kg:.2f} kg")
        print(f"  - Overflow: {overflow_kg:.2f} kg")
        print(f"  - Contenedores abiertos: {sum(1 for j in J for k in K if y[j,k].x > 0.5)}")
        
        # Generar resultados usando el módulo existente
        try:
            F_O, df_sitios, overflow, stats = Resultados.generar_resultados(
                model=m, x=x, y=y, z=z, q=q, I=I, J=J, K=K, d=d, f=f, 
                c_dump=c_dump, c_nr=c_nr, phi=phi, r=r,
                df_demandas=Instancia.df_demandas,
                df_candidatos=df_candidatos,
                nombre_archivo=f"mi_reporte_{nombre_output}.pdf" 
            )
            print(f"\n-> Resultados guardados en mi_reporte_{nombre_output}.pdf")
        except Exception as e:
            print(f"\n-> No se pudo generar PDF: {e}")
        
        return {
            'nombre': nombre_output,
            'obj_value': m.objVal,
            'instalacion': costo_inst_val,
            'overflow': costo_dump_val,
            'no_reciclar': costo_NR_val,
            'overflow_kg': overflow_kg,
            'no_recicla_kg': no_recicla_kg,
            'recicla_kg': recicla_kg,
            'n_contenedores': sum(1 for j in J for k in K if y[j,k].x > 0.5),
            'model': m,
            'x': x,
            'y': y,
            'z': z
        }
    else:
        print(f"\n-> No se encontró solución (status: {m.status})")
        return None


if __name__ == "__main__":
    
    print("\n" + "="*80)
    print("ANALISIS DE COSTO OCULTO POR NO CONSIDERAR OVERFLOW EN LA PLANIFICACION")
    print("="*80)
    print("\nEste analisis compara:")
    print("  - A1: Solucion optimizada sin overflow (usuario no va si esta lleno)")
    print("  - A1-D: Mismas ubicaciones de A1, pero evaluadas con overflow permitido")
    print("\nLa diferencia A1-D - A1 muestra el 'costo oculto' de planear sin overflow\n")
    
    # ============================================================================
    # CARGAR SOLUCIONES ORIGINALES (A1, A2, A3)
    # ============================================================================
    print("\n" + "="*60)
    print("CARGANDO SOLUCIONES ORIGINALES")
    print("="*60)
    
    # Leer valores de A1
    df_A1 = pd.read_excel('mi_reporte_A1.xlsx', sheet_name='Resumen')
    A1_obj = float(df_A1[df_A1['Indicador'] == 'Función Objetivo (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    A1_inst = float(df_A1[df_A1['Indicador'] == 'Costo Instalación (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    A1_nr = float(df_A1[df_A1['Indicador'] == 'Costo No Reciclar (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    
    print(f"\nA1 (sin overflow en planning):")
    print(f"  F.O. = ${A1_obj:.2f}")
    print(f"  - Instalacion: ${A1_inst:.2f}")
    print(f"  - No Reciclar: ${A1_nr:.2f}")
    print(f"  - Overflow: $0.00 (no permitido en modelo)")
    
    # Leer valores de A2
    df_A2 = pd.read_excel('mi_reporte_A2.xlsx', sheet_name='Resumen')
    A2_obj = float(df_A2[df_A2['Indicador'] == 'Función Objetivo (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    A2_inst = float(df_A2[df_A2['Indicador'] == 'Costo Instalación (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    A2_nr = float(df_A2[df_A2['Indicador'] == 'Costo No Reciclar (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    
    print(f"\nA2 (sin overflow en planning):")
    print(f"  F.O. = ${A2_obj:.2f}")
    print(f"  - Instalacion: ${A2_inst:.2f}")
    print(f"  - No Reciclar: ${A2_nr:.2f}")
    print(f"  - Overflow: $0.00 (no permitido en modelo)")
    
    # Leer valores de A3
    df_A3 = pd.read_excel('mi_reporte_A3.xlsx', sheet_name='Resumen')
    A3_obj = float(df_A3[df_A3['Indicador'] == 'Función Objetivo (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    A3_inst = float(df_A3[df_A3['Indicador'] == 'Costo Instalación (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    A3_overflow = float(df_A3[df_A3['Indicador'] == 'Costo Overflow (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    A3_nr = float(df_A3[df_A3['Indicador'] == 'Costo No Reciclar (USD)']['Valor'].values[0].replace('$','').replace(',',''))
    
    print(f"\nA3 (CON overflow en planning):")
    print(f"  F.O. = ${A3_obj:.2f}")
    print(f"  - Instalacion: ${A3_inst:.2f}")
    print(f"  - Overflow: ${A3_overflow:.2f}")
    print(f"  - No Reciclar: ${A3_nr:.2f}")
    
    # ============================================================================
    # EVALUAR A1 CON OVERFLOW (A1-D)
    # ============================================================================
    y_A1 = cargar_solucion_y_desde_excel('mi_reporte_A1.xlsx')
    resultado_A1_D = evaluar_con_overflow(y_A1, nombre_output="A1-D")
    
    # ============================================================================
    # EVALUAR A2 CON OVERFLOW (A2-D)
    # ============================================================================
    y_A2 = cargar_solucion_y_desde_excel('mi_reporte_A2.xlsx')
    resultado_A2_D = evaluar_con_overflow(y_A2, nombre_output="A2-D")
    
    # ============================================================================
    # TABLA COMPARATIVA FINAL
    # ============================================================================
    if resultado_A1_D and resultado_A2_D:
        print("\n" + "="*80)
        print("TABLA COMPARATIVA DE RESULTADOS")
        print("="*80)
        
        print("\n{:<15} {:<12} {:<12} {:<12} {:<12} {:<12}".format(
            "Modelo", "F.O. ($)", "Install ($)", "Overflow ($)", "No Recic ($)", "Diff vs A3 (%)"
        ))
        print("-" * 80)
        print("NOTA: La instalacion NO esta incluida en la F.O., solo se muestra como referencia")
        print("-" * 80)
        
        # A1
        print("{:<15} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f} {:<12}".format(
            "A1", A1_obj, A1_inst, 0.0, A1_nr, "-"
        ))
        
        # A1-D
        diff_A1D = ((resultado_A1_D['obj_value'] - A1_obj) / A1_obj * 100) if A1_obj > 0 else 0
        diff_A1D_vs_A3 = ((resultado_A1_D['obj_value'] - A3_obj) / A3_obj * 100) if A3_obj > 0 else 0
        print("{:<15} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f}".format(
            "A1-D", resultado_A1_D['obj_value'], resultado_A1_D['instalacion'], 
            resultado_A1_D['overflow'], resultado_A1_D['no_reciclar'], diff_A1D_vs_A3
        ))
        
        print("-" * 80)
        
        # A2
        print("{:<15} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f} {:<12}".format(
            "A2", A2_obj, A2_inst, 0.0, A2_nr, "-"
        ))
        
        # A2-D
        diff_A2D = ((resultado_A2_D['obj_value'] - A2_obj) / A2_obj * 100) if A2_obj > 0 else 0
        diff_A2D_vs_A3 = ((resultado_A2_D['obj_value'] - A3_obj) / A3_obj * 100) if A3_obj > 0 else 0
        print("{:<15} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f}".format(
            "A2-D", resultado_A2_D['obj_value'], resultado_A2_D['instalacion'], 
            resultado_A2_D['overflow'], resultado_A2_D['no_reciclar'], diff_A2D_vs_A3
        ))
        
        print("-" * 80)
        
        # A3
        print("{:<15} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f} {:<12.2f}".format(
            "A3", A3_obj, A3_inst, A3_overflow, A3_nr, 0.0
        ))
        
        print("\n" + "="*80)
        print("CONCLUSIONES")
        print("="*80)
        print("\nNOTA: F.O. = Costo Overflow + Costo No Reciclar")
        print("      (La instalacion es fija y no se incluye en la optimizacion)")
        
        print(f"\n1. COSTO OCULTO (subestimacion de costos por no planear con overflow):")
        print(f"   - A1 -> A1-D: +${resultado_A1_D['obj_value'] - A1_obj:.2f} (+{diff_A1D:.1f}%)")
        print(f"   - A2 -> A2-D: +${resultado_A2_D['obj_value'] - A2_obj:.2f} (+{diff_A2D:.1f}%)")
        
        print(f"\n2. COMPARACION CON MODELO PROPUESTO (A3):")
        print(f"   - A1-D vs A3: ${resultado_A1_D['obj_value'] - A3_obj:+.2f} ({diff_A1D_vs_A3:+.1f}%)")
        print(f"   - A2-D vs A3: ${resultado_A2_D['obj_value'] - A3_obj:+.2f} ({diff_A2D_vs_A3:+.1f}%)")
        
        print(f"\n3. OVERFLOW GENERADO:")
        print(f"   - A1-D: {resultado_A1_D['overflow_kg']:.2f} kg (${resultado_A1_D['overflow']:.2f})")
        print(f"   - A2-D: {resultado_A2_D['overflow_kg']:.2f} kg (${resultado_A2_D['overflow']:.2f})")
        print(f"   - A3: {df_A3[df_A3['Indicador'] == 'Overflow Total (kg)']['Valor'].values[0]} kg (${A3_overflow:.2f})")
        
        print("\n" + "="*80)
        
        # ========================================================================
        # VALIDACIONES DE COHERENCIA
        # ========================================================================
        print("\n" + "="*80)
        print("VALIDACIONES DE COHERENCIA")
        print("="*80)
        
        validaciones_ok = True
        
        # Validación 1: La instalación debe ser la misma en A1, A1-D (Y fijas)
        if abs(resultado_A1_D['instalacion'] - A1_inst) > 0.01:
            print(f"WARNING: Costo instalacion A1-D (${resultado_A1_D['instalacion']:.2f}) != A1 (${A1_inst:.2f})")
            validaciones_ok = False
        else:
            print(f"OK: A1-D mantiene misma instalacion que A1: ${resultado_A1_D['instalacion']:.2f}")
        
        # Validación 2: La instalación debe ser la misma en A2, A2-D (Y fijas)
        if abs(resultado_A2_D['instalacion'] - A2_inst) > 0.01:
            print(f"WARNING: Costo instalacion A2-D (${resultado_A2_D['instalacion']:.2f}) != A2 (${A2_inst:.2f})")
            validaciones_ok = False
        else:
            print(f"OK: A2-D mantiene misma instalacion que A2: ${resultado_A2_D['instalacion']:.2f}")
        
        # Validación 3: F.O. = Overflow + No Reciclar
        fo_calculada_A1D = resultado_A1_D['overflow'] + resultado_A1_D['no_reciclar']
        if abs(fo_calculada_A1D - resultado_A1_D['obj_value']) > 0.01:
            print(f"WARNING: F.O. A1-D ({resultado_A1_D['obj_value']:.2f}) != Overflow + No Reciclar ({fo_calculada_A1D:.2f})")
            validaciones_ok = False
        else:
            print(f"OK: F.O. A1-D = Overflow + No Reciclar: ${resultado_A1_D['obj_value']:.2f}")
        
        # Validación 4: F.O. = Overflow + No Reciclar
        fo_calculada_A2D = resultado_A2_D['overflow'] + resultado_A2_D['no_reciclar']
        if abs(fo_calculada_A2D - resultado_A2_D['obj_value']) > 0.01:
            print(f"WARNING: F.O. A2-D ({resultado_A2_D['obj_value']:.2f}) != Overflow + No Reciclar ({fo_calculada_A2D:.2f})")
            validaciones_ok = False
        else:
            print(f"OK: F.O. A2-D = Overflow + No Reciclar: ${resultado_A2_D['obj_value']:.2f}")
        
        # Validación 5: A1-D debería tener overflow
        if abs(resultado_A1_D['obj_value'] - A1_obj) > 0.01:
            if resultado_A1_D['overflow_kg'] < 0.01:
                print(f"WARNING: A1-D tiene F.O. diferente pero overflow = 0")
                validaciones_ok = False
            else:
                print(f"OK: A1-D genera overflow: {resultado_A1_D['overflow_kg']:.2f} kg")
        else:
            print(f"OK: A1-D tiene misma F.O. que A1 (diferencia < $0.01)")
        
        # Validación 6: Número de contenedores debe ser 10
        if resultado_A1_D['n_contenedores'] != 10:
            print(f"WARNING: A1-D tiene {resultado_A1_D['n_contenedores']} contenedores (esperado: 10)")
            validaciones_ok = False
        else:
            print(f"OK: A1-D mantiene 10 contenedores")
            
        if resultado_A2_D['n_contenedores'] != 10:
            print(f"WARNING: A2-D tiene {resultado_A2_D['n_contenedores']} contenedores (esperado: 10)")
            validaciones_ok = False
        else:
            print(f"OK: A2-D mantiene 10 contenedores")
        
        if validaciones_ok:
            print("\n=== TODAS LAS VALIDACIONES PASARON ===")
        else:
            print("\n=== ALGUNAS VALIDACIONES FALLARON - REVISAR DATOS ===")
        
        # ========================================================================
        # GUARDAR RESULTADOS EN EXCEL
        # ========================================================================
        print("\n" + "="*80)
        print("GUARDANDO RESULTADOS EN EXCEL")
        print("="*80)
        
        # Tabla comparativa principal
        tabla_comp = pd.DataFrame({
            'Modelo': ['A1', 'A1-D', 'A2', 'A2-D', 'A3'],
            'Descripcion': [
                'Sin overflow (binario)',
                'A1 evaluado con overflow',
                'Sin overflow (fraccional)',
                'A2 evaluado con overflow',
                'Con overflow (propuesto)'
            ],
            'F.O. (USD)': [A1_obj, resultado_A1_D['obj_value'], A2_obj, resultado_A2_D['obj_value'], A3_obj],
            'Instalacion (USD)': [A1_inst, resultado_A1_D['instalacion'], A2_inst, resultado_A2_D['instalacion'], A3_inst],
            'Overflow (USD)': [0, resultado_A1_D['overflow'], 0, resultado_A2_D['overflow'], A3_overflow],
            'No_Reciclar (USD)': [A1_nr, resultado_A1_D['no_reciclar'], A2_nr, resultado_A2_D['no_reciclar'], A3_nr],
            'Overflow (kg)': [0, resultado_A1_D['overflow_kg'], 0, resultado_A2_D['overflow_kg'], 
                             float(df_A3[df_A3['Indicador'] == 'Overflow Total (kg)']['Valor'].values[0])],
            'Reciclado (kg)': [
                float(df_A1[df_A1['Indicador'] == 'Reciclados (kg)']['Valor'].values[0].replace(',','')),
                resultado_A1_D['recicla_kg'],
                float(df_A2[df_A2['Indicador'] == 'Reciclados (kg)']['Valor'].values[0].replace(',','')),
                resultado_A2_D['recicla_kg'],
                float(df_A3[df_A3['Indicador'] == 'Reciclados (kg)']['Valor'].values[0].replace(',',''))
            ],
            'No_Reciclado (kg)': [
                float(df_A1[df_A1['Indicador'] == 'NO Reciclados (kg)']['Valor'].values[0].replace(',','')),
                resultado_A1_D['no_recicla_kg'],
                float(df_A2[df_A2['Indicador'] == 'NO Reciclados (kg)']['Valor'].values[0].replace(',','')),
                resultado_A2_D['no_recicla_kg'],
                float(df_A3[df_A3['Indicador'] == 'NO Reciclados (kg)']['Valor'].values[0].replace(',',''))
            ],
            'Contenedores': [10, resultado_A1_D['n_contenedores'], 10, resultado_A2_D['n_contenedores'], 10]
        })
        
        # Tabla de diferencias (costo oculto)
        tabla_diferencias = pd.DataFrame({
            'Comparacion': ['A1 -> A1-D', 'A2 -> A2-D'],
            'Costo_Oculto (USD)': [
                resultado_A1_D['obj_value'] - A1_obj,
                resultado_A2_D['obj_value'] - A2_obj
            ],
            'Costo_Oculto (%)': [
                ((resultado_A1_D['obj_value'] - A1_obj) / A1_obj * 100) if A1_obj > 0 else 0,
                ((resultado_A2_D['obj_value'] - A2_obj) / A2_obj * 100) if A2_obj > 0 else 0
            ],
            'Overflow_Generado (kg)': [
                resultado_A1_D['overflow_kg'],
                resultado_A2_D['overflow_kg']
            ],
            'Overflow_Generado (USD)': [
                resultado_A1_D['overflow'],
                resultado_A2_D['overflow']
            ]
        })
        
        # Tabla comparando A1-D, A2-D vs A3
        tabla_vs_A3 = pd.DataFrame({
            'Modelo': ['A1-D', 'A2-D'],
            'Diff_F.O. vs A3 (USD)': [
                resultado_A1_D['obj_value'] - A3_obj,
                resultado_A2_D['obj_value'] - A3_obj
            ],
            'Diff_F.O. vs A3 (%)': [
                ((resultado_A1_D['obj_value'] - A3_obj) / A3_obj * 100) if A3_obj > 0 else 0,
                ((resultado_A2_D['obj_value'] - A3_obj) / A3_obj * 100) if A3_obj > 0 else 0
            ],
            'Mejor_que_A3': [
                'SI' if resultado_A1_D['obj_value'] < A3_obj else 'NO',
                'SI' if resultado_A2_D['obj_value'] < A3_obj else 'NO'
            ]
        })
        
        # Guardar todo en Excel con múltiples hojas
        with pd.ExcelWriter('comparacion_modelos.xlsx', engine='openpyxl') as writer:
            tabla_comp.to_excel(writer, sheet_name='Comparacion_General', index=False)
            tabla_diferencias.to_excel(writer, sheet_name='Costo_Oculto', index=False)
            tabla_vs_A3.to_excel(writer, sheet_name='Comparacion_vs_A3', index=False)
        
        print("-> Resultados guardados en: comparacion_modelos.xlsx")
        print("  Hojas:")
        print("    - Comparacion_General: Tabla completa de todos los modelos")
        print("    - Costo_Oculto: Diferencias A1->A1-D y A2->A2-D")
        print("    - Comparacion_vs_A3: Comparacion de A1-D y A2-D vs modelo propuesto")
        print("\n" + "="*80)