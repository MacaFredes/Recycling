#Modeling and optimization.
import gurobipy as gp
from gurobipy import GRB

#Importar instancias del otro documento
import Instancia

# Importar modulo de resultados
import Resultados
# #%%=======================================================Generar Conjuntos y parámetros========================================

#CASO: LA GENTE VA, DEJA LO QUE PUEDE EN EL CONTENEDOR Y EL RESTO SE LO TRAE.
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

# #%%=======================================================Generar modelo========================================

#-------------------------------------------Model-------------------------------
m = gp.Model('Patrulling')

#m.setParam("OutputFlag",1)

# ------------------------------------------Variables----------------------------
print("Iniciando variables")

x = m.addVars(I,J, vtype=GRB.BINARY, lb = 0) #Si el sitio i decidió utilizar el sitio de reciclaje j.
y = m.addVars(J,K, vtype=GRB.BINARY, lb = 0) #Si el municipio decide utilizar la ubicación j con un contenedor de capacidad k.
w = m.addVars(I,J, vtype=GRB.CONTINUOUS, lb = 0, ub=1) #Auxiliar de si el sitio i decidió utilizar el sitio de reciclaje j. Pero indica % de basura dejada.
print("Finalizando variables")
# ------------------------------------------Objective Function------------------

#falta agregarle lo que se llevan devuelta a casa
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
    # print(i,Ji[i])
    
#La instalación de contenedores debe respetar el presupuesto del municipio. 
m.addConstr(gp.quicksum(y[j,k]*f[j,k] for j in J for k in K) <= p)

for i in I:
    # Cada sitio i debe ser asignado a lo más a un sitio de reciclaje j.
    m.addConstr(gp.quicksum(x[i,j] for j in J) <= 1)
    # Cada sitio i no se le asignará sitio j dónde phi sea mayor a r.
    m.addConstr(gp.quicksum(x[i,j] for j in J if j not in Ji[i]) == 0)

    for j in Ji[i]:
        #Si se habilita el sitio de reciclaje j con contenedores k, se puede asignar a algun sitio i.
        m.addConstr(x[i,j] <= gp.quicksum(y[j,k] for k in K))
        # Se considera todas las locaciones más proximas a j.
        m.addConstr(gp.quicksum(y[j,k] for k in K) <= gp.quicksum(x[i,jp] for jp in Ji[i] 
                                  if phi[i,jp] <= phi[i,j]))

    for j in J:
        # La cantidad de residuos llevado a reciclar no puede ser mayor a lo ya generado.
        m.addConstr(w[i,j] <= x[i,j])
for j in J:
    #para todo sitio de reciclaje j debe existir a lo más un contenedor k.
    m.addConstr(gp.quicksum(y[j,k] for k in K) <= 1)
    # Evalúa cuánta cantidad de residuo se llevó el sitio j
    m.addConstr(gp.quicksum(q[i]*w[i,j] for i in I) <= gp.quicksum(d[j,k]*y[j,k] for k in K))

print("Finaliza restricciones")
m.setParam(GRB.Param.TimeLimit, 2500)
m.setParam(GRB.Param.Cuts, 0)
m.setParam(GRB.Param.Seed, 123)

#--------------------------------------------Resuslt------------------------------------------------------
#Set up solver to solve the model
m.optimize()

for j in J:
    for i in I:
        if w[i,j].x != 0:
            print("El sitio", i, "decidió utilizar el sitio de reciclaje",j, "en un", w[i,j].x*100,"%")

    # for k in K:
    #     if y[j,k].x > 0.5:
    #         print("El municipio decidió utilizar la ubicación", j, "para poner un contenedor",k)

print("el presupuesto es",p)
F_O, df_sitios, regresados, stats = Resultados.generar_resultados(
    model=m, x=x, y=y, w=w, q=q, I=I, J=J, K=K, d=d, f=f, 
    c_nr=c_nr, phi=phi, r=r,  # r es tu parámetro de radio
    df_demandas=Instancia.df_demandas,
    df_candidatos=Instancia.df_candidatos,
    nombre_archivo="mi_reporte_A2.pdf" 
)