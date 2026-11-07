"""Matched M3 fixed-step combat/routing/charge/pursuit workloads, no rendering.

Python runs actual Battle.step with no army AI, commander/specialist abilities or
projectiles. C# runs that supported slice. Includes Python's existing analysis
bookkeeping; this is not a comparison with the complete game or future engine.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter_ns
from .dynamics_reference import ROOT,SCENARIOS,make,queue
from .movement_reference import compare


def python_sample(path,seed=None):
    data=json.loads(path.read_text())
    if seed is not None:data['seed']=seed
    b,schedule=make(data);timings=[];started=perf_counter_ns()
    for tick in range(700):
        if b.result is not None:raise RuntimeError('Benchmark completed prematurely')
        start=perf_counter_ns();queue(b,schedule);b.step()
        if tick>=100:timings.append((perf_counter_ns()-start)/1e6)
    total=(perf_counter_ns()-started)/1e9;timings.sort()
    states=[dict(id=u.id,position=dict(x=u.pos.x,y=u.pos.y),strength=u.strength,morale=u.morale,cohesion=u.cohesion,state=u.state.value,withdrawn=u.withdrawn) for u in b.units]
    return dict(language='python',units=len(b.units),seed=data['seed'],meanMs=mean(timings),medianMs=timings[300],p95Ms=timings[570],
                ticksPerSecond=1000/mean(timings),measuredWallSeconds=sum(timings)/1000,totalWallSeconds=total,
                measuredTicks=600,simulatedSeconds=60,randomDraws=b.rng.draws,finalStates=states,
                checksum=hashlib.sha256(json.dumps(states,sort_keys=True).encode()).hexdigest(),
                routs=b.metrics['routs'],rallies=b.metrics['rallies'],chargeStarts=sum(u.analysis['charge_initiations'] for u in b.units),
                chargeImpacts=sum(u.analysis['charges'] for u in b.units),pursuitCasualties=sum(u.analysis['pursuit_casualties'] for u in b.units),
                pursuitLosses=sum(u.analysis['pursuit_losses'] for u in b.units))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--counts',type=int,nargs='+',default=[12,24,36,60]);parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--seed',type=int,default=17)
    parser.add_argument('--output',type=Path,default=ROOT/'benchmark-results/csharp-dynamics.json');args=parser.parse_args()
    if args.repeats<1 or any(n not in [12,24,36,60] for n in args.counts):parser.error('Use positive repeats and counts 12/24/36/60')
    runner=ROOT/'godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll'
    if not runner.exists():parser.error('Build Simulation.Runner in Release first')
    samples=[]
    for repeat in range(args.repeats):
        for count in args.counts:
            path=SCENARIOS/f'benchmark-dynamics-{count}.json';py=python_sample(path,args.seed)
            result=subprocess.run(['bash','tools/dotnet.sh',str(runner),'--scenario',str(path),'--seed',str(args.seed),'--benchmark'],cwd=ROOT,text=True,capture_output=True,check=True)
            cs=json.loads(result.stdout)
            compare(dict(name='final-state',units=py['finalStates']),dict(name='final-state',units=cs['finalStates']))
            for key in ('routs','chargeStarts','chargeImpacts','pursuitCasualties','pursuitLosses'):
                if py[key]!=cs['metrics'][key]:raise RuntimeError(f'{count} {key}: Python {py[key]} / C# {cs["metrics"][key]}')
            if py['randomDraws']!=cs['randomDraws']:raise RuntimeError('Random consumption diverged')
            if not all(cs['metrics'][key]>0 for key in ('routs','chargeStarts','chargeImpacts','pursuitCasualties')):raise RuntimeError('Inactive benchmark')
            for row in (py,cs):row['repeat']=repeat;samples.append(row)
            print(f'Repeat {repeat+1}/{args.repeats}, {count}: Python {py["meanMs"]:.3f} ms / C# {cs["meanMs"]:.3f} ms',flush=True)
    summary=[]
    for count in args.counts:
        row={'units':count}
        for language in ('python','csharp'):
            rows=[r for r in samples if r['units']==count and r['language']==language]
            for key in ('meanMs','medianMs','p95Ms','ticksPerSecond','measuredWallSeconds'):row[language+key[0].upper()+key[1:]]=mean(r[key] for r in rows)
            if language=='csharp':
                row['allocatedBytesPerTick']=mean(r['allocatedBytesPerTick'] for r in rows);row.update(rows[0]['metrics'])
                if len({r['checksum'] for r in rows})!=1:raise RuntimeError('C# reproducibility failed')
        row['scopedSpeedup']=row['pythonMeanMs']/row['csharpMeanMs'];summary.append(row)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(workload='m3-dynamics-v1',seed=args.seed,warmupTicks=100,measuredTicks=600,repeats=args.repeats,summary=summary,samples=samples),indent=2)+'\n')
    with args.output.with_suffix('.csv').open('w') as file:
        writer=csv.DictWriter(file,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
