"""M3 oracle: actual Python Battle.step(), no commanders/army AI/projectiles.

The existing Python game is untouched. Only this harness substitutes the same
specified SplitMix64 stream used by C#, or a controlled finite tape for probes.
"""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
from .combat_reference import ROOT,SCENARIOS,SplitMix64,Tape,case,unit,enemy,ground,hill,forest
from .movement_reference import create,command
from simulation import combat,morale,cavalry,routing
from simulation.geometry import Vec
from simulation.orders import Order,OrderKind,Command
from simulation.regiment import MoraleState as S,CavalryState as C

FIXTURES=ROOT/'migration_tools/dynamics_fixtures'


def dynamics(name,units,terrain=None,duration=60,commands=()):
    data=case(name,units,terrain,duration,commands);data.update(moraleEnabled=True,cavalryEnabled=True,width=1400,height=800)
    return data


def horse(uid,x,y):return unit(uid,x,y,archetype='cavalry')
def charge(uid,target):return dict(tick=0,regimentId=uid,order=dict(kind='charge',targetId=target))
def reserves(first=2):return [unit(first,120,650),enemy(first+1,1250,650)]


def live_scenarios():
    yield 'infantry-under-fire',dynamics('Infantry Under Fire',[unit(0,430,220),unit(1,430,410),enemy(2,570,220),enemy(3,570,410)],duration=600)
    troops=[unit(0,500,200),unit(1,500,250),unit(2,500,300),unit(3,220,650),enemy(4,700,200),enemy(5,700,390)]
    for u,value in zip(troops[:3],[10,31,36.5]):u.update(morale=value,cohesion=55)
    yield 'cascading-rout',dynamics('Cascading Rout',troops,duration=120)
    yield 'prepared-charge',dynamics('Cavalry Against Prepared Infantry',[horse(0,400,300),enemy(1,490,300),*reserves()],commands=[charge(0,1)])
    yield 'flank-charge',dynamics('Cavalry Flank Charge',[horse(0,400,300),enemy(1,490,300,facing=math.pi/2),*reserves()],commands=[charge(0,1)])
    weak=enemy(1,490,300);weak.update(state='wavering',morale=28,cohesion=30,strength=180)
    yield 'wavering-charge',dynamics('Charge Against Wavering Infantry',[horse(0,400,300),weak,*reserves()],commands=[charge(0,1)])
    routed=enemy(1,470,300,facing=0);routed.update(state='routing',morale=10,cohesion=30,strength=180)
    yield 'routing-pursuit',dynamics('Pursuit of Routing Infantry',[horse(0,400,300),routed,*reserves()],commands=[charge(0,1)])
    routed=enemy(2,470,300,facing=0);routed.update(state='routing',morale=10,cohesion=30,strength=200)
    yield 'shared-pursuit',dynamics('Multiple Cavalry Pursuit',[horse(0,400,295),horse(1,400,305),routed,*reserves(3)],commands=[charge(0,2),charge(1,2)])
    recovering=unit(0,550,300,facing=math.pi);recovering.update(state='routing',morale=8,cohesion=65)
    yield 'safe-rally',dynamics('Rallying Away From Danger',[recovering,unit(1,200,650),enemy(2,1250,650)],duration=70)
    yield 'difficult-charge',dynamics('Difficult Terrain Charge',[horse(0,400,300),enemy(1,490,300),*reserves()],
          ground([hill(520,300,90,110,22,True)],[forest(450,300,140,110,.85)]),commands=[charge(0,1)])


def make(data):
    b,schedule=create(data);b.sandbox=False
    for u,d in zip(b.units,sorted(data['units'],key=lambda x:x['id'])):
        u.strength=d.get('strength',u.strength);u.morale=d.get('morale',u.morale);u.state=S(d.get('state','steady'));u.safe_time=d.get('safeTime',0)
    b.initial_strength={army:sum(u.strength for u in b.units if u.army==army) for army in sorted({u.army for u in b.units})}
    b.initial_unit_strength={u.id:u.strength for u in b.units}
    b.rng=Tape(data['randomDraws']) if data.get('randomDraws') is not None else SplitMix64(data['seed'])
    return b,schedule


