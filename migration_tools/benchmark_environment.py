"""Matched environmental workloads; reports overhead without claiming a language speedup."""
import argparse,json,statistics,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repeat',type=int,default=3);p.add_argument('--output',type=Path,default=ROOT/'benchmark-results/environment-after.json');a=p.parse_args()
 if a.repeat<1:p.error('repeat must be positive')
 reports=[]
 for n in [12,24,36,60]:
  for kind in ['baseline','river','roads','rain','fog']:
   samples=[]
   for _ in range(a.repeat):
    r=subprocess.run(['bash','tools/dotnet.sh','godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll','--scenario',f'simulation_data/combat_scenarios/benchmark-environment-{kind}-{n}.json','--benchmark'],cwd=ROOT,capture_output=True,text=True,check=True)
    samples.append(json.loads(r.stdout))
   d=samples[0];d['variant']=kind;d['repeats']=a.repeat
   for k in ['meanMs','p95Ms','ticksPerSecond','allocatedBytesPerTick','measuredWallSeconds']:d[k]=statistics.median(s[k] for s in samples)
   assert len({s['checksum'] for s in samples})==1,'Nondeterministic run'
   reports.append(d);print(f'{kind:8} {n:2} mean {d["meanMs"]:.3f} ms; p95 {d["p95Ms"]:.3f}; {d["ticksPerSecond"]:.0f} ticks/s',flush=True)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(reports,indent=2)+'\n')
if __name__=='__main__':main()
