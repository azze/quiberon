"""Shared movement-only fixtures, Python oracles and matched C# comparisons.

The movement tick calls the existing authoritative movement/positioning/terrain
functions. Combat, AI target searches and commander abilities are intentionally
excluded in BOTH benchmarks. Nothing in the Python game is changed.
"""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter_ns
from simulation import movement, positioning, morale
from simulation.archetypes import ARCHETYPES
from simulation.battle import Battle
from simulation.config import Rules
from simulation.formations import Formation
from simulation.geometry import Vec, angle_delta
from simulation.orders import Command, Order, OrderKind
from simulation.regiment import Regiment
from simulation.terrain import TerrainMap, Hill, Forest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'migration_tools/movement_fixtures'


def point(x, y):
    return dict(x=x, y=y)


def unit(uid, x, y, *, archetype='infantry', facing=0., formation=None, cohesion=100.):
    result = dict(id=uid, army=0, name=f'Movement Regiment {uid+1}', archetype=archetype,
                  position=point(x, y), facing=facing, cohesion=cohesion)
    if formation: result['formation'] = formation
    return result


def command(tick, uid, x=None, y=None, *, formation=None, facing=None, kind='move'):
    result = dict(tick=tick, regimentId=uid)
    if formation: result['formation'] = formation
    else:
        result['order'] = dict(kind=kind, destination=point(x,y) if x is not None else None, facing=facing)
    return result


