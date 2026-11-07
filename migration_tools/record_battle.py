"""Export a seeded Python battle for the Godot viewer, without importing Pygame."""
import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
from time import perf_counter
from .recording import BattleRecorder
from scenarios.battle_config import BattleConfig
from scenarios.presets import PRESETS,load_preset
from simulation.terrain import TERRAIN_PRESETS


def create_battle(seed=17,count=12,terrain='Mixed Terrain',config=None,advance=None):
    if config is None:
        from analysis.scaling import scenario
        config=scenario(count,terrain,seed)
        advance=130. if advance is None else advance
        name=f'migration-demo/{count}/{terrain}/forward{advance:g}'
    else:
        config=replace(config,seed=seed).with_ai_armies((0,1)).prepared()
        advance=0. if advance is None else advance
        name=config.name
    battle=config.create_battle()
    if advance:
        from simulation.geometry import Vec
        for u in battle.units:u.pos+=Vec(advance if u.army==0 else -advance,0)
        battle.deployment_positions={u.id:u.pos for u in battle.units}
    return battle,name


def record(battle,path,scenario,duration=600.,interval_ticks=1):
    if not math.isfinite(duration) or duration<=0:raise ValueError('duration must be positive and finite.')
    start=perf_counter()
    with BattleRecorder(battle,path,scenario,interval_ticks) as writer:
        for _ in range(max(1,math.ceil(duration/battle.rules.dt))):
            if battle.result:break
            battle.step();writer.capture()
    return dict(path=str(path),result=battle.result or 'limit',simulated_seconds=battle.time,
                wall_seconds=perf_counter()-start,frames=writer.count,events=writer.sequence)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group();group.add_argument('--config',type=Path);group.add_argument('--preset',choices=PRESETS)
    p.add_argument('--seed',type=int,default=17);p.add_argument('--count',type=int,default=12,help='Even demo army total; used without config/preset')
    p.add_argument('--terrain',choices=TERRAIN_PRESETS,default='Mixed Terrain')
    p.add_argument('--advance',type=float,help='Demo advances each deployment 130 m by default; recipes default to 0')
    p.add_argument('--duration',type=float,default=600.,help='Maximum simulated seconds; stop early at actual battle result')
    p.add_argument('--interval-ticks',type=int,default=1,help='Snapshot stride; events still record every emission')
    p.add_argument('--output',type=Path,default=Path('recordings/battle'))
    a=p.parse_args()
    try:
        if a.advance is not None and not math.isfinite(a.advance):raise ValueError('advance must be finite.')
        config=BattleConfig.load(a.config) if a.config else load_preset(a.preset) if a.preset else None
        battle,name=create_battle(a.seed,a.count,a.terrain,config,a.advance)
        print(json.dumps(record(battle,a.output,name,a.duration,a.interval_ticks)),flush=True)
    except (ValueError,OSError) as exc:p.error(str(exc))

if __name__=='__main__':main()
