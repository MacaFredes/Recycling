import xml.etree.ElementTree as ET
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# ===== LEER EL ARCHIVO KML =====
ruta_kml = 'Estación Central Case Study.kml'

tree = ET.parse(ruta_kml)
root = tree.getroot()

ns = {'kml': 'http://www.opengis.net/kml/2.2'}

# Listas separadas para cada tipo
demandas = []
candidatos = []

# Extraer todos los Placemarks
for placemark in root.findall('.//kml:Placemark', ns):
    nombre_elem = placemark.find('kml:name', ns)
    nombre = nombre_elem.text if nombre_elem is not None else 'Sin nombre'
    
    desc_elem = placemark.find('kml:description', ns)
    descripcion = desc_elem.text if desc_elem is not None else ''
    
    coords_elem = placemark.find('.//kml:coordinates', ns)
    if coords_elem is not None:
        coords = coords_elem.text.strip()
        partes = coords.split(',')
        if len(partes) >= 2:
            longitud = float(partes[0])
            latitud = float(partes[1])
            
            punto = {
                'nombre': nombre,
                'latitud': latitud,
                'longitud': longitud,
                'descripcion': descripcion
            }
            
            # ===== CLASIFICAR SEGÚN EL NOMBRE =====
            # Si el nombre contiene "loc_" es CANDIDATO
            if nombre.lower().startswith('loc_') or 'loc_' in nombre.lower():
                candidatos.append(punto)
            # Si el nombre contiene "punto" es DEMANDA
            elif 'punto' in nombre.lower() or nombre.lower().startswith('punto'):
                demandas.append(punto)
            # Si no está claro, imprimir para ver
            else:
                print(f" Punto sin clasificar: '{nombre}'")
                demandas.append(punto)

# Crear DataFrames
df_demandas = pd.DataFrame(demandas)
df_candidatos = pd.DataFrame(candidatos)

# ===== IMPRIMIR INFORMACIÓN =====
print("\n" + "=" * 80)
print("RESUMEN DE DATOS EXTRAÍDOS DEL KML")
print("=" * 80)
print(f" Total de puntos de DEMANDA (azules - 'Puntos'): {len(df_demandas)}")
print(f" Total de puntos CANDIDATOS (rojos - 'loc_X'): {len(df_candidatos)}")
print(f" Total general: {len(df_demandas) + len(df_candidatos)}")

if len(df_demandas) > 0:
    print("\n" + "=" * 80)
    print("MUESTRA DE PUNTOS DE DEMANDA (primeros 10)")
    print("=" * 80)
    print(df_demandas.head(10).to_string())

if len(df_candidatos) > 0:
    print("\n" + "=" * 80)
    print("MUESTRA DE PUNTOS CANDIDATOS (primeros 10)")
    print("=" * 80)
    print(df_candidatos.head(10).to_string())

# ===== GUARDAR EN EXCEL SEPARADOS =====
# if len(df_demandas) > 0:
#     df_demandas.to_excel('demandas_bloques_censales.xlsx', index=False)
#     print("\n Demandas guardadas en 'demandas_bloques_censales.xlsx'")

# if len(df_candidatos) > 0:
#     df_candidatos.to_excel('candidatos_contenedores.xlsx', index=False)
#     print(" Candidatos guardados en 'candidatos_contenedores.xlsx'")

# ===== VISUALIZACIÓN ESTILO GOOGLE MAPS =====
fig = plt.figure(figsize=(16, 12))

# Graficar puntos de demanda (AZULES)
if len(df_demandas) > 0:
    plt.scatter(df_demandas['longitud'], df_demandas['latitud'], 
                c='#4285F4', s=80, alpha=0.7, 
                edgecolors='white', linewidth=1.5,
                label=f'Demandas (bloques censales) n={len(df_demandas)}',
                marker='o', zorder=3)

# Graficar puntos candidatos (ROJOS)
if len(df_candidatos) > 0:
    plt.scatter(df_candidatos['longitud'], df_candidatos['latitud'], 
                c='#EA4335', s=150, alpha=0.8,
                edgecolors='darkred', linewidth=2,
                label=f'Candidatos (contenedores) n={len(df_candidatos)}',
                marker='o', zorder=5)

plt.xlabel('Longitud', fontsize=14, fontweight='bold')
plt.ylabel('Latitud', fontsize=14, fontweight='bold')
plt.title('Mapa de Estación Central - Demandas y Candidatos\n(Replicando Google Maps)', 
          fontsize=16, fontweight='bold', pad=20)
plt.legend(loc='upper right', fontsize=12, framealpha=0.95, 
           edgecolor='black', fancybox=True, shadow=True)
plt.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
plt.tight_layout()
plt.show()

