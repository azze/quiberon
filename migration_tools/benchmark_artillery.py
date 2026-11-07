"""Matched M4 combined-arms / artillery-heavy fixed-tick workloads, no renderer.
Three sequential repeats by default; supported mechanics only, not full AI/commanders.
"""
import argparse,json,csv,subprocess
from statistics import mean
from time import perf_counter_ns
from pathlib import Path
from .artillery_reference import ROOT,SCENARIOS,make,queue
from .movement_reference import compare

def python_sample(path):
 d=json.loads(path.read_text());b,schedule=make(d);timings=[];peak=0;shots=0
 for tick in range(700):
  if b.result is not None:raise RuntimeError('Inactive/finished benchmark')
  start=perf_counter_ns();queue(b,schedule);b.step()
  if tick>=100:timings.append((perf_counter_ns()-start)/1e6)
  peak=max(peak,len(b.projectiles))
 timings.sort()
 return dict(meanMs=mean(timings),medianMs=timings[300],p95Ms=timings[570],ticksPerSecond=1000/mean(timings),measuredWallSeconds=sum(timings)/1000,randomDraws=b.rng.draws,peakProjectiles=peak,artilleryShots=sum(u.analysis['artillery_shots'] for u in b.units),finalStates=[dict(id=u.id,position=dict(x=u.pos.x,y=u.pos.y),strength=u.strength,morale=u.morale,cohesion=u.cohesion,state=u.state.value,withdrawn=u.withdrawn) for u in b.units])
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--counts',nargs='+',type=int,default=[12,24,36,60]);parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--kinds',nargs='+',choices=['artillery','combined'],default=['artillery','combined']);parser.add_argument('--output',type=Path,default=ROOT/'benchmark-results/m4-headless.json');args=parser.parse_args()
 if args.repeats<1 or any(n not in [12,24,36,60] for n in args.counts):parser.error('Use positive repeats and counts 12/24/36/60')
 samples=[]
 for repeat in range(args.repeats):
  for kind in args.kinds:
   for count in args.counts:
    id=f'benchmark-{kind}-{count}';path=SCENARIOS/(id+'.json');py=python_sample(path)
    command=['bash','tools/dotnet.sh','godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll','--scenario',str(path),'--benchmark']
    cs=json.loads(subprocess.run(command,cwd=ROOT,capture_output=True,text=True,check=True).stdout)
    parity='matched';error=0
    try:
     error=compare(dict(name=id,units=py['finalStates']),dict(name=id,units=cs['finalStates']))
     if py['randomDraws']!=cs['randomDraws']:raise AssertionError('Random draw count')
    except (AssertionError,KeyError) as exc:parity=str(exc)
    samples.append(dict(kind=kind,count=count,repeat=repeat,python=py,csharp=cs,parity=parity,maximumError=error))
    print(f'{kind} {count} repeat {repeat+1}: Python {py["meanMs"]:.3f} / C# {cs["meanMs"]:.3f} ms; {parity}',flush=True)
 summary=[]
 for kind in args.kinds:
  for count in args.counts:
   rows=[r for r in samples if r['kind']==kind and r['count']==count];row=dict(kind=kind,count=count,parity=rows[0]['parity'])
   for lang in ['python','csharp']:
    for metric in ['meanMs','medianMs','p95Ms','ticksPerSecond','measuredWallSeconds']:row[lang+'_'+metric]=mean(r[lang][metric] for r in rows)
   for metric in ['allocatedBytesPerTick']:row[metric]=mean(r['csharp'][metric] for r in rows)
   row.update(rows[0]['csharp']['metrics']);summary.append(row)
 args.output.parent.mkdir(exist_ok=True,parents=True);args.output.write_text(json.dumps(dict(warmup=100,measuredTicks=600,simulatedSeconds=60,repeats=args.repeats,summary=summary,samples=samples),indent=2)+'\n')
 with args.output.with_suffix('.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
 if any(r['parity']!='matched' for r in samples):raise SystemExit('Reference divergence; inspect saved parity fields')
if __name__=='__main__':main()
