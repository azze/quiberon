"""Equivalent M2 infantry workloads: no morale, charges, artillery or army AI.

Uses the same scenario JSON, standing orders, SplitMix64 draws and 0.1 s phases.
Sequential wall-clock measurements, 100 warm-up + 600 measured ticks per run.
This is not a comparison with the complete Python battle engine.
"""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter_ns
from .combat_reference import ROOT, SCENARIOS, make, combat_tick


def python_sample(path):
    data=json.loads(path.read_text());b,schedule=make(data);timings=[]
    wall=perf_counter_ns()
    for tick in range(700):
        start=perf_counter_ns();combat_tick(b,schedule)
        if tick>=100:timings.append((perf_counter_ns()-start)/1e6)
    total=(perf_counter_ns()-wall)/1e9;timings.sort()
    final=[dict(id=u.id,position=asdict(u.pos),facing=u.facing,strength=u.strength,cohesion=u.cohesion,reload=u.reload_left) for u in b.units]
    return dict(language='python',units=len(b.units),seed=data['seed'],meanMs=mean(timings),medianMs=timings[300],p95Ms=timings[570],
                ticksPerSecond=1000/mean(timings),measuredWallSeconds=sum(timings)/1000,totalWallSeconds=total,
                measuredTicks=600,simulatedSeconds=60,checksum=hashlib.sha256(json.dumps(final,sort_keys=True).encode()).hexdigest(),
                randomDraws=b.rng.draws,volleys=sum(u.analysis['volleys'] for u in b.units),
                casualties=sum(u.stats.strength-u.strength for u in b.units),finalStrengths=[u.strength for u in b.units])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--counts',type=int,nargs='+',default=[12,24,36,60])
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--output',type=Path,default=ROOT/'benchmark-results/csharp-combat.json')
    args=parser.parse_args()
    if args.repeats<1 or any(n not in [12,24,36,60] for n in args.counts):parser.error('Use positive repeats and counts 12/24/36/60')
    runner=ROOT/'godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll'
    if not runner.exists():parser.error('Build Simulation.Runner in Release first')
    samples=[]
    for repeat in range(args.repeats):
        for count in args.counts:
            path=SCENARIOS/f'benchmark-{count}.json'
            py=python_sample(path);py['repeat']=repeat;samples.append(py)
            result=subprocess.run(['bash','tools/dotnet.sh',str(runner),'--scenario',str(path),'--benchmark'],cwd=ROOT,text=True,capture_output=True,check=True)
            cs=json.loads(result.stdout);cs['repeat']=repeat;samples.append(cs)
            # Both have active volleys/melee. Their portable streams should retain
            # identical draw counts; full formulas/traces are checked by xUnit.
            if py['randomDraws']!=cs['randomDraws'] or not cs['metrics']['volleys'] or not cs['metrics']['meleePulses']:
                raise RuntimeError(f'Workload drift/inactive combat at {count}: Python draws {py["randomDraws"]}, C# draws {cs["randomDraws"]}')
            if py['finalStrengths']!=cs['finalStrengths']:raise RuntimeError(f'Casualty outcomes diverged at {count}')
            print(f'Repeat {repeat+1}/{args.repeats}, {count}: Python {py["meanMs"]:.3f} ms / C# {cs["meanMs"]:.3f} ms',flush=True)
    summary=[]
    for count in args.counts:
        row={'units':count}
        for language in ['python','csharp']:
            rows=[r for r in samples if r['units']==count and r['language']==language]
            for key in ['meanMs','medianMs','p95Ms','ticksPerSecond','measuredWallSeconds']:
                row[language+key[0].upper()+key[1:]]=mean(r[key] for r in rows)
            if language=='csharp':
                row['allocatedBytesPerTick']=mean(r['allocatedBytesPerTick'] for r in rows)
                row.update(rows[0]['metrics'])
                if len({r['checksum'] for r in rows})!=1:raise RuntimeError('C# reproducibility failure')
        row['scopedSpeedup']=row['pythonMeanMs']/row['csharpMeanMs'];summary.append(row)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(workload='m2-ordinary-infantry-v1',seed=17,warmupTicks=100,measuredTicks=600,repeats=args.repeats,summary=summary,samples=samples),indent=2)+'\n')
    with args.output.with_suffix('.csv').open('w') as file:
        writer=csv.DictWriter(file,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
