"""Repeatable headless tick timings with optional dummy-display render timings."""
import argparse
from dataclasses import fields, is_dataclass, replace
from enum import Enum
import hashlib
import json
from pathlib import Path
import platform
import statistics
from time import perf_counter
from scenarios.battle_config import BattleConfig, ConfigError
from simulation.terrain import TERRAIN_PRESETS


def fingerprint(battle):
    """Exact-state checksum for comparisons on the same Python/math runtime."""
    def plain(value):
        if isinstance(value,Enum): return value.value
        if is_dataclass(value):
            # New optional campaign fields have a neutral representation so old
            # generic-battle checksums still compare exactly. Active upgrade
            # state is always included.
            neutral={'upgrades':(), 'upgrade_state':{}, 'upgrade_stationary':0.}
            return {f.name:plain(getattr(value,f.name)) for f in fields(value) if f.compare and not
                    (f.name in neutral and getattr(value,f.name)==neutral[f.name])}
        if isinstance(value,dict): return {str(key):plain(val) for key,val in value.items()}
        if isinstance(value,set): return [plain(item) for item in sorted(value)]
        if isinstance(value,(tuple,list)): return [plain(item) for item in value]
        return value
    state=dict(tick=battle.tick,result=battle.result,terrain=battle.terrain,rules=battle.rules,units=battle.units,projectiles=battle.projectiles,
               events=list(battle.events),metrics=battle.metrics,rng=battle.rng.getstate())
    if getattr(battle,'upgrade_next',None):state['upgrade_next']=battle.upgrade_next
    return hashlib.sha256(json.dumps(plain(state),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def benchmark(config,warmup,ticks,render_frames=0,profile=False):
    config=config.prepared()
    battle=config.create_battle()
    for _ in range(warmup):
        battle.step()
        if battle.result: raise ValueError('Battle ended during warm-up; reduce --warmup.')
    timings=[]
    for _ in range(ticks):
        start=perf_counter(); battle.step(); timings.append((perf_counter()-start)*1000)
        if battle.result: break
    ordered=sorted(timings)
    row=dict(terrain=battle.terrain.preset,units=len(battle.units),seed=battle.seed,ticks=len(timings),
             mean_tick_ms=statistics.mean(timings),p95_tick_ms=ordered[min(len(ordered)-1,int(len(ordered)*.95))],
             end_tick=battle.tick,state_sha256=fingerprint(battle))
    if render_frames:
        import os
        os.environ.setdefault('SDL_VIDEODRIVER','dummy'); os.environ.setdefault('SDL_AUDIODRIVER','dummy')
        import pygame
        from viewer.renderer import Renderer
        from viewer.camera import Camera
        from viewer.controls import Controls
        from viewer.interpolation import MotionFrame
        pygame.init()
        try:
            screen=pygame.display.set_mode((1280,800)); camera=Camera(height=800)
            camera.fit(battle.rules.width,battle.rules.height)
            renderer=Renderer(screen,camera); controls=Controls(); controls.selected=0
            render_battle=config.create_battle()
            row['render_tick']=render_battle.tick
            motion=MotionFrame(render_battle)
            start=perf_counter(); renderer.draw(render_battle,controls,motion=motion,alpha=.5)
            row['first_draw_ms']=(perf_counter()-start)*1000
            for _ in range(5): renderer.draw(render_battle,controls,motion=motion,alpha=.5)
            start=perf_counter()
            for _ in range(render_frames): renderer.draw(render_battle,controls,motion=motion,alpha=.5)
            row['render_ms']=(perf_counter()-start)/render_frames*1000
            row['display_driver']=pygame.display.get_driver()
            row['pygame']=pygame.version.ver
        finally: pygame.quit()
    if profile:
        import cProfile
        import pstats
        profiler=cProfile.Profile(); profiler.enable()
        for _ in range(ticks):
            battle.step()
            if battle.result: break
        profiler.disable()
        pstats.Stats(profiler).strip_dirs().sort_stats('cumulative').print_stats(20)
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terrain',choices=TERRAIN_PRESETS,help='Default: compare Open Field and Mixed Terrain')
    parser.add_argument('--config',type=Path,help='Benchmark a saved battle instead')
    parser.add_argument('--seed',type=int)
    parser.add_argument('--warmup',type=int,default=800)
    parser.add_argument('--ticks',type=int,default=200)
    parser.add_argument('--render-frames',type=int,default=0,help='Optional dummy-display rendering benchmark')
    parser.add_argument('--profile',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.ticks<1 or args.warmup<0 or args.render_frames<0: parser.error('ticks must be positive; warmup/render-frames nonnegative.')
    if args.config and args.terrain: parser.error('Choose --config or --terrain.')
    try:
        if args.config:
            config=BattleConfig.load(args.config)
            if args.seed is not None: config=replace(config,seed=args.seed)
            configs=[config]
        else:
            configs=[BattleConfig(seed=17 if args.seed is None else args.seed,terrain_preset=name) for name in ([args.terrain] if args.terrain else ['Open Field','Mixed Terrain'])]
        rows=[]
        for config in configs:
            rows.append(benchmark(config,args.warmup,args.ticks,args.render_frames,args.profile))
            print(json.dumps(rows[-1]),flush=True)
    except (ConfigError,ValueError) as exc: parser.error(str(exc))
    report=dict(python=platform.python_version(),battles=rows)
    if args.output: args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
