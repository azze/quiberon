"""Ordinary-infantry Python oracle: current rules, frozen morale, controlled RNG.

This module changes no game code. It calls authoritative terrain/combat/movement
functions, excluding routing, charges, artillery and army-level tactical AI.
"""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
from .movement_reference import ROOT,point,unit,command,create,queue_scheduled
from simulation import ai,combat,movement,positioning,morale
from simulation.geometry import Vec,angle_delta,touching
from simulation.spatial import candidate_pairs,SpatialIndex
from simulation.orders import OrderKind
from simulation.formations import Formation

FIXTURES=ROOT/'migration_tools/combat_fixtures'
SCENARIOS=ROOT/'simulation_data/combat_scenarios'
MASK=(1<<64)-1

class SplitMix64:
    def __init__(self,seed):self.state=seed&MASK;self.draws=0
    def random(self):
        self.state=(self.state+0x9E3779B97F4A7C15)&MASK;z=self.state
        z=((z^(z>>30))*0xBF58476D1CE4E5B9)&MASK
        z=((z^(z>>27))*0x94D049BB133111EB)&MASK
        z=z^(z>>31);self.draws+=1
        return (z>>11)/9007199254740992
    def uniform(self,a,b):return a+(b-a)*self.random()

class Tape:
    def __init__(self,values):self.values=values;self.draws=0
    def random(self):
        result=self.values[self.draws];self.draws+=1;return result
    def uniform(self,a,b):return a+(b-a)*self.random()

def enemy(uid,x,y,**kw):
    u=unit(uid,x,y,**kw);u['army']=1
    if 'facing' not in kw:u['facing']=math.pi
    return u

def case(name,units,terrain=None,duration=30,commands=()):
    units=[dict(u,name=f'{"Red" if u["army"] else "Blue"} '+{'infantry':'Line','cavalry':'Cavalry','artillery':'Battery'}.get(u['archetype'],'Infantry')+f' {u["id"]+1}') for u in units]
    return dict(version=1,name=name,seed=17,combatEnabled=True,width=1000,height=650,duration=duration,
                sampleTicks=sorted({0,1,2,10,20,21,50,100,int(duration*10)}),units=units,commands=list(commands),terrain=terrain)

def hill(x,y,rx,ry,height,compact=False):return dict(x=x,y=y,radiusX=rx,radiusY=ry,height=height,compact=compact)
def forest(x,y,rx,ry,density=1):return dict(x=x,y=y,radiusX=rx,radiusY=ry,density=density)
def ground(hills=(),forests=()):return dict(hills=list(hills),forests=list(forests))

def live_scenarios():
    yield 'infantry-duel',case('Infantry Duel',[unit(0,430,220),unit(1,430,400),enemy(2,570,220),enemy(3,570,400)],duration=900)
    yield 'ridge-defence',case('Ridge Defence',[unit(0,530,220,facing=math.pi),unit(1,530,400,facing=math.pi),enemy(2,310,220,facing=0),enemy(3,310,400,facing=0)],
          ground([hill(570,310,90,170,28,True)]),duration=900,commands=[dict(tick=0,regimentId=2,order=dict(kind='attack',targetId=0)),dict(tick=0,regimentId=3,order=dict(kind='attack',targetId=1))])
    yield 'forest-engagement',case('Forest Engagement',[unit(0,400,220),unit(1,400,400),enemy(2,540,220),enemy(3,540,400)],
          ground(forests=[forest(420,220,80,60,.5),forest(535,400,95,75,.8)]),duration=900,
          commands=[dict(tick=0,regimentId=2,order=dict(kind='attack',targetId=0)),dict(tick=0,regimentId=3,order=dict(kind='attack',targetId=1))])
    yield 'flank-attack',case('Flank Attack',[unit(0,400,300),unit(1,330,170),enemy(2,438,300,facing=math.pi/2)],duration=900)
    yield 'friendly-obstruction',case('Friendly Firing Obstruction',[unit(0,360,300),unit(1,400,300),unit(2,400,405),enemy(3,500,300)],duration=900)
    units=[unit(i,400,110+i*110) for i in range(4)]
    units += [unit(4,260,65,archetype='cavalry'),unit(5,280,590,archetype='artillery')]
    units += [enemy(6+i,650,110+i*110) for i in range(4)]
    units += [enemy(10,810,65,archetype='cavalry'),enemy(11,800,590,archetype='artillery')]
    yield 'combined',case('Combined Movement and Combat',units,ground([hill(550,320,100,130,12,True)],[forest(610,500,80,80,.4)]),duration=900,
                commands=[dict(tick=0,regimentId=6+i,order=dict(kind='attack',targetId=i)) for i in range(4)])

