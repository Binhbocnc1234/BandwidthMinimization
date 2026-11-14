import sys, time
sys.path.insert(0, "script/sat")
from SATSolverWrapper import solveBMPSAT
sol=sys.argv[1]
t=time.time()
print("start", sol, flush=True)
res=solveBMPSAT("data/HarwellBoeing/graphs/ibm32.col","order",sol,float(sys.argv[2]),verbose=True)
print(sol,"limit",sys.argv[2],"elapsed",round(time.time()-t,1),res["status"],res["bestUB"],flush=True)