def queue(b,schedule):
    for c in schedule.get(b.tick,[]):
        raw=c.get('order');order=None
        if raw:order=Order(OrderKind(raw['kind']),Vec(**raw['destination']) if raw.get('destination') else None,raw.get('targetId'),raw.get('facing'))
        from simulation.formations import Formation
        b.issue(Command(c['regimentId'],order,Formation(c['formation']) if c.get('formation') else None))


def describe(u):
    return dict(id=u.id,position=asdict(u.pos),facing=u.facing,strength=u.strength,morale=u.morale,cohesion=u.cohesion,fatigue=u.fatigue,
                # Inactive motion is explicitly cleared in the native snapshot;
                # Python retains its last speed. This is not gameplay movement.
                speed=u.speed if u.active else 0,state=u.state.value,withdrawn=u.withdrawn,effective=u.effective,safeTime=u.safe_time,
                reloadLeft=u.reload_left,chargeState=u.cavalry_state.value,momentum=u.charge_momentum,lastMomentum=u.charge_last_momentum,
                chargeDistance=u.charge_distance,chargeReady=u.charge_ready,cooldown=u.charge_cooldown,
                chargeSequence=u.charge_sequence,impactedSequence=u.charge_impacted_sequence,
                impactTarget=u.charge_impact_target_id,chargeResult=u.charge_result)


def trace(data):
    b,schedule=make(data);samples=set(data['sampleTicks']);frames=[]
    while True:
        if b.tick in samples or b.result is not None:frames.append(dict(tick=b.tick,units=[describe(u) for u in b.units]))
        if b.tick>=round(data['duration']*10) or b.result is not None:break
        queue(b,schedule);b.step()
    return dict(name=data['name'],frames=frames,draws=b.rng.draws,result=b.result,
                routs=b.metrics['routs'],rallies=b.metrics['rallies'],cascadeShocks=b.metrics['cascade_shocks'],
                chargeStarts=sum(u.analysis['charge_initiations'] for u in b.units),impacts=sum(u.analysis['charges'] for u in b.units),
                pursuitCasualties=sum(u.analysis['pursuit_casualties'] for u in b.units),pursuitLosses=sum(u.analysis['pursuit_losses'] for u in b.units))


def calculations():
    def data(name,units,action,**control):
        d=dynamics(name,units);d['randomDraws']=[.37]*1000
        return dict(input=d,action=action,control=control)
    for losses,shock in [(0,4),(12,0),(24,4),(120,18)]:
        yield data(f'damage-{losses}-{shock}',[unit(0,500,300),enemy(1,600,300)],'damage',losses=losses,shock=shock)
    for value,state in [(23,'steady'),(39,'steady'),(59,'steady'),(62,'shaken'),(67,'shaken'),(45,'wavering'),(47,'wavering')]:
        u=unit(0,500,300);u.update(morale=value,state=state)
        yield data(f'state-{state}-{value}',[u],'morale')
    for state,m,c,safe in [('routing',8,65,21.95),('rallying',35,30,0),('rallying',48,45,0)]:
        u=unit(0,500,300);u.update(state=state,morale=m,cohesion=c,safeTime=safe)
        yield data('recovery-'+state+str(m),[u],'morale')
    for name,ex,ey in [('left',430,300),('right',570,300),('above',500,230),('below',500,370)]:
        u=unit(0,500,300);u.update(morale=10,state='routing')
        yield data('escape-'+name,[u,enemy(1,ex,ey)],'routing')
    for name,facing,state,coh,momentum in [('front',math.pi,'steady',100,.9),('flank',math.pi/2,'steady',100,.9),
          ('rear',0,'steady',100,.9),('wavering',math.pi,'wavering',30,.9),('routing',math.pi,'routing',20,.9),
          ('short',math.pi,'steady',100,.08)]:
        target=enemy(1,515,300,facing=facing);target.update(state=state,cohesion=coh,morale=20 if state=='routing' else 35 if state=='wavering' else 85)
        yield data('impact-'+name,[horse(0,500,300),target],'impact',momentum=momentum)
    for state in ['steady','shaken','wavering','routing','rallying']:
        u=unit(0,500,300);u.update(state=state,cohesion=20,morale=30,strength=3)
        yield data('melee-'+state,[u,enemy(1,512,300)],'melee')
        shooter=unit(0,500,300);shooter.update(state=state,morale=30,cohesion=65)
        yield data('fire-'+state,[shooter,enemy(1,600,300)],'fire')
    for coh,speed,distance in [(100,2,12),(100,12,12),(30,12,12),(100,12,2)]:
        u=horse(0,500,300);u['cohesion']=coh
        yield data(f'momentum-{coh}-{speed}-{distance}',[u,enemy(1,590,300)],'momentum',speed=speed,distance=distance)


