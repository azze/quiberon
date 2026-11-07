"""M4 reference fixtures: unchanged Python ballistics and specialist formulas.
No commander/AI/campaign effects. Shared SplitMix64 test stream, not game MT19937.
"""
import json,math,argparse
from pathlib import Path
from dataclasses import asdict
from .dynamics_reference import make,queue,dynamics,reserves
from .combat_reference import unit,enemy,ground,hill,forest
from .movement_reference import command
from simulation import projectiles,combat,archetypes,morale,movement
from simulation.geometry import Vec
ROOT=Path(__file__).resolve().parents[1]
SCENARIOS=ROOT/'simulation_data/combat_scenarios'
FIXTURES=ROOT/'migration_tools/artillery_fixtures'
def target_order(uid,target):return dict(tick=0,regimentId=uid,order=dict(kind='attack',targetId=target))
def battery(i,x,y,horse=False):return unit(i,x,y,archetype='french_horse_artillery' if horse else 'artillery')
def scenario(name,units,terrain=None,commands=(),duration=70):
 for u in units:u['name']=('Blue' if u['army']==0 else 'Red')+' '+archetypes.ARCHETYPES[u['archetype']].name+' '+str(u['id']+1)
 d=dynamics(name,units,terrain,duration,commands);d.update(artilleryEnabled=True,specialistsEnabled=True,sampleTicks=[0,1,10,50,100,200,400,700]);return d

def scenarios():
 for key,name,terrain,extra in [('open-shot','Cannonball Across Open Ground',None,[]),('ricochet','Round Shot and Ricochet',None,[]),('artillery-hills','Artillery and Hills',ground([hill(510,300,35,110,28,True)],[]),[]),('friendly-fire','Artillery Friendly Fire',None,[unit(2,540,300)])]:
  yield key,scenario(name,[battery(0,300,300),enemy(1,620,300),*extra,*reserves(3)],terrain,[target_order(0,1)])
 yield 'enfilade',scenario('Formation Geometry and Enfilade',[battery(0,300,220),battery(1,300,450),enemy(2,620,220),enemy(3,620,450,facing=math.pi/2),*reserves(4)],commands=[target_order(0,2),target_order(1,3)])
 yield 'battery-under-attack',scenario('Battery Under Cavalry Attack',[battery(0,500,300),dict(enemy(1,590,300),archetype='commonwealth_uhlans'),*reserves(2)],commands=[target_order(1,0)])
 yield 'prussian-drill',scenario('Prussian Drill Comparison',[unit(0,400,220,archetype='prussian_line'),unit(1,400,440),enemy(2,540,220),enemy(3,540,440)])
 yield 'woodland-specialists',scenario('Woodland Skirmishing',[unit(0,420,250,archetype='haudenosaunee_skirmishers'),unit(1,420,500),enemy(2,500,250),enemy(3,500,500)],ground([],[forest(440,250,110,85,.8),forest(440,500,110,85,.8)]))
 weak=unit(0,430,300);weak.update(morale=42)
 yield 'grenadier-support',scenario('Grenadier Morale Support',[weak,unit(1,390,360,archetype='royal_grenadiers'),enemy(2,560,300),*reserves(3)])
 weak=enemy(1,490,280);weak.update(morale=28,cohesion=30,state='wavering')
 yield 'uhlan-charge',scenario('Uhlan Charge and Pursuit',[unit(0,400,280,archetype='commonwealth_uhlans'),weak,*reserves()],commands=[target_order(0,1)])
 yield 'rifle-engagement',scenario('Rifles at Extended Range',[unit(0,400,300,archetype='revolutionary_rifles'),enemy(1,610,300),*reserves()])
 yield 'horse-redeployment',scenario('Horse and Field Battery Redeployment',[battery(0,300,230),battery(1,300,450,True),enemy(2,800,230),enemy(3,800,450)],commands=[command(0,0,430,230),command(0,1,430,450),dict(tick=780,regimentId=0,order=dict(kind='attack',targetId=2)),dict(tick=780,regimentId=1,order=dict(kind='attack',targetId=3))],duration=110)
 yield 'combined-arms',benchmark(12,False)

def benchmark(count,heavy):
 ids=['artillery','french_horse_artillery','artillery','prussian_line','royal_grenadiers','commonwealth_uhlans'] if heavy else ['prussian_line','haudenosaunee_skirmishers','royal_grenadiers','commonwealth_uhlans','revolutionary_rifles','french_horse_artillery']
 troops=[];commands=[];half=count//2
 for army in range(2):
  for i in range(half):
   a=ids[i%len(ids)];x=390 if army==0 else 610;y=110+i*110
   if a in ['artillery','french_horse_artillery']:x=280 if army==0 else 720
   u=unit(army*half+i,x,y,archetype=a,facing=0 if army==0 else math.pi);u['army']=army;troops.append(u)
   if a=='commonwealth_uhlans':commands.append(target_order(u['id'],(1-army)*half+i))
 d=scenario(f'{"Artillery Heavy" if heavy else "Combined Arms"} {count}',troops,ground([hill(530,120,50,65,8,True)],[forest(460,220,70,75,.6)]),commands)
 d['height']=max(800,half*110+120);return d

