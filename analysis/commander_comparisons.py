"""Small mirrored commander experiments with per-officer performance records."""
import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
from scenarios.commander_comparisons import COMMANDER_PRESETS,create
from .battle_report import battle_report
from .matchups import swap_sides


def run(name,seed=17,duration=180.,swapped=False):
    # Fix officer/map generation to 17; varying seeds change combat RNG only.
    config=replace(create(name,17),seed=seed)
    if swapped:config=swap_sides(config)
    battle=config.create_battle()
    for _ in range(int(duration/battle.rules.dt)):
        battle.step()
        if battle.result:break
    report=battle_report(battle)
    report.update(preset=name,swapped=swapped,
                  commander_events=[dict(time=e.time,unit_id=e.unit_id,message=e.message) for e in battle.events if e.kind=='trait'])
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--preset',choices=COMMANDER_PRESETS,action='append')
    p.add_argument('--runs',type=int,default=2);p.add_argument('--seed',type=int,default=17)
    p.add_argument('--duration',type=float,default=180.)
    p.add_argument('--output',type=Path,default=Path('benchmark-results/commander-comparisons.json'))
    a=p.parse_args()
    if a.runs<1 or not math.isfinite(a.duration) or a.duration<=0:p.error('Positive runs and finite duration required.')
    if not -(2**63)<=a.seed<2**63 or a.seed+a.runs>2**63:p.error('Seed sequence must fit signed 64-bit range.')
    rows=[]
    for name in a.preset or COMMANDER_PRESETS:
        for seed in range(a.seed,a.seed+a.runs):
            for swapped in (False,True):
                row=run(name,seed,a.duration,swapped);rows.append(row)
                print(json.dumps(dict(preset=name,seed=seed,swapped=swapped,result=row['result'],duration=row['duration'],
                    losses=[army['lost'] for army in row['armies']])),flush=True)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(dict(battles=rows),indent=2)+'\n')


if __name__=='__main__':main()