# ===== PANEL CON MÚLTIPLES VISTAS =====
fig, axes = plt.subplots(2, 2, figsize=(18, 14))

# Subplot 1: Vista completa estilo Google Maps
if len(df_demandas) > 0:
    axes[0, 0].scatter(df_demandas['longitud'], df_demandas['latitud'], 
                       c='#4285F4', s=70, alpha=0.6, 
                       edgecolors='white', linewidth=1, zorder=3)
if len(df_candidatos) > 0:
    axes[0, 0].scatter(df_candidatos['longitud'], df_candidatos['latitud'], 
                       c='#EA4335', s=120, alpha=0.8, 
                       edgecolors='darkred', linewidth=1.5, zorder=5)
axes[0, 0].set_title('Vista Completa del Área', fontweight='bold', fontsize=12)
axes[0, 0].grid(True, alpha=0.3)
axes[0, 0].set_xlabel('Longitud')
axes[0, 0].set_ylabel('Latitud')

# Subplot 2: Mapa de densidad de demandas
if len(df_demandas) > 0:
    axes[0, 1].hexbin(df_demandas['longitud'], df_demandas['latitud'], 
                      gridsize=25, cmap='Blues', alpha=0.7, mincnt=1)
    if len(df_candidatos) > 0:
        axes[0, 1].scatter(df_candidatos['longitud'], df_candidatos['latitud'], 
                           c='red', s=100, edgecolors='darkred', linewidth=2, 
                           marker='*', label='Candidatos', zorder=10)
axes[0, 1].set_title('Densidad de Demanda', fontweight='bold', fontsize=12)
axes[0, 1].grid(True, alpha=0.3)
axes[0, 1].set_xlabel('Longitud')
axes[0, 1].set_ylabel('Latitud')
axes[0, 1].legend()

# Subplot 3: Distribución geográfica
if len(df_demandas) > 0 and len(df_candidatos) > 0:
    axes[1, 0].scatter(df_demandas['longitud'], df_demandas['latitud'], 
                       c='lightblue', s=50, alpha=0.5, 
                       edgecolors='blue', linewidth=0.5, label='Demandas')
    axes[1, 0].scatter(df_candidatos['longitud'], df_candidatos['latitud'], 
                       c='red', s=200, alpha=0.7, 
                       edgecolors='darkred', linewidth=2, 
                       marker='^', label='Candidatos')
axes[1, 0].set_title('Comparación de Ubicaciones', fontweight='bold', fontsize=12)
axes[1, 0].grid(True, alpha=0.3)
axes[1, 0].set_xlabel('Longitud')
axes[1, 0].set_ylabel('Latitud')
axes[1, 0].legend()

# Subplot 4: Estadísticas (CORREGIDO)
axes[1, 1].axis('off')

# Calcular estadísticas separadamente para evitar error en f-string
if len(df_demandas) > 0:
    dem_lat_mean = f"{df_demandas['latitud'].mean():.6f}"
    dem_lon_mean = f"{df_demandas['longitud'].mean():.6f}"
    dem_lat_min = f"{df_demandas['latitud'].min():.6f}"
    dem_lat_max = f"{df_demandas['latitud'].max():.6f}"
    dem_lon_min = f"{df_demandas['longitud'].min():.6f}"
    dem_lon_max = f"{df_demandas['longitud'].max():.6f}"
else:
    dem_lat_mean = dem_lon_mean = "N/A"
    dem_lat_min = dem_lat_max = "N/A"
    dem_lon_min = dem_lon_max = "N/A"

if len(df_candidatos) > 0:
    cand_lat_mean = f"{df_candidatos['latitud'].mean():.6f}"
    cand_lon_mean = f"{df_candidatos['longitud'].mean():.6f}"
    cand_lat_min = f"{df_candidatos['latitud'].min():.6f}"
    cand_lat_max = f"{df_candidatos['latitud'].max():.6f}"
    cand_lon_min = f"{df_candidatos['longitud'].min():.6f}"
    cand_lon_max = f"{df_candidatos['longitud'].max():.6f}"
else:
    cand_lat_mean = cand_lon_mean = "N/A"
    cand_lat_min = cand_lat_max = "N/A"
    cand_lon_min = cand_lon_max = "N/A"

