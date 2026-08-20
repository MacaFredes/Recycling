#Modeling and optimization.
import gurobipy as gp
from gurobipy import GRB

#Importar instancias del otro documento
import Instancia

# Importar modulo de resultados
import Resultados
# #%%=======================================================Generar Conjuntos y parámetros========================================

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

x = m.addVars(I,J, vtype=GRB.BINARY, lb = 0) #Si el citio i decidió utilizar el citio de reciclaje j.
y = m.addVars(J,K, vtype=GRB.BINARY, lb = 0) #Si el municipio decide utilizar la ubicación j con un contenedor de capacidad k.
z = m.addVars(J, vtype=GRB.CONTINUOUS, lb = 0) #Cantidad de residuos que excede la capacidad del contenedor en el punto j

print("Finalizando variables")
# ------------------------------------------Objective Function------------------

#costo_inst = gp.quicksum(y[j,k]*f[j,k] for j in J for k in K)
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
            # Ij[j].append(i)
    print(i,Ji[i])
    
        
#La instalación de contenedores debe respetar el presupuesto del municipio. 
m.addConstr(gp.quicksum(y[j,k]*f[j,k] for j in J for k in K) <= p)

for i in I:
    # Cada citio i debe ser asignado a lo más a un citio de reciclaje j.
    m.addConstr(gp.quicksum(x[i,j] for j in J) <= 1)
    # Cada citio i no se le asignará citio j dónde phi sea mayor a r.
    m.addConstr(gp.quicksum(x[i,j] for j in J if j not in Ji[i]) == 0)
        
    for j in Ji[i]:
        #Si se habilita el citio de reciclaje j con contenedores k, se puede asignar a algun citio i.
        m.addConstr(x[i,j] <= gp.quicksum(y[j,k] for k in K))
        # Se considera todas las locaciones más proximas a j.
        m.addConstr(gp.quicksum(y[j,k] for k in K) <= gp.quicksum(x[i,jp] for jp in Ji[i] 
                                  if phi[i,jp] <= phi[i,j]))
for j in J:
    #para todo citio de reciclaje j debe existir a lo más un contenedor k.
    m.addConstr(gp.quicksum(y[j,k] for k in K) <= 1)
    #Evalúa si los contenedores se ven con excedentes.
    m.addConstr(gp.quicksum(q[i]*x[i,j] for i in I) <= gp.quicksum(d[j,k]*y[j,k] for k in K) + z[j])
#q[i]*x[i,j] = w[i,j], rec 95, iz debería ir w[i,j]
#w[i,j] <= q[i]*x[i,j]
#x[i,j] <= w[i,j] (pensarlo más, si j va, el w tiene que tomar un valor) Esto es asumir que la persona no va a dejar cosas afuera.
#La otra opción es que no va, si es que está repleto (otro modelo), solo va si solo si, si sabe que hay capacidad.

print("Finaliza restricciones")
m.setParam(GRB.Param.TimeLimit, 2500)
m.setParam(GRB.Param.Cuts, 0)
m.setParam(GRB.Param.Seed, 123)

#--------------------------------------------Resuslt------------------------------------------------------


#Set up solver to solve the model
m.optimize()


costo_dump = gp.quicksum(z[j].x*c_dump[j] for j in J)

print("Cantidad no reciclacada:", sum(q[i]*(1-sum(x[i,j].x for j in J)) for i in I),
      'Gasto: ', sum(q[i]*(1-sum(x[i,j].x for j in J)) for i in I)*0.080)

for i in I:
    if sum(x[i,j].x for j in J) < 0.5 and sum(y[j,k].x for j in Ji[i] for k in K) >0.5:
        print("i",i,r[i],"j", [(j,phi[i,j]) for j in Ji[i] if sum(y[j,k].x for k in K)>0])
        
print("EL VALOR ES",sum(x['loc_59',j].x for j in J),"EL VALOR ES", sum(y['punto_84',k].x for k in K) )
print("VAMOS A VER JI",Ji['loc_59'])

# print("Cantidad reciclaca:", sum(min(sum(q[i]*x[i,j].x for i in I),1200) for j in J),
#       'Ahorro : ', sum(min(sum(q[i]*x[i,j].x for i in I),1200)*0.067 for j in J))


# print("Cantidad overflow:", sum(max(sum(q[i]*x[i,j].x for i in I)-1200,0) for j in J),
#       'Costo : ', sum(max(sum(q[i]*x[i,j].x for i in I)-1200,0)*c_dump[j] for j in J))

print("el valor de la F.O es",m.ObjVal)
#print("el costo dump es", costo_dump)


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
# #     for i in I:
# #         if x[i,j].x != 0:
# #             print("El sitio", i, "decidió utilizar el sitio de reciclaje",j, "valor", x[i,j].x)
    # for k in K:
    #     if y[j,k].x > 0.5:
    #         print("El municipio decidió utilizar la ubicación", j, "para poner un contenedor",k)

F_O, df_sitios, overflow, stats = Resultados.generar_resultados(
    model=m, x=x, y=y, z=z, q=q, I=I, J=J, K=K, d=d, f=f, 
    c_dump=c_dump, c_nr=c_nr, phi=phi, r=r,
    df_demandas=Instancia.df_demandas,
    df_candidatos=Instancia.df_candidatos,
    nombre_archivo="mi_reporte_A3.pdf" 
)