def benchmark(count,terrain=True):
    pairs=count//2;units=[];orders=[]
    for army in [0,1]:
        for i in range(pairs):
            x=220+(i%3)*500+(130 if i%2==0 else 12)*army
            u=unit(i+army*pairs,x,90+(i//3)*90,facing=math.pi if army else 0);u['army']=army;units.append(u)
            if army==0 and i%2==0:
                orders.extend([command(5,i,x+45,u['position']['y']),command(400,i,kind='hold')])
    data=case(f'Combat Benchmark {count}',units,ground([hill(300,230,95,110,12,True),hill(1220,550,90,90,18,True)],
                [forest(280,90,45,42,.5),forest(770,360,60,60,.45),forest(1260,720,75,70,.6)]) if terrain else None,duration=70,commands=orders)
    data.update(width=1600,height=max(850,math.ceil(pairs/3)*90+100),sampleTicks=[0,100,700])
    return data

def calculations():
    base=[unit(0,300,300),enemy(1,430,300)]
    yield 'clear',base,None,False
    yield 'range-limit',[unit(0,300,300),enemy(1,456,300)],None,False
    yield 'rear-arc',[unit(0,300,300,facing=math.pi),enemy(1,430,300)],None,False
    yield 'column',[unit(0,300,300,formation='column'),enemy(1,430,300)],None,False
    yield 'dispersed-target',[unit(0,300,300),enemy(1,430,300,formation='skirmish')],None,False
    yield 'low-cohesion',[unit(0,300,300,cohesion=25),enemy(1,430,300)],None,False
    yield 'moving',base,None,True
    yield 'ridge',base,ground([hill(365,300,20,70,25)]),False
    yield 'elevated',base,ground([hill(300,300,20,60,25),hill(430,300,20,60,25),hill(365,300,15,60,4)]),False
    yield 'forest-deep',base,ground(forests=[forest(370,300,180,100)]),False
    yield 'forest-close',[unit(0,350,300),enemy(1,380,300)],ground(forests=[forest(370,300,180,100)]),False
    yield 'treeline-incoming',base,ground(forests=[forest(430,300,80,65,.5)]),False
    yield 'treeline-outgoing',[unit(0,430,300,facing=math.pi),enemy(1,300,300,facing=0)],ground(forests=[forest(430,300,80,65,.5)]),False
    yield 'dense-screen',base+[unit(2,350,300)],None,False
    yield 'loose-screen',base+[unit(2,350,300,formation='skirmish')],None,False
    yield 'clear-flank',base+[unit(2,350,390)],None,False
    yield 'partial-screen',base+[unit(2,350,345)],None,False
    yield 'stacked-lines',base+[unit(2,300,300),unit(3,300,300)],None,False
    yield 'overlapping-targets',base+[enemy(2,430,300)],None,False
    yield 'elevated-screen',base+[unit(2,365,300)],ground([hill(300,300,14,50,25),hill(430,300,14,50,25)]),False
    for facing,name in [(math.pi,'front'),(math.pi/2,'flank'),(0,'rear')]:yield 'melee-'+name,[unit(0,300,300),enemy(1,312,300,facing=facing)],None,False
    yield 'melee-forest',[unit(0,300,300),enemy(1,312,300)],ground(forests=[forest(300,300,90,90)]),False
    yield 'melee-column',[unit(0,300,300,formation='column'),enemy(1,312,300)],ground(forests=[forest(300,300,90,90)]),False
    yield 'melee-uphill',[unit(0,300,300),enemy(1,312,300)],ground([hill(350,300,65,65,35)]),False

def make(data):
    # Calculation probes may use a loose generic formation to isolate geometry,
    # rather than activating a specialist's unported combat abilities.
    adjusted=json.loads(json.dumps(data))
    overrides={}
    for u in adjusted['units']:
        if u.get('formation')=='skirmish' and u['archetype']=='infantry':overrides[u['id']]='skirmish';u.pop('formation')
    battle,schedule=create(adjusted)
    for u in battle.units:
        if u.id in overrides:u.formation=Formation(overrides[u.id])
        original=next(x for x in data['units'] if x['id']==u.id)
        if 'strength' in original:u.strength=original['strength']
    battle.rng=Tape(data['randomDraws']) if data.get('randomDraws') is not None else SplitMix64(data['seed'])
    # Preserve explicit attack target IDs, omitted by the movement-only harness.
    return battle,schedule

def calculation_reference(data,moving):
    b,_=make(data);a=b.unit(0);target=b.unit(1)
    if moving:movement.move(a,a.pos+Vec(100,0),b.rules.dt,b.rules.width,b.rules.height,b.terrain,b.rules.terrain)
    sight=b.visibility(a,target);factor=combat.friendly_fire_factor(b,a,target)
    distance=(target.pos-a.pos).length();shots=max(1,int(a.strength*.42*combat.PROFILES[a.formation][4]*factor))
    probability=b.rules.musket_accuracy*(1-.65*distance/a.stats.range)*(.3+a.cohesion/140)
    if target.formation==Formation.SKIRMISH:probability*=.65
    if not b.terrain.empty:
        outgoing,protection,_=combat.forest_fire_factors(b,a,target,sight);probability*=outgoing*protection
    if a.speed>.1:probability*=.45
    probability=max(0,min(.95,probability))
    flank_angle=abs(angle_delta(target.facing,combat.angle_to(target.pos,a.pos)))
    flank=1 if flank_angle<math.pi/3 else 1.6 if flank_angle<2.3 else 2.2
    terrain,power,shock=combat.forest_melee_factors(b,a)
    if not b.terrain.empty:
        grade=(b.terrain.get_elevation(target.pos.x,target.pos.y)-b.terrain.get_elevation(a.pos.x,a.pos.y))/max(10,(target.pos-a.pos).length())
        terrain/=1+max(0,grade)*b.rules.terrain.uphill_melee_penalty
    melee_power=a.strength*.013*(.3+a.cohesion/100)*flank*terrain*power
    if a.formation==Formation.SKIRMISH:melee_power*=.65
    result=dict(elevation=b.terrain.get_elevation(a.pos.x,a.pos.y),forest=b.terrain.forest_density(a.pos.x,a.pos.y),slope=b.terrain.slope(a.pos.x,a.pos.y),
                visible=sight.visible,transmission=sight.transmission,vegetation=sight.vegetation,reason=sight.reason,
                canFire=combat.can_fire(b,a,target),laneFactor=factor,shots=shots,probability=probability,
                touching=touching(a,target),meleePower=melee_power,meleeShock=flank*terrain*shock)
    if data['name'].startswith('melee-'):combat.melee(b,a,target)
    else:combat.fire(b,a,target)
    result['after']=[dict(id=u.id,strength=u.strength,cohesion=u.cohesion,reloadLeft=u.reload_left) for u in b.units];result['draws']=b.rng.draws
    return result

def combat_tick(b,schedule):
    from simulation.orders import Order,Command
    for c in schedule.get(b.tick,[]):
        raw=c.get('order');order=Order(OrderKind(raw['kind']),Vec(**raw['destination']) if raw.get('destination') else None,raw.get('targetId'),raw.get('facing')) if raw else None
        b.issue(Command(c['regimentId'],order,Formation(c['formation']) if c.get('formation') else None))
    for c in b.commands:
        u=b.unit(c.regiment_id)
        if not u or not u.active:continue
        if c.order:
            u.order=c.order;u.player_order=True;positioning.reset(u);movement.reset_avoidance(u)
            t=b.unit(u.order.target_id)
            if t and t.active and t.army!=u.army:u.last_seen_target_pos=t.pos
        if c.formation and c.formation!=u.formation and not u.transition_left and c.formation in u.archetype.formations:
            u.next_formation=c.formation;u.transition_left=b.rules.formation_seconds;u.cohesion=max(0,u.cohesion-6)
    b.commands.clear();active=[u for u in b.units if u.active]
    intents={u.id:ai.destination(b,u) for u in active};overlaps=movement.update_congestion(active,b.rules)
    positioning.settle(b,active,intents,overlaps)
    destinations={u.id:movement.avoid_friends(u,intents[u.id],active,b.rules,intents) for u in active}
    for u in active:
        u.combat_state='idle';u.reload_left=max(0,u.reload_left-b.rules.dt)
        dest=movement.terrain_steer(b,u,destinations[u.id]);arrival=u.order.facing if u.order.kind in (OrderKind.MOVE,OrderKind.ADVANCE) and dest in (u.order.destination,u.settling_goal) else None
        if u.settling_facing is not None and dest==u.settling_goal:arrival=u.settling_facing
        movement.move(u,dest,b.rules.dt,b.rules.width,b.rules.height,b.terrain,b.rules.terrain,arrival)
        if u.settling_goal is not None and u.settling_facing is not None and (u.pos-u.settling_goal).length()<1 and abs(angle_delta(u.facing,u.settling_facing))<.001:u.settling_facing=None
    movement.update_congestion(active,b.rules,b.rules.dt)
    for a,c in candidate_pairs(active,padding=1.5):
        if a.active and c.active and a.army!=c.army and touching(a,c):combat.melee(b,a,c)
    b._fire_index=SpatialIndex(active) if len(active)>=12 else None
    try:
        for u in active:
            if not u.active or u.combat_state=='melee':continue
            target=combat.select_fire_target(b,u)
            if target:u.target_id=target.id;combat.fire(b,u,target)
    finally:b._fire_index=None
    for u in active:
        if u.active:morale.recover_cohesion(u,b.rules,b.rules.dt)
        if u.target_id is not None and not b.unit(u.target_id).active:u.target_id=None
    movement.separate([u for u in active if u.active],b.rules.width,b.rules.height)
    b.tick+=1

def trace(data):
    b,schedule=make(data);samples=set(data['sampleTicks']);frames=[]
    for tick in range(round(data['duration']*10)+1):
        if tick in samples:
            frames.append(dict(tick=tick,units=[dict(id=u.id,position=asdict(u.pos),facing=u.facing,strength=u.strength,cohesion=u.cohesion,reloadLeft=u.reload_left,combatState=u.combat_state if u.active else 'destroyed') for u in b.units]))
        if tick<round(data['duration']*10):combat_tick(b,schedule)
    return dict(name=data['name'],frames=frames,draws=b.rng.draws)

def generate():
    FIXTURES.mkdir(parents=True,exist_ok=True);SCENARIOS.mkdir(parents=True,exist_ok=True)
    probes=[]
    for name,units,terrain,moving in calculations():
        data=case(name,units,terrain);data['randomDraws']=[((i*37)%997+.5)/997 for i in range(128)]
        probes.append(dict(input=data,moving=moving,expected=calculation_reference(data,moving)))
    (FIXTURES/'calculations.json').write_text(json.dumps(probes,indent=2)+'\n')
    traces=[]
    for id,data in live_scenarios():
        (SCENARIOS/(id+'.json')).write_text(json.dumps(data,indent=2)+'\n')
        if id!='combined':
            duration=90 if id in ('ridge-defence','forest-engagement') else 30
            scoped={**data,'name':id,'duration':duration,'sampleTicks':sorted({0,1,2,10,20,21,50,100,200,300,duration*10})}
            traces.append(dict(input=scoped,expected=trace(scoped)))
    data=benchmark(12);data['name']='moving-combat';data['sampleTicks']=[0,5,10,100,200,400,700]
    traces.append(dict(input=data,expected=trace(data)))
    (FIXTURES/'traces.json').write_text(json.dumps(traces,indent=2)+'\n')
    rng=SplitMix64(17)
    (FIXTURES/'rng.json').write_text(json.dumps([rng.random() for _ in range(100)],indent=2)+'\n')
    for count in [12,24,36,60]:(SCENARIOS/f'benchmark-{count}.json').write_text(json.dumps(benchmark(count),indent=2)+'\n')
    print(f'Generated {len(probes)} calculation probes, {len(traces)} traces, six live scenarios and four benchmarks')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generate',action='store_true');args=parser.parse_args()
    if args.generate:generate()

if __name__=='__main__':main()
