"""Measure live Godot .NET movement/presentation separately from console ticks."""
import argparse
import json
from pathlib import Path
import subprocess
from .movement_reference import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--counts',type=int,nargs='+',default=[12,24,36,60])
    parser.add_argument('--frames',type=int,default=600)
    parser.add_argument('--headless',action='store_true',help='Validation only; not a GPU timing')
    parser.add_argument('--combat',action='store_true',help='Use the M2 mixed-terrain shooting/melee workloads')
    parser.add_argument('--commonwealth',action='store_true',help='Stage-1 mixed roster and army-command workloads')
    parser.add_argument('--environment',choices=['baseline','river','roads','rain','fog'],help='Environmental movement/crossing workload')
    parser.add_argument('--ai',action='store_true',help='M5 autonomous battles with named commanders')
    parser.add_argument('--artillery',action='store_true',help='Use M4 combined-arms workloads with physical projectiles and specialists')
    parser.add_argument('--dynamics',action='store_true',help='Use M3 combat, routing, charges and pursuit after 14 simulated seconds')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'benchmark-results')
    args=parser.parse_args()
    if args.frames<1 or any(n<2 or n>256 for n in args.counts):parser.error('Use positive frames and counts 2–256')
    args.output_dir=args.output_dir.resolve();args.output_dir.mkdir(parents=True,exist_ok=True)
    for count in args.counts:
        stem=('environment-'+args.environment+'-live-' if args.environment else 'commonwealth-live-' if args.commonwealth else 'ai-live-' if args.ai else 'artillery-live-' if args.artillery else 'dynamics-live-' if args.dynamics else 'combat-live-' if args.combat else 'live-')+str(count)
        output=args.output_dir/(stem+'.json');output.unlink(missing_ok=True)
        command=['bash','tools/godot.sh','--rendering-method','gl_compatibility']
        if args.headless:command.append('--headless')
        source=[f'--combat-scenario=benchmark-environment-{args.environment}-{count}','--live-warmup-ticks=300','--live-speed=4'] if args.environment else [f'--combat-scenario=benchmark-commonwealth-{count}','--live-warmup-ticks=140','--live-speed=4'] if args.commonwealth else [f'--combat-scenario=benchmark-ai-{count}','--live-warmup-ticks=140','--live-speed=4'] if args.ai else [f'--combat-scenario=benchmark-combined-{count}','--live-warmup-ticks=140','--live-speed=4'] if args.artillery else [f'--combat-scenario=benchmark-dynamics-{count}','--live-warmup-ticks=140','--live-speed=4'] if args.dynamics else [f'--combat-scenario=benchmark-{count}','--legacy-combat'] if args.combat else [f'--live-count={count}','--march']
        command+=['--','--live',*source,'--camera-span=800',f'--benchmark-frames={args.frames}','--benchmark-output='+str(output)]
        result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=90)
        log=result.stdout+result.stderr;(args.output_dir/(stem+'.log')).write_text(log)
        if result.returncode or 'SCRIPT ERROR' in log or not output.exists():raise SystemExit('Live benchmark failed: '+log)
        report=json.loads(output.read_text())
        if report.get('source')!='live-csharp':raise SystemExit('Benchmark did not run the C# source')
        print(json.dumps(report),flush=True)

if __name__=='__main__':main()