stats_text = f"""
═══════════════════════════════════════
   ESTADÍSTICAS DEL CASO DE ESTUDIO
═══════════════════════════════════════

PUNTOS DE DEMANDA (Azules):
  • Total de bloques censales: {len(df_demandas)}
  • Coordenadas promedio:
    - Latitud:  {dem_lat_mean}
    - Longitud: {dem_lon_mean}
  • Rango:
    - Lat: [{dem_lat_min}, {dem_lat_max}]
    - Lon: [{dem_lon_min}, {dem_lon_max}]

UBICACIONES CANDIDATAS (Rojos):
  • Total de candidatos: {len(df_candidatos)}
  • Coordenadas promedio:
    - Latitud:  {cand_lat_mean}
    - Longitud: {cand_lon_mean}
  • Rango:
    - Lat: [{cand_lat_min}, {cand_lat_max}]
    - Lon: [{cand_lon_min}, {cand_lon_max}]

SEGÚN EL PAPER:
  • Demandas = Centroides de bloques censales
  • Candidatos = Intersecciones en avenidas
  • Radio máximo de cobertura: 0.3 km
═══════════════════════════════════════
"""

axes[1, 1].text(0.05, 0.5, stats_text, fontsize=10, family='monospace',
                verticalalignment='center')

plt.tight_layout()
plt.show()

print("\n" + "=" * 80)
print(" VISUALIZACIONES GENERADAS EXITOSAMENTE")
print("=" * 80)
print("\nPara verificar contra Google Maps:")
if len(df_demandas) > 0:
    print(f"  Centro de demandas: {df_demandas['latitud'].mean():.6f}, {df_demandas['longitud'].mean():.6f}")
if len(df_candidatos) > 0:
    print(f"  Centro de candidatos: {df_candidatos['latitud'].mean():.6f}, {df_candidatos['longitud'].mean():.6f}")
    
# =========== Generar conjuntos ===========

print("\n" + "=" * 80)
print("GENERANDO CONJUNTOS PARA EL MODELO RBLP")
print("=" * 80)

# 1. Primero crear las columnas de ID único en los DataFrames
df_demandas['id_unico'] = ['loc_' + str(i) for i in df_demandas.index]
df_candidatos['id_unico'] = ['punto_' + str(i) for i in df_candidatos.index]

# Conjunto I: DEMANDAS 
I = df_demandas['id_unico'].tolist()   #####ESTE IMPORTA


# Conjunto J: CANDIDATOS 
J = df_candidatos['id_unico'].tolist()    #####ESTE IMPORTA


# Conjunto K: Tipos de capacidad
K = [1, 2, 3]      #####ESTE IMPORTA

print(f"\n I (demandas): |I| = {len(I)}")

print(f"\n J (candidatos): |J| = {len(J)}")

# print(J)


# =========== Crear parámetro d_jk (capacidades) ===========

# Capacidades disponibles (en kg)
capacidades = {
    1: 600,   # Pequeño
    2: 900,   # Mediano
    3: 1200   # Grande (estándar del paper)
}

# Crear diccionario d[j,k] = capacidad k en ubicación j
d = {}
for j in J:
    for k in K:
        d[(j, k)] = capacidades[k]

# Valor de d
print(f"\n Parámetro d creado: {len(d)} elementos")
#print(d)  #####ESTE IMPORTA

# =========== Calcular phi_ij (distancias round-trip) ===========

def haversine(lat1, lon1, lat2, lon2):
    """
    Calcula distancia en km usando fórmula de Haversine.
    """
    R = 6371  # Radio de la Tierra en km
    
    # Convertir a radianes
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    # Diferencias
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    # Fórmula de Haversine
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    return R * c

# Crear diccionario phi[i,j]
phi = {}

for i in I:
    # Coordenadas del usuario i
    lat_i = df_demandas[df_demandas['id_unico'] == i]['latitud'].values[0]
    lon_i = df_demandas[df_demandas['id_unico'] == i]['longitud'].values[0]
    
    for j in J:
        # Coordenadas del candidato j
        lat_j = df_candidatos[df_candidatos['id_unico'] == j]['latitud'].values[0]
        lon_j = df_candidatos[df_candidatos['id_unico'] == j]['longitud'].values[0]
        
        # Distancia round-trip (ida y vuelta)
        phi[(i, j)] = 2 * haversine(lat_i, lon_i, lat_j, lon_j)

# print(f"\n Matriz phi calculada: {len(phi)} elementos")
# print(f"  Dimensión: |I| × |J| = {len(I)} × {len(J)}")
#print(phi)     ####ESTE IMPORTA #ESTÁ EN KM


# =========== Calcular q_i (cantidad de residuos por cada i) ===========

VIVIENDAS_TOTALES = 65_017  # Censo 2024 INE - Estación Central
FACTOR_SEMANAL = 0.24  # kg/vivienda/semana (del paper)

# Distribuir las 65,017 viviendas entre los bloques censales
np.random.seed(42)
viviendas_por_bloque = np.random.randint(5, 4317, len(I))
viviendas_por_bloque = viviendas_por_bloque * (VIVIENDAS_TOTALES / viviendas_por_bloque.sum()) #esto es para asegurar que la suma de exactamente 65.017 bloques

