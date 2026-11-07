"""Release headless autonomous workloads. No profiler or renderer during timing."""
import argparse,json,csv,subprocess,statistics
from pathlib import Path
from .movement_reference import ROOT

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--commonwealth',action='store_true',help='Use the Stage-1 mixed roster and historical commanders');parser.add_argument('--counts',nargs='+',type=int,default=[12,24,36,60]);parser.add_argument('--output',type=Path,default=ROOT/'benchmark-results/m5-headless.json');a=parser.parse_args()
 if a.repeats<1 or any(n not in [12,24,36,60] for n in a.counts):parser.error('Use positive repeats and counts 12/24/36/60')
 rows=[]
 for repeat in range(a.repeats):
  for count in a.counts:
   result=subprocess.run(['bash','tools/dotnet.sh','godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll','--combat-scenario',f'benchmark-commonwealth-{count}' if a.commonwealth else f'benchmark-ai-{count}','--benchmark'],cwd=ROOT,capture_output=True,text=True,check=True)
   row=json.loads(result.stdout)
   if row['measuredTicks']!=600:raise RuntimeError('Benchmark completed before 600 measured ticks')
   row['repeat']=repeat;rows.append(row);print(count,repeat,row['meanMs'],row['p95Ms'],row['metrics']['aiDecisions'],flush=True)
 summary=[]
 for count in a.counts:
  samples=[r for r in rows if r['units']==count]
  if len({r['checksum'] for r in samples})!=1:raise RuntimeError('AI reproducibility failed')
  metrics=samples[0]['metrics'];summary.append(dict(units=count,**{k:statistics.mean(r[k] for r in samples) for k in ['meanMs','medianMs','p95Ms','ticksPerSecond','measuredWallSeconds','allocatedBytesPerTick']},aiDecisions=metrics['aiDecisions'],targetEvaluations=metrics['aiTargetEvaluations'],aiMeanTickMs=statistics.mean(r['metrics']['aiMilliseconds']/(r['finalTick'] or 1) for r in samples),visibilityQueries=metrics['visibilityQueries'],visibilityCalculations=metrics['visibilityCalculations'],volleys=metrics['volleys'],rounds=metrics['artilleryShots'],charges=metrics['chargeStarts'],routs=metrics['routs']))
 a.output.parent.mkdir(exist_ok=True,parents=True);a.output.write_text(json.dumps(dict(warmup=100,measuredTicks=600,simulatedSeconds=60,repeats=a.repeats,summary=summary,samples=rows),indent=2)+'\n')
 with a.output.with_suffix('.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
if __name__=='__main__':main()