def calculation(row):
    b,_=make(row['input']);u=b.units[0];target=b.units[1] if len(b.units)>1 else None;control=row['control'];action=row['action'];extra={}
    if action=='damage':combat.damage(b,target,control['losses'],'probe',u,control['shock'])
    elif action=='morale':morale.update(b)
    elif action=='routing':
        goal=routing.destination(b,u);extra['goal']=asdict(goal) if goal else None
    elif action=='impact':
        u.cavalry_state=C.CHARGING;u.charge_sequence=1;u.charge_momentum=control['momentum'];u.velocity=Vec(12,0)
        extra['readiness']=cavalry.readiness(u,target);cavalry.impact(b,u,target)
    elif action=='melee':combat.melee(b,u,target)
    elif action=='fire':combat.fire(b,u,target)
    elif action=='momentum':
        u.cavalry_state=C.CHARGING;u.charge_distance=control['distance'];u.velocity=Vec(control['speed'],0)
        cavalry.after_move(b,u,u.pos)
    return dict(units=[describe(x) for x in b.units],draws=b.rng.draws,extra=extra)


def benchmark(count):
    # Four-regiment modules: simultaneous charge/pursuit, low-morale firefights,
    # and steady reserves keeping the grace timer from ending measurement early.
    units=[];commands=[];modules=count//4
    for m in range(modules):
        column=m%3;row=m//3;x=250+column*600;y=120+row*190;base=m*4
        if m%2==0:
            troops=[horse(base,x,y),enemy(base+1,x+70,y,facing=0),unit(base+2,x-100,y+100),enemy(base+3,x+330,y+100)]
            troops[1].update(state='routing',morale=10,cohesion=30,strength=180)
            commands.append(charge(base,base+1))
        else:
            troops=[unit(base,x,y),enemy(base+1,x+130,y),unit(base+2,x-100,y+100),enemy(base+3,x+330,y+100)]
            for t in troops[:2]:t.update(morale=26,cohesion=65)
            commands.extend([command(5,base,x+40,y),command(300,base,kind='hold')])
        units.extend(troops)
    data=dynamics(f'Dynamics Benchmark {count}',units,ground([hill(900,500,110,120,12,True)],[forest(950,600,90,80,.4)]),duration=70,commands=commands)
    data.update(width=2100,height=max(800,math.ceil(modules/3)*190+130),sampleTicks=[0,100,700]);return data


def generate():
    FIXTURES.mkdir(parents=True,exist_ok=True);probes=[];traces=[]
    for row in calculations():row['expected']=calculation(row);probes.append(row)
    (FIXTURES/'calculations.json').write_text(json.dumps(probes,indent=2)+'\n')
    for id,data in live_scenarios():
        (SCENARIOS/(id+'.json')).write_text(json.dumps(data,indent=2)+'\n')
        duration=600 if id=='infantry-under-fire' else min(data['duration'],70)
        scoped={**data,'name':id,'duration':duration,'sampleTicks':sorted({0,1,2,10,50,100,150,200,300,500,600,int(duration*10)})}
        traces.append(dict(input=scoped,expected=trace(scoped)))
    fleeing=enemy(1,1200,300,facing=0);fleeing.update(state='routing',morale=10)
    victory=dynamics('morale-victory',[unit(0,200,300),fleeing],duration=30)
    victory['sampleTicks']=[0,1,10,100,120]
    traces.append(dict(input=victory,expected=trace(victory)))
    (FIXTURES/'traces.json').write_text(json.dumps(traces,indent=2)+'\n')
    for count in [12,24,36,60]:(SCENARIOS/f'benchmark-dynamics-{count}.json').write_text(json.dumps(benchmark(count),indent=2)+'\n')
    print(f'Generated {len(probes)} calculations, {len(traces)} actual Python traces and four dynamics benchmarks')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generate',action='store_true');args=parser.parse_args()
    if args.generate:generate()

if __name__=='__main__':main()
