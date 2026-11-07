"""Headless seeded runs, JSON or CSV, plus aggregate statistics."""
import argparse
import csv
import json
import statistics
from pathlib import Path
from scenarios import movement_test, standard_battle


def type_statistics(battle):
    """Flat numeric columns work in both JSON and the existing CSV writer."""
    result={}
    groups=sorted({(u.army,u.archetype.id) for u in battle.units})
    for army,archetype_id in groups:
        units=[u for u in battle.units if u.army==army and u.archetype.id==archetype_id]
        prefix=f'army{army}_{archetype_id}_'
        values={key:sum(u.analysis[key] for u in units) for key in units[0].analysis}
        values.update(regiments=len(units),remaining=sum(u.strength for u in units),
                      casualties=sum(u.stats.strength-u.strength for u in units))
        values['casualties_per_volley']=values['volley_casualties']/max(1,values['volleys'])
        values['mean_firing_distance']=values['firing_distance_total']/max(1,values['volleys'])
        result.update({prefix+key:value for key,value in values.items()})
    return result


def run(seed=1, duration=900., scenario='standard', spectator=False, config=None):
    if config is not None:
        from dataclasses import replace
        b=replace(config,seed=seed).create_battle(spectator=spectator)
    else:
        b=(movement_test if scenario=='movement' else standard_battle).create(seed,spectator=spectator)
    for _ in range(int(duration/b.rules.dt)):
        b.step()
        if b.result is not None: break
    row=dict(seed=seed,winner=b.result or 'timeout',duration=round(b.time,1),**b.metrics)
    for army,initial in b.initial_strength.items():
        remaining=sum(u.strength for u in b.units if u.army==army)
        row[f'casualties_{army}']=initial-remaining
        row[f'remaining_{army}']=remaining
    row.update(type_statistics(b))
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scenario',choices=['standard','movement'],default='standard')
    p.add_argument('--runs',type=int,default=10)
    p.add_argument('--seed',type=int,help='Starting seed; saved seed is the default for --config')
    p.add_argument('--config',type=Path,help='Saved battle configuration')
    from scenarios.presets import PRESETS,load_preset
    p.add_argument('--preset',choices=PRESETS,help='Editable built-in battle matchup')
    p.add_argument('--duration',type=float,default=900)
    p.add_argument('--spectator',action='store_true')
    p.add_argument('--output',type=Path,default=Path('results.json'))
    a=p.parse_args()
    if a.runs<1 or a.duration<=0: p.error('runs and duration must be positive')
    config=None
    if a.config and a.preset: p.error('Choose --config or --preset.')
    if a.preset: config=load_preset(a.preset)
    if a.config:
        from scenarios.battle_config import BattleConfig,ConfigError
        try: config=BattleConfig.load(a.config).prepared()
        except ConfigError as exc: p.error(str(exc))
    starting_seed=a.seed if a.seed is not None else (config.seed if config and config.seed is not None else 1)
    if config and starting_seed+a.runs-1 >= 2**63: p.error('Seed sequence exceeds signed 64-bit range.')
    rows=[]
    for seed in range(starting_seed,starting_seed+a.runs):
        rows.append(run(seed,a.duration,a.scenario,a.spectator,config))
        print(json.dumps(rows[-1]),flush=True)
    aggregate={'runs':len(rows),'mean_duration':statistics.mean(r['duration'] for r in rows),
               'wins':{winner:sum(r['winner']==winner for r in rows) for winner in sorted({r['winner'] for r in rows})},
               'means':{key:statistics.mean(r[key] for r in rows) for key in rows[0] if key not in ('seed','winner')}}
    if a.output.suffix=='.csv':
        with a.output.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        a.output.with_suffix('.summary.json').write_text(json.dumps(aggregate,indent=2)+'\n')
    else: a.output.write_text(json.dumps({'battles':rows,'aggregate':aggregate},indent=2)+'\n')
    print(json.dumps(aggregate,indent=2))

if __name__=='__main__': main()