def definitions():
    cases = {
        'straight': ([unit(0,200,300)], [command(0,0,450,300)], 140),
        'turning': ([unit(0,300,200,facing=math.pi)], [command(0,0,550,420,facing=-math.pi/2)], 180),
        'formation': ([unit(0,200,300,cohesion=85)], [command(0,0,formation='column'),command(80,0,420,300),command(500,0,formation='line')], 90),
        'friendly-crossing': ([unit(0,350,300),unit(1,530,300,facing=math.pi)], [command(0,0,650,300),command(0,1,200,300)], 180),
        'cavalry-overtaking': ([unit(0,250,300,archetype='cavalry'),unit(1,240,300,archetype='cavalry',cohesion=80)], [command(0,0,800,300),command(0,1,800,300),command(120,0,650,450)], 120),
        'stationary-separation': ([unit(0,400,300),unit(1,400,300)], [command(0,0,kind='hold'),command(0,1,kind='hold')], 100),
        'destination-conflict': ([unit(0,220,300),unit(1,220,390)], [command(0,0,420,340,facing=0),command(0,1,420,340,facing=0)], 180),
        'congested': ([unit(i,300+(i%3)*15,180+(i//3)*55,formation='column' if i%2 else 'line') for i in range(9)], [command(0,i,620,200+(i//3)*55) for i in range(9)], 180),
        'boundaries': ([unit(0,200,300)], [command(0,0,1200,-200),command(500,0,500,300,facing=math.pi)], 180),
        'artillery-march': ([unit(0,250,300,archetype='artillery')], [command(0,0,310,300),command(700,0,kind='hold')], 100),
        'woodland-march': ([unit(0,250,200),unit(1,250,300,archetype='haudenosaunee_skirmishers'),unit(2,250,420,archetype='artillery')], [command(0,i,700,200+i*110) for i in range(3)], 180),
    }
    for name,(units,commands,duration) in cases.items():
        data = dict(version=1,name=name,seed=17,width=1000,height=600,duration=duration,units=units,commands=commands,
                    sampleTicks=sorted({0,1,10,30,70,80,100,200,400,700,int(duration*10)}))
        if name=='cavalry-overtaking': data['units'][1]['fatigue']=50.
        if name=='woodland-march': data['terrain']=dict(hills=[dict(x=500,y=300,radiusX=95,radiusY=120,height=28,compact=True)],forests=[dict(x=420,y=300,radiusX=95,radiusY=190,density=.9)])
        yield data


def benchmark_definition(count, duration=70):
    roster=('infantry','infantry','cavalry','artillery','haudenosaunee_skirmishers')
    units=[]; commands=[]
    for i in range(count):
        right=i%2==0
        u=unit(i,410+(i%6)*18 if right else 570-(i%6)*18,90+(i//6)*70,
               archetype=roster[i%5],facing=0 if right else math.pi)
        units.append(u)
        commands.append(command(0,i,800 if right else 200,u['position']['y']+(15 if right else -15)))
        commands.append(command(500,i,250 if right else 750,u['position']['y']))
    return dict(version=1,name=f'benchmark-{count}',seed=17,width=1000,height=max(600,math.ceil(count/6)*70+100),duration=duration,
                units=units,commands=commands,sampleTicks=[0,100,int(duration*10)])


def create(data):
    units=[Regiment(u['id'],u['name'],u['army'],Vec(**u['position']),facing=u.get('facing',0),archetype_id=u['archetype'],
                    formation=Formation(u['formation']) if 'formation' in u else None,cohesion=u.get('cohesion',100),fatigue=u.get('fatigue',0)) for u in data['units']]
    terrain=data.get('terrain') or {}
    hills=tuple(Hill(h['x'],h['y'],h['radiusX'],h['radiusY'],h['height'],h.get('compact',False)) for h in terrain.get('hills',[]))
    forests=tuple(Forest(f['x'],f['y'],f['radiusX'],f['radiusY'],f.get('density',1)) for f in terrain.get('forests',[]))
    battle=Battle(units,seed=data['seed'],rules=Rules(width=data['width'],height=data['height']),terrain=TerrainMap(data['width'],data['height'],hills,forests),sandbox=True,generate_commanders=False)
    for u in battle.units:movement.clamp_to_field(u,battle.rules.width,battle.rules.height)
    schedule={}
    for c in data['commands']:schedule.setdefault(c['tick'],[]).append(c)
    return battle,schedule


def queue_scheduled(battle,schedule):
    for c in schedule.get(battle.tick,[]):
        raw=c.get('order');order=None
        if raw:order=Order(OrderKind(raw['kind']),Vec(**raw['destination']) if raw.get('destination') else None,facing=raw.get('facing'))
        battle.issue(Command(c['regimentId'],order,Formation(c['formation']) if c.get('formation') else None))


def movement_tick(battle):
    for cmd in battle.commands:
        u=battle.unit(cmd.regiment_id)
        if u is None or not u.effective:continue
        if cmd.order:
            u.order=cmd.order;u.player_order=True;positioning.reset(u);movement.reset_avoidance(u)
        if cmd.formation and cmd.formation in u.archetype.formations and cmd.formation!=u.formation and not u.transition_left and u.stats.kind.value=='infantry':
            u.next_formation=cmd.formation;u.transition_left=battle.rules.formation_seconds;u.cohesion=max(0,u.cohesion-6)
    battle.commands.clear()
    active=[u for u in battle.units if u.active]
    intents={u.id:u.order.destination if u.order.kind in (OrderKind.MOVE,OrderKind.ADVANCE,OrderKind.DEFEND) else None for u in active}
    overlaps=movement.update_congestion(active,battle.rules)
    positioning.settle(battle,active,intents,overlaps)
    destinations={u.id:movement.avoid_friends(u,intents[u.id],active,battle.rules,intents) for u in active}
    for u in active:
        dest=movement.terrain_steer(battle,u,destinations[u.id])
        arrival=u.order.facing if u.order.kind in (OrderKind.MOVE,OrderKind.ADVANCE) and dest in (u.order.destination,u.settling_goal) else None
        if u.settling_facing is not None and dest==u.settling_goal:arrival=u.settling_facing
        movement.move(u,dest,battle.rules.dt,battle.rules.width,battle.rules.height,battle.terrain,battle.rules.terrain,arrival)
        if u.settling_goal is not None and u.settling_facing is not None and (u.pos-u.settling_goal).length()<1 and abs(angle_delta(u.facing,u.settling_facing))<.001:u.settling_facing=None
    movement.update_congestion(active,battle.rules,battle.rules.dt)
    for u in active:morale.recover_cohesion(u,battle.rules,battle.rules.dt)
    movement.separate(active,battle.rules.width,battle.rules.height)
    battle.tick+=1


def state(battle):
    def vec(value):return asdict(value) if value is not None else None
    def describe(u):
        if u.transition_left>0:return 'changing formation'
        if u.limber_left>0:return 'limbering'
        if u.setup_left>0 and u.speed<.1:return 'deploying'
        if u.speed>.1 and (u.velocity or Vec(0,0)).length()>.1:return 'moving'
        if u.settling_goal is not None and (u.settling_goal-u.pos).length()>1:return 'separating'
        if u.order.destination is not None and (u.order.destination-u.pos).length()<1 and (u.order.facing is None or abs(angle_delta(u.facing,u.order.facing))<.001):return 'arrived'
        return 'holding'
    return dict(tick=battle.tick,time=battle.time,units=[dict(id=u.id,army=u.army,position=vec(u.pos),facing=u.facing,formation=u.formation.value,
                cohesion=u.cohesion,fatigue=u.fatigue,speed=u.speed,velocity=vec(u.velocity or Vec(0,0)),order=dict(kind=u.order.kind.value,destination=vec(u.order.destination),facing=u.order.facing),
                movementState=describe(u),transitionLeft=u.transition_left,nextFormation=u.next_formation.value if u.next_formation else None,settlingGoal=vec(u.settling_goal),positionPreference=vec(u.position_preference),
                congestion=u.congestion,congestionSpeed=u.congestion_speed,congestionLoss=u.congestion_loss,terrainSpeed=u.terrain_speed,terrainLoss=u.terrain_loss,forestCover=u.forest_cover,groundSlope=u.ground_slope,limberLeft=u.limber_left,setupLeft=u.setup_left)
                for u in battle.units])


def run(data):
    battle,schedule=create(data); samples={*data['sampleTicks'],int(round(data['duration']*10))};frames=[]
    while True:
        if battle.tick in samples:frames.append(state(battle))
        if battle.tick>=round(data['duration']*10):break
        queue_scheduled(battle,schedule);movement_tick(battle)
    return dict(name=data['name'],snapshots=frames)


def compare(expected,actual,tolerance=1e-5):
    maximum=0.
    def visit(a,b,path):
        nonlocal maximum
        if isinstance(a,dict):
            for key,value in a.items():visit(value,b[key],path+'.'+key)
        elif isinstance(a,list):
            if len(a)!=len(b):raise AssertionError(path+' length')
            for i,(x,y) in enumerate(zip(a,b)):visit(x,y,path+f'[{i}]')
        elif isinstance(a,(float,int)) and not isinstance(a,bool):
            error=abs(a-b);maximum=max(maximum,error)
            if not math.isfinite(b) or error>tolerance:raise AssertionError(f'{path}: {a} vs {b} (error {error})')
        elif a!=b:raise AssertionError(f'{path}: {a!r} vs {b!r}')
    visit(expected,actual,expected['name']);return maximum


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate',action='store_true');parser.add_argument('--compare',type=Path)
    parser.add_argument('--benchmark',action='store_true');parser.add_argument('--counts',type=int,nargs='+',default=[12,24,36,60]);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.generate:
        FIXTURES.mkdir(parents=True,exist_ok=True);(FIXTURES/'references').mkdir(exist_ok=True)
        for data in definitions():
            (FIXTURES/(data['name']+'.json')).write_text(json.dumps(data,indent=2)+'\n')
            (FIXTURES/'references'/(data['name']+'.json')).write_text(json.dumps(run(data),indent=2)+'\n')
        for count in [12,24,36,60]: (FIXTURES/f'benchmark-{count}.json').write_text(json.dumps(benchmark_definition(count),indent=2)+'\n')
        print(f'Generated 11 reference cases and 4 benchmark inputs: {FIXTURES}')
    if args.compare:
        actual=json.loads(args.compare.read_text());ref=json.loads((FIXTURES/'references'/(actual['name']+'.json')).read_text())
        print(f'Maximum error: {compare(ref,actual):.12g}')
    if args.benchmark:
        results=[]
        for count in args.counts:
            data=benchmark_definition(count);battle,schedule=create(data);timings=[]
            wall=perf_counter_ns()
            for i in range(700):
                start=perf_counter_ns();queue_scheduled(battle,schedule);movement_tick(battle)
                if i>=100:timings.append((perf_counter_ns()-start)/1e6)
            total=(perf_counter_ns()-wall)/1e9;timings.sort()
            results.append(dict(units=count,language='python',seed=17,warmupTicks=100,measuredTicks=600,simulatedSeconds=60,
                                meanMs=mean(timings),medianMs=timings[300],p95Ms=timings[570],ticksPerSecond=1000/mean(timings),measuredWallSeconds=sum(timings)/1000,totalWallSeconds=total))
        text=json.dumps(results,indent=2);print(text)
        if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text+'\n')

if __name__=='__main__':main()
