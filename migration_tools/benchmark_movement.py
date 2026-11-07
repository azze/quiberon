"""Compare equivalent Python and C# movement phases, excluding AI/combat/rendering."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
from statistics import mean
import sys
from .movement_reference import ROOT,FIXTURES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--counts',type=int,nargs='+',default=[12,24,36,60])
    parser.add_argument('--output',type=Path,default=ROOT/'benchmark-results/csharp-movement.json')
    args=parser.parse_args()
    if args.repeats<1 or any(n not in [12,24,36,60] for n in args.counts):parser.error('Use positive repeats and prepared counts 12/24/36/60')
    runner=ROOT/'godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll'
    if not runner.exists():parser.error('Build Simulation.Runner in Release first')
    samples=[]
    for repeat in range(args.repeats):
        # Sequential measurements: no overlapping Python/C# battles or renderers.
        result=subprocess.run([sys.executable,'-m','migration_tools.movement_reference','--benchmark','--counts',*[str(n) for n in args.counts]],cwd=ROOT,text=True,capture_output=True,check=True)
        for row in json.loads(result.stdout):row['repeat']=repeat;samples.append(row)
        for count in args.counts:
            result=subprocess.run(['bash','tools/dotnet.sh',str(runner),'--scenario',str(FIXTURES/f'benchmark-{count}.json'),'--benchmark'],cwd=ROOT,text=True,capture_output=True,check=True)
            row=json.loads(result.stdout);row['repeat']=repeat;samples.append(row)
        print(f'Completed repeat {repeat+1}/{args.repeats}',flush=True)
    summary=[]
    for count in args.counts:
        row={'units':count}
        for language in ['python','csharp']:
            rows=[r for r in samples if r['units']==count and r['language']==language]
            for key in ['meanMs','medianMs','p95Ms','ticksPerSecond','measuredWallSeconds']:
                row[language+key[0].upper()+key[1:]]=mean(r[key] for r in rows)
            if language=='csharp':row['csharpAllocatedBytesPerTick']=mean(r['allocatedBytesPerTick'] for r in rows)
        row['speedup']=row['pythonMeanMs']/row['csharpMeanMs'];summary.append(row)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(workload='movement-only-v1',warmupTicks=100,measuredTicks=600,seed=17,repeats=args.repeats,summary=summary,samples=samples),indent=2)+'\n')
    with args.output.with_suffix('.csv').open('w') as file:
        writer=csv.DictWriter(file,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
