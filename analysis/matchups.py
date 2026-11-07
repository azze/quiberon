"""Seeded specialist presets, replayed from both deployment sides."""
import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
import statistics
from scenarios.presets import SPECIALIST_PRESETS, load_preset
from simulation.geometry import Vec
from .batch_simulation import run


def swap_sides(config):
    """Mirror regiments/orders across x, keeping the SAME terrain for both runs."""
    def mirror(point): return None if point is None else Vec(config.width-point.x,point.y)
    placements=tuple(replace(p,army=1-p.army,pos=mirror(p.pos),facing=math.pi-p.facing,
        order=replace(p.order,destination=mirror(p.order.destination),
                      facing=None if p.order.facing is None else math.pi-p.order.facing)) for p in config.placements)
    return replace(config,blue=config.red,red=config.blue,placements=placements,ai_strategies=tuple(reversed(config.ai_strategies)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preset',choices=SPECIALIST_PRESETS,action='append',help='Repeat for multiple presets; default all')
    parser.add_argument('--runs',type=int,default=2,help='Seeds per preset; each seed runs on both sides')
    parser.add_argument('--seed',type=int,default=1)
    parser.add_argument('--duration',type=float,default=300.)
    parser.add_argument('--output',type=Path,default=Path('matchups.json'))
    args=parser.parse_args()
    if args.runs<1 or not math.isfinite(args.duration) or args.duration<=0: parser.error('Positive runs and finite duration required.')
    if not -(2**63)<=args.seed<2**63 or args.seed+args.runs>2**63: parser.error('Seed sequence must fit signed 64-bit range.')
    rows=[]
    for name in args.preset or SPECIALIST_PRESETS:
        for seed in range(args.seed,args.seed+args.runs):
            config=replace(load_preset(name),seed=seed,ai_armies=(0,1)).prepared()
            for swapped in (False,True):
                row=run(seed,args.duration,config=swap_sides(config) if swapped else config)
                row.update(preset=name,swapped=swapped)
                rows.append(row)
                print(json.dumps({key:row[key] for key in ('preset','seed','swapped','winner','duration','casualties_0','casualties_1')}),flush=True)
    summary={}
    for name in sorted({r['preset'] for r in rows}):
        group=[r for r in rows if r['preset']==name]
        summary[name]=dict(battles=len(group),mean_duration=statistics.mean(r['duration'] for r in group),
                          specialist_wins=sum(r['winner']==('army_1' if r['swapped'] else 'army_0') for r in group),
                          opponent_wins=sum(r['winner']==('army_0' if r['swapped'] else 'army_1') for r in group),
                          timeouts=sum(r['winner']=='timeout' for r in group))
    args.output.write_text(json.dumps(dict(battles=rows,summary=summary),indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
