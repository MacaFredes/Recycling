# -*- coding: utf-8 -*-
"""
Extraer solo las manzanas de Estación Central del archivo grande
"""
import json

# Ruta al archivo descargado (ajusta según donde lo guardaste)
ruta_entrada = 'R13_MANZANA_IND_C17.shp.geojson'
ruta_salida = 'manzanas_estacion_central.geojson'

print("Leyendo archivo grande...")
with open(ruta_entrada, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total de manzanas en RM: {len(data['features'])}")

# Filtrar solo Estación Central (código comuna = 13106)
manzanas_ec = []
for feature in data['features']:
    props = feature['properties']
    # El código de comuna puede estar en diferentes campos
    comuna = props.get('COMUNA', props.get('comuna', props.get('COD_COMUNA', '')))
    if str(comuna) == '13106':
        manzanas_ec.append(feature)

print(f"Manzanas en Estación Central: {len(manzanas_ec)}")

# Guardar archivo filtrado
output = {
    'type': 'FeatureCollection',
    'features': manzanas_ec
}

with open(ruta_salida, 'w', encoding='utf-8') as f:
    json.dump(output, f)

print(f"Guardado: {ruta_salida}")