#Modeling and optimization.
import gurobipy as gp
from gurobipy import GRB

#Importar instancias del otro documento
import Instancia

# Importar modulo de resultados
import Resultados

#%%=======================================================Generar Conjuntos y parámetros========================================

#CASO: La gente no va, si es que está repleto, solo va si solo si, si sabe que hay capacidad.

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
x = m.addVars(I,J, vtype=GRB.BINARY, lb = 0)
y = m.addVars(J,K, vtype=GRB.BINARY, lb = 0)
w = m.addVars(I,J, vtype=GRB.BINARY, lb = 0)
print("Finalizando variables")

# ------------------------------------------Objective Function------------------

costo_NR = gp.quicksum(q[i]*c_nr[i]*(1 - gp.quicksum((w[i,j]) for j in J)) for i in I)

m.setObjective(costo_NR, GRB.MINIMIZE)

#------------------------------------------Restricciones------------------------
print("Iniciando restricciones")
Ji = {}
for i in I:
    Ji[i] = []
    for j in J:
        if r[i] > phi[i,j] :
            Ji[i].append(j)
            
m.addConstr(gp.quicksum(y[j,k]*f[j,k] for j in J for k in K) <= p)

for i in I:
    m.addConstr(gp.quicksum(x[i,j] for j in J) <= 1)
    m.addConstr(gp.quicksum(x[i,j] for j in J if j not in Ji[i]) == 0)

    for j in Ji[i]:
        m.addConstr(x[i,j] <= gp.quicksum(y[j,k] for k in K))
        m.addConstr(gp.quicksum(y[j,k] for k in K) <= gp.quicksum(x[i,jp] for jp in Ji[i] 
                                  if phi[i,jp] <= phi[i,j]))

    for j in J:
        m.addConstr(w[i,j] <= x[i,j])

for j in J:
    m.addConstr(gp.quicksum(y[j,k] for k in K) <= 1)
    m.addConstr(gp.quicksum(q[i]*w[i,j] for i in I) <= gp.quicksum(d[j,k]*y[j,k] for k in K))
    
print("Finaliza restricciones")

#------------------------------------------Parámetros del solver------------------------

m.setParam(GRB.Param.TimeLimit, 2500)
m.setParam(GRB.Param.Cuts, 0)
m.setParam(GRB.Param.Seed, 123)

# Buscar múltiples soluciones óptimas
m.setParam(GRB.Param.PoolSearchMode, 2)
m.setParam(GRB.Param.PoolSolutions, 10)
m.setParam(GRB.Param.PoolGap, 0.0)

#--------------------------------------------Optimizar------------------------------------------------------

m.optimize()

#--------------------------------------------Análisis de soluciones múltiples-------------------------------

print("\n" + "="*60)
print("ANÁLISIS DE SOLUCIONES MÚLTIPLES - MODELO A1")
print("="*60)
print(f"Soluciones óptimas encontradas: {m.SolCount}")
print(f"Valor óptimo: {m.ObjVal:.2f}")

for sol in range(m.SolCount):
    m.setParam(GRB.Param.SolutionNumber, sol)
    ubicaciones = [(j, k) for j in J for k in K if y[j,k].Xn > 0.5]
    print(f"\nSolución {sol}: {len(ubicaciones)} contenedores")
    for j, k in ubicaciones:
        print(f"  - {j}, tipo {k}")
    # Verificar si las asignaciones x varían entre soluciones
    asignaciones = tuple(sorted([(i, j) for i in I for j in J if x[i,j].Xn > 0.5]))
    print(f"  Hash asignaciones x: {hash(asignaciones)}")

# Volver a la mejor solución
m.setParam(GRB.Param.SolutionNumber, 0)

print("\n" + "="*60)

#--------------------------------------------Resultados originales------------------------------------------------------

print("El el sitio de reciclaje","punto_0", "contuvo", sum(w[i,"punto_0"].x*q[i] for i in I))
       
print("el presupuesto es",p)

F_O, df_sitios, regresados, stats = Resultados.generar_resultados(
    model=m, x=x, y=y, w=w, q=q, I=I, J=J, K=K, d=d, f=f, 
    c_nr=c_nr, phi=phi, r=r,
    df_demandas=Instancia.df_demandas,
    df_candidatos=Instancia.df_candidatos,
    nombre_archivo="mi_reporte_A1.pdf" 
)