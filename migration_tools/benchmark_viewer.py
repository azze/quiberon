"""Prepare active recordings and benchmark Godot separately from Python ticks."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from time import perf_counter
from .record_battle import create_battle,record

ROOT=Path(__file__).resolve().parents[1]


def prepare(count,folder):
    path=folder/f'{count}-units'
    if (path/'metadata.json').exists():return path
    # Independent no-export run for actual simulation tick timing.
    battle,_=create_battle(count=count)
    timings=[]
    for i in range(300):
        start=perf_counter();battle.step()
        if i>=100:timings.append((perf_counter()-start)*1000)
    timings.sort()
    battle,name=create_battle(count=count)
    export=record(battle,path,name,30,1)
    info=dict(units=count,seed=17,terrain='Mixed Terrain',warmup_ticks=100,measured_ticks=200,
              tick_mean_ms=sum(timings)/len(timings),tick_p95_ms=timings[int(len(timings)*.95)],export=export)
    (path/'python-timing.json').write_text(json.dumps(info,indent=2)+'\n')
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--counts',type=int,nargs='+',default=[12,24,36,60])
    parser.add_argument('--mode',choices=['prepare','headless','graphics'],default='prepare')
    parser.add_argument('--viewer',choices=['2d','3d'],default='3d')
    parser.add_argument('--frames',type=int,default=600);parser.add_argument('--godot',default=shutil.which('godot') or 'godot')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'benchmark-results/godot')
    args=parser.parse_args()
    if args.frames<1 or any(n<2 or n%2 for n in args.counts):parser.error('Use positive frames and even regiment totals >=2.')
    args.output_dir=args.output_dir.resolve();args.output_dir.mkdir(parents=True,exist_ok=True)
    for count in args.counts:
        path=prepare(count,args.output_dir)
        if args.mode=='prepare':print(path,flush=True);continue
        output=path/f'{args.mode}-{args.viewer}.json'
        command=[args.godot,'--path',str(ROOT/'godot'),'--scene','res://scenes/battlefield_3d.tscn' if args.viewer=='3d' else 'res://scenes/battlefield.tscn','--rendering-method','gl_compatibility']
        if args.mode=='headless':command.append('--headless')
        command+=['--','--recording='+str(path/'metadata.json'),'--seek=15',f'--benchmark-frames={args.frames}','--benchmark-output='+str(output)]
        result=subprocess.run(command,text=True,capture_output=True,timeout=120)
        (path/f'{args.mode}-{args.viewer}.log').write_text(result.stdout+result.stderr)
        if result.returncode or not output.exists() or 'SCRIPT ERROR' in result.stdout+result.stderr:raise SystemExit(f'Godot failed: {result.stdout}{result.stderr}')
        print(output.read_text(),flush=True)

if __name__=='__main__':main()
