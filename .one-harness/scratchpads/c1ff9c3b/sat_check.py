import itertools, random, sys, tempfile, os
sys.path.insert(0, "script/sat")
from SATSolverWrapper import solveBMPSAT

def oracle(n, edges):
    return min(max((abs(p[u-1]-p[v-1]) for u,v in edges), default=0) for p in itertools.permutations(range(1,n+1)))

cases = [(1,[]),(5,[]),(4,[(1,4),(2,3),(3,4)]),(5,[(1,2),(2,3),(3,4),(4,5),(1,5)]),(5,list(itertools.combinations(range(1,6),2))),(6,[(1,4),(2,5),(4,6)]),(8,[(1,8),(2,7),(3,6)])]
r = random.Random(17)
for _ in range(5):
    cases.append((5,[e for e in itertools.combinations(range(1,6),2) if r.random()<0.4]))
wrong=0; total=0; notopt=[]
with tempfile.TemporaryDirectory() as d:
    for idx,(n,edges) in enumerate(cases):
        path=os.path.join(d,f"g{idx}.col")
        open(path,"w").write(f"p edge {n} {len(edges)}\n"+"".join(f"e {u} {v}\n" for u,v in edges))
        best=oracle(n,edges)
        for enc in ("order","pairwise"):
            for sol in ("repeated","incremental"):
                res=solveBMPSAT(path,enc,sol,15.0)
                total+=1
                if res["bestUB"]!=best: wrong+=1; print("WRONG",idx,enc,sol,res["bestUB"],best)
                if res["status"]!="OPTIMAL": notopt.append((idx,n,len(edges),enc,sol,res["status"],res["bestUB"]))
print("runs",total,"wrong bandwidth",wrong,"not OPTIMAL",len(notopt))
for x in notopt: print(x)
