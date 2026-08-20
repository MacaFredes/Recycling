#Modeling and optimization.
import gurobipy as gp
from gurobipy import GRB

#Importar instancias del otro documento
import Instancia

# Importar modulo de resultados
import Resultados

#%%=======================================================Generar Conjuntos y parámetros========================================

#Importamos datos

J = Instancia.J  #Conjunto J: CANDIDATOS
I = Instancia.I  #Conjunto I: DEMANDAS 
K = Instancia.K  #Conjunto K: Tipos de capacidad
d = Instancia.d  #Crear parámetro d_jk (capacidades en kg)
phi = Instancia.phi #Calcular phi_ij (distancias round-trip en km)
q = Instancia.q #q_i (cantidad de residuos por cada i kg)
r = Instancia.r #r_i (máximo xotos que citio i está dispuesto a asumir para reciclar en km)
f = Instancia.f #f_jk (Costo de instalar contenedor en un citio USD)
c_dump = Instancia.c_dump #c_dump_j (Costo marginal por recoger reciduos externos USD/kg)
c_nr = Instancia.c_nr #c_nr_i (Costo marginal para el citio I por no reciclar USD/kg)
p= Instancia.p #Presupuesto USD
df_candidatos= Instancia.df_candidatos
print("DATOS CARGADOS")



#%%=======================================================Generar modelo========================================

#-------------------------------------------Model-------------------------------
m = gp.Model('Patrulling')

# ------------------------------------------Variables----------------------------
print("Iniciando variables")

print(f"n° demandas (|I|): {len(I)}")
print(f"n° candidatos (|J|): {len(J)}")

x = m.addVars(I,J, vtype=GRB.BINARY, lb = 0)
y = m.addVars(J,K, vtype=GRB.BINARY, lb = 0)
z = m.addVars(J, vtype=GRB.CONTINUOUS, lb = 0)

print("Finalizando variables")

# ------------------------------------------Objective Function------------------

costo_dump = gp.quicksum(z[j]*c_dump[j] for j in J)
costo_NR = gp.quicksum(q[i]*c_nr[i]*(1 - gp.quicksum((x[i,j]) for j in J)) for i in I)

m.setObjective(costo_dump+costo_NR, GRB.MINIMIZE)

#------------------------------------------Restricciones------------------------
print("Iniciando restricciones")

Ji = {}
Ij = {j : [] for j in J}
for i in I:
    Ji[i] = []
    for j in J:
        if r[i] > phi[i,j] :
            Ji[i].append(j)
#    print(i,Ji[i])

m.addConstr(gp.quicksum(y[j,k]*f[j,k] for j in J for k in K) <= p)

for i in I:
    m.addConstr(gp.quicksum(x[i,j] for j in J) <= 1)
    m.addConstr(gp.quicksum(x[i,j] for j in J if j not in Ji[i]) == 0)
        
    for j in Ji[i]:
        m.addConstr(x[i,j] <= gp.quicksum(y[j,k] for k in K))
        m.addConstr(gp.quicksum(y[j,k] for k in K) <= gp.quicksum(x[i,jp] for jp in Ji[i] 
                                  if phi[i,jp] <= phi[i,j]))

for j in J:
    m.addConstr(gp.quicksum(y[j,k] for k in K) <= 1)
    m.addConstr(gp.quicksum(q[i]*x[i,j] for i in I) <= gp.quicksum(d[j,k]*y[j,k] for k in K) + z[j])

print("Finaliza restricciones")

#------------------------------------------Parámetros del solver------------------------

m.setParam(GRB.Param.TimeLimit, 2500)
m.setParam(GRB.Param.Cuts, 0)
m.setParam(GRB.Param.Seed, 123)

# Buscar múltiples soluciones óptimas
m.setParam(GRB.Param.PoolSearchMode, 2)  # Busca las mejores soluciones
m.setParam(GRB.Param.PoolSolutions, 10)  # Guarda hasta 10 soluciones
m.setParam(GRB.Param.PoolGap, 0.0)       # Solo soluciones con mismo valor óptimo

#--------------------------------------------Optimizar------------------------------------------------------

m.optimize()

#--------------------------------------------Análisis de soluciones múltiples-------------------------------

print("\n" + "="*60)
print("ANÁLISIS DE SOLUCIONES MÚLTIPLES")
print("="*60)
print(f"Soluciones óptimas encontradas: {m.SolCount}")
print(f"Valor óptimo: {m.ObjVal:.2f}")

# Ver las ubicaciones seleccionadas en cada solución
for sol in range(m.SolCount):
    m.setParam(GRB.Param.SolutionNumber, sol)
    ubicaciones = [(j, k) for j in J for k in K if y[j,k].Xn > 0.5]
    print(f"\nSolución {sol}: {len(ubicaciones)} contenedores")
    for j, k in ubicaciones:
        print(f"  - {j}, tipo {k}")

# Volver a la mejor solución para el resto del análisis
m.setParam(GRB.Param.SolutionNumber, 0)

print("\n" + "="*60)

#--------------------------------------------Resultados originales------------------------------------------------------

costo_dump = gp.quicksum(z[j].x*c_dump[j] for j in J)

print("Cantidad no reciclacada:", sum(q[i]*(1-sum(x[i,j].x for j in J)) for i in I),
      'Gasto: ', sum(q[i]*(1-sum(x[i,j].x for j in J)) for i in I)*0.080)

for i in I:
    if sum(x[i,j].x for j in J) < 0.5 and sum(y[j,k].x for j in Ji[i] for k in K) >0.5:
        print("i",i,r[i],"j", [(j,phi[i,j]) for j in Ji[i] if sum(y[j,k].x for k in K)>0])

print("el valor de la F.O es",m.ObjVal)

print(f"Presupuesto: {p:.2f}")
print(f"Presupuesto usado: {sum(y[j,k].x * f[j,k] for j in J for k in K):.2f}")
print(f"\nContenedores abiertos: {sum(1 for j in J for k in K if y[j,k].x > 0.5)}")
print(f"Demandas que NO reciclan: {sum(1 for i in I if sum(x[i,j].x for j in J) < 0.5)}")

basura = []
for j in J:
    if z[j].x != 0:
        basura.append(z[j].x)
        print("La cantidad de residuos excedida en el sitio",j, "es de",z[j].x)
print(len(basura)) 

F_O, df_sitios, overflow, stats = Resultados.generar_resultados(
    model=m, x=x, y=y, z=z, q=q, I=I, J=J, K=K, d=d, f=f, 
    c_dump=c_dump, c_nr=c_nr, phi=phi, r=r,
    df_demandas=Instancia.df_demandas,
    df_candidatos=Instancia.df_candidatos,
    nombre_archivo="mi_reporte_A3.pdf" 
)