# Crear q: Di = 0.24 × viviendas
q = {i: round(FACTOR_SEMANAL * viviendas_por_bloque[idx], 2) 
     for idx, i in enumerate(I)}

#print(q)  #####ESTE IMPORTA #ES KG/SEMANA

# =========== Crear parámetro r_i  ===========
# En el paper: r_i = r = 0.3 km para TODOS los usuarios

r = {i: 0.3*2 for i in I}  # 0.3 km = 300 metros = caminata de 5 minutos

#print(r)  #####ESTE IMPORTA

# =========== Crear parámetro c_nr ===========
# Costo de oportunidad por no reciclar vidrio (precio de venta de reciclables)
#
# Fuente: Rodríguez Sepúlveda (2021). Plan de negocios centro de pretratamiento
#         para la valorización de residuos. Tesis, Universidad de Chile.
#         Precio promedio ponderado de venta de materiales reciclables: 3.7 UF/ton
#
# Conversión a USD/kg:
#   - UF promedio enero 2021: 29,070 CLP
#     Fuente: SII (2021). https://www.sii.cl/valores_y_fechas/uf/uf2021.htm
#   - Tipo de cambio promedio 2021: 759 CLP/USD
#     Fuente: Banco Central de Chile (2021). Dólar Observado.
#             https://si3.bcentral.cl/indicadoressiete
#
#   c_nr = (3.7 UF/ton × 29,070 CLP/UF) / (759 CLP/USD × 1,000 kg/ton)
#        = 107,559 / 759,000 ≈ 0.142 USD/kg

c_ton = {i: 142 for i in I}  # USD/ton
c_nr = {i: round(c_ton[i] / 1000, 3) for i in I}  # 0.142 USD/kg
#print(c_nr)  #####ESTE IMPORTA #ESTE ES USD/kg

# =========== Crear parámetro f_jk ===========
# COSTO BASE: Contenedor 1,100 L = 284 USD
# Fuente: PlayPlaza Chile (255,493 CLP ≈ 284 USD)
# Link: https://playplaza.cl/products/contenedor-de-basura-1100-lts-azul
# CONVERSIÓN KG → LITROS:
# Vidrio fragmentado en contenedor tiene densidad aparente ≈ 0.3 kg/L
# (mucho aire entre fragmentos/botellas)
#
# Por lo tanto:
# - 600 kg ÷ 0.3 kg/L = 2,000 L
# - 900 kg ÷ 0.3 kg/L = 3,000 L
# - 1,200 kg ÷ 0.3 kg/L = 4,000 L
# CÁLCULO DE PRECIOS:
# Usando economía de escala: Precio = 284 × (Volumen_nuevo / 1100)^0.7
#
# k=1: 284 × (2000/1100)^0.7 = 284 × 1.556 = 442 USD
# k=2: 284 × (3000/1100)^0.7 = 284 × 1.936 = 550 USD
# k=3: 284 × (4000/1100)^0.7 = 284 × 2.247 = 638 USD
# Si un contenedor dura 5 años (260 semanas)
VIDA_UTIL_SEMANAS = 260
costos_fijos_amortizados = {
    1: 442 / VIDA_UTIL_SEMANAS,  # ~1.70 USD/semana
    2: 550 / VIDA_UTIL_SEMANAS,  # ~2.12 USD/semana
    3: 638 / VIDA_UTIL_SEMANAS   # ~2.45 USD/semana
}
# Crear f[j,k] con costos amortizados
f = {}
for j in J:
    for k in capacidades.keys():
        f[(j, k)] = costos_fijos_amortizados[k]
#print(f)  #####ESTE IMPORTA

# =========== Crear parámetro c_dump_j ===========
# Costo de overflow = 1.5 × c_NR
#
# Fuente: Dávila-Gálvez et al. (2025). Waste Management Externalities at
#         Recycling Drop-off Locations: A Recycling Bin Location Problem.
#         Ratio c_d / c_NR = 1.5, reflejando que el overflow incurre en los
#         costos de gestión estándar más externalidades adicionales por
#         disposición inadecuada en el punto de recolección.
#
#   c_dump = 1.5 × 0.142 = 0.213 USD/kg

COSTO_ADICIONAL_OVERFLOW = 1.5 * 0.142  # = 0.213 USD/kg
c_dump = {}
for j in J:
    c_dump[j] = COSTO_ADICIONAL_OVERFLOW
#print(c_dump)  #####ESTE IMPORTA USD/KG

# =========== presupuesto p ===========

p = round(len(J)/10)*1.8 #máximo valor del contenedor (ANTES 2.4)




print("\n" + "=" * 80)
print("INSTANCIAS GENERADAS")  #####ESTE 