def projectile_data(p):return dict(position=asdict(p.pos),velocity=asdict(p.velocity),height=p.height,verticalSpeed=p.vertical_speed,energy=p.energy,age=p.age,bounces=p.bounces,hitIds=sorted(p.hit_ids))
def physics_case(name,terrain=None,init=None,steps=30):
 d=scenario(name,[battery(0,300,300),enemy(1,550,300),unit(2,430,300)],terrain);b,_=make(d)
 p=projectiles.Projectile(Vec(320,300),Vec(100,0),1.2,2,0)
 if init:
  for k,v in init.items():setattr(p,k,v)
 b.projectiles=[p];frames=[]
 for tick in range(steps):
  projectiles.update(b)
  frames.append(dict(tick=tick+1,projectile=projectile_data(p),active=p in b.projectiles,strengths=[u.strength for u in b.units],morale=[u.morale for u in b.units],cohesion=[u.cohesion for u in b.units],draws=b.rng.draws))
 return dict(name=name,input=d,initial=dict(position=asdict(Vec(320,300)),velocity=asdict(Vec(100,0)),height=init.get('height',1.2) if init else 1.2,verticalSpeed=init.get('vertical_speed',2) if init else 2,energy=1),frames=frames)
def probes():
 rows=[]
 for aid in archetypes.ARCHETYPES:
  d=scenario(aid,[unit(0,400,300,archetype=aid),enemy(1,480,300)],ground([],[forest(430,300,130,100,.6)]));b,_=make(d);u,t=b.units
  u.cohesion=85;u.speed=0;u.forest_cover=b.terrain.movement_effect(u,Vec(0,0)).forest
  sight=b.visibility(u,t);form,power,shock=combat.forest_melee_factors(b,u);out,protection,_=combat.forest_fire_factors(b,u,t,sight)
  rows.append(dict(id=aid,reload=archetypes.reload_time(u),formation=archetypes.formation_time(u,7),manoeuvre=archetypes.manoeuvre_factor(u),aimed=archetypes.aimed_bonus(u,sight.transmission),visibility=asdict(sight),forestPower=power,forestShock=shock,outgoing=out,protection=protection,movement=asdict(b.terrain.movement_effect(u,Vec(1,0))),guns=u.available_guns))
 return rows

def trace(data):
 b,schedule=make(data);frames=[];samples=set(data['sampleTicks']);limit=round(data['duration']*10)
 while True:
  if b.tick in samples or b.tick==limit or b.result is not None:
   frames.append(dict(tick=b.tick,units=[dict(id=u.id,position=asdict(u.pos),facing=u.facing,strength=u.strength,morale=u.morale,cohesion=u.cohesion,reloadLeft=u.reload_left) for u in b.units],projectiles=[dict(position=asdict(p.pos),velocity=asdict(p.velocity),height=p.height,verticalSpeed=p.vertical_speed,energy=p.energy,bounces=p.bounces) for p in b.projectiles]))
  if b.tick>=limit or b.result is not None:break
  queue(b,schedule);b.step()
 return dict(input=data,frames=frames,draws=b.rng.draws)

def generate():
 FIXTURES.mkdir(exist_ok=True)
 for id,d in scenarios():(SCENARIOS/(id+'.json')).write_text(json.dumps(d,indent=2)+'\n')
 for count in [12,24,36,60]:
  for heavy in [False,True]:
   id=f'benchmark-{"artillery" if heavy else "combined"}-{count}';(SCENARIOS/(id+'.json')).write_text(json.dumps(benchmark(count,heavy),indent=2)+'\n')
 cases=[physics_case('flat'),physics_case('hill',ground([hill(445,300,12,60,20,True)],[])),physics_case('forest',ground([],[forest(470,300,100,70,.7)])),physics_case('overflight',init=dict(height=30,vertical_speed=0)),physics_case('ricochet',init=dict(height=.5,vertical_speed=-5),steps=60)]
 for id in ['open-shot','prussian-drill','rifle-engagement','woodland-specialists','grenadier-support']:
  d=dict(scenarios())[id];d.update(duration=20,sampleTicks=[0,1,10,50,100,200]);(FIXTURES/(id+'-trace.json')).write_text(json.dumps(trace(d),indent=2)+'\n')
 import random
 rng=random.Random(127)
 norms=[]
 for _ in range(1000):
  v=Vec(rng.uniform(-1000,1000),rng.uniform(-1000,1000)).normalized()*100
  norms.append(dict(x=v.x,y=v.y,length=v.length(),pieces=max(1,math.ceil(v.length()*.1/2))))
 (FIXTURES/'norms.json').write_text(json.dumps(norms,indent=2)+'\n')
 (FIXTURES/'physics.json').write_text(json.dumps(cases,indent=2)+'\n');(FIXTURES/'specialists.json').write_text(json.dumps(probes(),indent=2)+'\n')
def generate_stress():
 rows=[]
 for kind in ['artillery','combined']:
  for count in [12,24,36,60]:
   data=benchmark(count,kind=='artillery');b,schedule=make(data)
   for _ in range(700):queue(b,schedule);b.step()
   rows.append(dict(name=f'{kind}-{count}',input=data,expected=dict(finalStates=[dict(id=u.id,position=asdict(u.pos),strength=u.strength,morale=u.morale,cohesion=u.cohesion,state=u.state.value,withdrawn=u.withdrawn) for u in b.units],draws=b.rng.draws)))
 (FIXTURES/'stress.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stress',action='store_true',help='Also regenerate eight 700-tick stress references (slower)');args=parser.parse_args();generate()
 if args.stress:generate_stress()

