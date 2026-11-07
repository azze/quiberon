"""Active mixed-roster scaling benchmarks; timings and profiles run separately."""
import argparse
import cProfile
import csv
import json
import os
from pathlib import Path
import platform
import pstats
import statistics
from time import perf_counter
from scenarios.battle_config import ArmyConfig, BattleConfig
from simulation.terrain import TERRAIN_PRESETS
from .performance import fingerprint

COUNTS=(6,12,18,24,36,60)
ROSTER=('prussian_line','cavalry','french_horse_artillery','infantry','haudenosaunee_skirmishers',
        'royal_grenadiers','commonwealth_uhlans','revolutionary_rifles','artillery')


def scenario(count,terrain,seed=17):
    if count<2 or count%2: raise ValueError('Use an even total regiment count >= 2')
    army=ArmyConfig(0,0,0)
    for i in range(count//2):
        key=ROSTER[i%len(ROSTER)]; army=army.with_count(key,army.count(key)+1)
    return BattleConfig(seed=seed,blue=army,red=army,max_total=max(48,count),
                        ai_armies=(0,1),terrain_preset=terrain).prepared()


def distribution(values):
    values=sorted(values)
    return dict(mean_ms=statistics.mean(values),median_ms=statistics.median(values),
                p95_ms=values[min(len(values)-1,int(len(values)*.95))])


def warm(config,ticks):
    battle=config.create_battle()
    # Stage both deployments 130 m forward to exercise combat without timing a
    # long march. Same rigid translation for every army size; no stats change.
    from simulation.geometry import Vec
    for unit in battle.units: unit.pos+=Vec(130 if unit.army==0 else -130,0)
    battle.deployment_positions={u.id:u.pos for u in battle.units}
    for _ in range(ticks): battle.step()
    if battle.result: raise ValueError('Battle finished during warmup')
    return battle


def measure(config,warmup,ticks,repeats=2,frames=0,profile_path=None,paced=False,speed=1):
    timings=[]; checksums=[]; samples=[]; active=[]; projectiles=[]; walls=[]
    for repeat in range(repeats):
        battle=warm(config,warmup); start=perf_counter(); times=[]
        for _ in range(ticks):
            before=perf_counter(); battle.step(); times.append((perf_counter()-before)*1000)
            active.append(sum(u.active for u in battle.units)); projectiles.append(len(battle.projectiles))
            if battle.result: raise ValueError('Battle ended in measured window; shorten ticks')
        walls.append(perf_counter()-start); timings.extend(times); samples.append(distribution(times))
        checksums.append(fingerprint(battle))
    if len(set(checksums))!=1: raise AssertionError('Nondeterministic benchmark replay')
    row=dict(units=len(battle.units),terrain=config.terrain_preset,seed=config.seed,warmup_ticks=warmup,
             measured_ticks=ticks,repeats=repeats,simulated_seconds=ticks*battle.rules.dt,
             wall_seconds=statistics.mean(walls),ticks_per_wall_second=ticks/statistics.mean(walls),
             active_units_mean=statistics.mean(active),active_projectiles_mean=statistics.mean(projectiles),
             active_projectiles_max=max(projectiles),state_sha256=checksums[0],tick=distribution(timings),repeat_ticks=samples,
             activity=dict(volleys=sum(u.analysis['volleys'] for u in battle.units),charges=sum(u.analysis['charges'] for u in battle.units),
                           losses=sum(u.stats.strength-u.strength for u in battle.units),**battle.metrics))
    if frames: row['graphics']=graphics(config,warmup,frames,paced=paced,speed=speed)
    if profile_path:
        profile_path=Path(profile_path); profile_path.parent.mkdir(parents=True,exist_ok=True)
        probe=warm(config,warmup); profiler=cProfile.Profile();profiler.enable()
        for _ in range(ticks): probe.step()
        profiler.disable();profiler.dump_stats(str(profile_path))
        stats=pstats.Stats(profiler)
        counts={}
        names={'visibility','get_elevation','forest_density','gradient','touching','separation','intersection_area','segment_rect','army_plan','destination'}
        for (file,line,name),value in stats.stats.items():
            if name in names: counts[Path(file).name+':'+name]=value[1]
        row['profile_counts']=counts
        row['scheduled_army_updates']=sum(t%50==0 for t in range(warmup,warmup+ticks))*len(battle.ai_armies)
        with profile_path.with_suffix('.txt').open('w') as out:
            pstats.Stats(profiler,stream=out).strip_dirs().sort_stats('cumulative').print_stats(35)
            pstats.Stats(profiler,stream=out).strip_dirs().sort_stats('tottime').print_stats(20)
        if fingerprint(probe)!=checksums[0]: raise AssertionError('Profiling changed outcome')
    try:
        import resource
        row['process_peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024 if platform.system()=='Linux' else 1024**2)
    except ImportError: pass
    return row


def graphics(config,warmup,frames,paced=False,speed=1):
    os.environ.setdefault('SDL_VIDEODRIVER','dummy'); os.environ.setdefault('SDL_AUDIODRIVER','dummy')
    import pygame
    from viewer.application import Application
    pygame.init(); results={}
    try:
        screen=pygame.display.set_mode((1280,800))
        for debug in (False,True):
            app=Application(screen); app.start(config)
            app.battle=warm(config,warmup)
            app.controls.speed=speed; app.controls.debug=debug; app.controls.selected=0; app.motion.capture(app.battle)
            start=perf_counter(); app.draw(); first=(perf_counter()-start)*1000
            for _ in range(5): app.draw()
            draws=[]; updates=[]; clock=pygame.time.Clock(); start=perf_counter(); tick=app.battle.tick; limited=0
            for _ in range(frames):
                elapsed=clock.tick(60)/1000 if paced else 1/60
                a=perf_counter(); app.update(elapsed); limited+=int(app.controls.slow); updates.append((perf_counter()-a)*1000)
                a=perf_counter(); app.draw(); draws.append((perf_counter()-a)*1000)
            wall=perf_counter()-start
            results['debug' if debug else 'normal']=dict(render=distribution(draws),update=distribution(updates),
                loop_fps=frames/wall,paced=paced,requested_speed=speed,limited_frames=limited,pending_sim_seconds=app.accumulator,achieved_speed=(app.battle.tick-tick)*app.battle.rules.dt/wall,
                first_frame_ms=first,display_driver=pygame.display.get_driver(),frames=frames,pygame=pygame.version.ver)
    finally: pygame.quit()
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--counts',type=int,nargs='+',default=COUNTS)
    p.add_argument('--terrains',nargs='+',choices=TERRAIN_PRESETS,default=['Open Field','Mixed Terrain'])
    p.add_argument('--seed',type=int,default=17);p.add_argument('--warmup',type=int,default=100)
    p.add_argument('--ticks',type=int,default=100);p.add_argument('--repeats',type=int,default=2)
    p.add_argument('--frames',type=int,default=0);p.add_argument('--paced',action='store_true',help='60 FPS cap using real elapsed time');p.add_argument('--speed',type=int,choices=(1,2,4,10),default=1);p.add_argument('--profile-dir',type=Path)
    p.add_argument('--output',type=Path,default=Path('benchmark-results/scaling.json'))
    p.add_argument('--compare',type=Path)
    a=p.parse_args()
    if min(a.ticks,a.repeats)<1 or min(a.frames,a.warmup)<0:p.error('Invalid durations')
    if any(n<2 or n%2 for n in a.counts): p.error('Counts must be positive even army totals.')
    rows=[]; a.output.parent.mkdir(parents=True,exist_ok=True)
    json_path=a.output.with_suffix('.json')
    reference=json.loads(a.compare.read_text()) if a.compare else None
    if reference and reference.get('workload')!='forward130-v1': p.error('Comparison workload metadata does not match forward130-v1')
    for terrain in a.terrains:
        for count in a.counts:
            if reference:
                previous=next((r for r in reference['battles'] if (r['units'],r['terrain'])==(count,terrain)),None)
                if previous is None or (previous['seed'],previous['warmup_ticks'],previous['measured_ticks'])!=(a.seed,a.warmup,a.ticks):
                    p.error('Comparison requires matching counts, terrain, seed, warmup and measured ticks.')
            config=scenario(count,terrain,a.seed)
            profile=a.profile_dir/f'{count}-{terrain.replace(" ","_")}.prof' if a.profile_dir else None
            row=measure(config,a.warmup,a.ticks,a.repeats,a.frames,profile,a.paced,a.speed)
            rows.append(row); print(json.dumps(row),flush=True)
            report=dict(workload='forward130-v1',python=platform.python_version(),platform=platform.platform(),cpu=platform.processor(),battles=rows)
            json_path.write_text(json.dumps(report,indent=2)+'\n')
    if a.compare:
        old=reference
        for row in rows:
            before=next(r for r in old['battles'] if (r['units'],r['terrain'])==(row['units'],row['terrain']))
            print(f'{row["units"]:2} {row["terrain"]}: {before["tick"]["mean_ms"]:.2f} -> {row["tick"]["mean_ms"]:.2f} ms ({before["tick"]["mean_ms"]/row["tick"]["mean_ms"]:.2f}x); exact={before["state_sha256"]==row["state_sha256"]}')
    with a.output.with_suffix('.csv').open('w',newline='') as out:
        columns=['units','terrain','mean_ms','median_ms','p95_ms','ticks_per_wall_second','wall_seconds','state_sha256']
        writer=csv.DictWriter(out,fieldnames=columns);writer.writeheader()
        for r in rows:writer.writerow({k:(r['tick'][k] if k in r['tick'] else r[k]) for k in columns})

if __name__=='__main__':main()
