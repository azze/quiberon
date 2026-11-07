"""M5 Python decision/commander oracles and shared live/headless scenarios."""
import json,math
from pathlib import Path
from dataclasses import asdict
from .artillery_reference import scenario,battery,ROOT,SCENARIOS,unit,enemy,ground,hill,forest,benchmark
from .dynamics_reference import make
from simulation import commanders as c,commander_ai,ai
from simulation.archetypes import ARCHETYPES
from simulation.geometry import Vec
from simulation.orders import Order,OrderKind
FIXTURES=ROOT/'migration_tools/ai_fixtures'
def officer(id=0,personality='methodical',specialization='drillmaster'):
 return dict(id=f'officer-{id}',name=f'Test Officer {id}',rank='Major',background='Generic',personality=personality,specialization=specialization)
def auto(name,units,terrain=None,armies=(0,1),duration=900):
 d=scenario(name,units,terrain,duration=duration);d.update(aiEnabled=True,commandersEnabled=True,commanderSeed=1729,aiArmies=list(armies),aiStrategies={str(a):'balanced' for a in armies});return d

def scenarios():
 yield 'ai-infantry',auto('AI Infantry Engagement',[unit(0,350,250),unit(1,350,400),enemy(2,680,250),enemy(3,680,400)])
 yield 'ai-cavalry-reserve',auto('AI Cavalry Reserve',[unit(0,380,270),unit(1,260,400,archetype='cavalry'),enemy(2,650,270),enemy(3,650,420)])
 yield 'ai-exposed-flank',auto('AI Exposed Flank',[unit(0,400,300,archetype='commonwealth_uhlans'),enemy(1,510,300,facing=math.pi/2),unit(2,250,650),enemy(3,1100,650)])
 yield 'ai-forest',auto('AI Woodland Harassment',[unit(0,390,300,archetype='haudenosaunee_skirmishers'),enemy(1,560,300),unit(2,320,470),enemy(3,600,470)],ground([],[forest(420,300,150,100,.7)]))
 yield 'ai-rifles',auto('AI Rifle Range',[unit(0,390,300,archetype='revolutionary_rifles'),enemy(1,640,300)])
 yield 'ai-artillery',auto('AI Artillery Positioning',[battery(0,300,300),unit(1,400,470),enemy(2,610,300),enemy(3,610,470)],ground([hill(450,300,25,14,18,True)],[]))
 yield 'ai-horse-artillery',auto('AI Horse Battery',[battery(0,220,230),battery(1,220,500,True),enemy(2,800,230),enemy(3,800,500)])
 u=[unit(0,370,250,archetype='cavalry'),unit(1,370,490,archetype='cavalry'),enemy(2,640,250),enemy(3,640,490)]
 u[0]['commander']=officer(0,'aggressive','firebrand');u[1]['commander']=officer(1,'cautious','firebrand')
 yield 'ai-personalities',auto('AI Cavalry Personalities',u)
 u=[unit(0,400,240,archetype='prussian_line'),unit(1,400,490),enemy(2,620,240),enemy(3,620,490)]
 u[0]['commander']=officer(0,'methodical','drillmaster');u[1]['commander']=officer(1,'stalwart','defensive_tactician')
 yield 'ai-specializations',auto('AI Commander Specializations',u)
 for suffix,armies in [('combined',(0,1)),('player',(1,))]:
  d=benchmark(12,False);d.update(name='AI Combined Arms' if len(armies)==2 else 'Player versus AI',aiEnabled=True,commandersEnabled=True,commanderSeed=1729,aiArmies=list(armies),commands=[],duration=1200,aiStrategies={str(a):'balanced' for a in armies})
  yield 'ai-'+suffix,d

def probes():
 rows=[]
 for kind,archetype in [(c.U.INFANTRY,'infantry'),(c.U.CAVALRY,'cavalry'),(c.U.ARTILLERY,'artillery')]:
  for personality in c.P:
   for spec in c.compatible(kind):
    d=auto(personality.value+'-'+spec.value,[unit(0,400,300,archetype=archetype),enemy(1,470,300)])
    d['units'][0]['commander']=officer(0,personality.value,spec.value)
    b,_=make(d);u=b.units[0];u.commander=c.Commander.from_dict({k:v for k,v in d['units'][0]['commander'].items()});u.cohesion=85
    rows.append(dict(input=d,expected=dict(formation=c.formation_factor(u),manoeuvre=c.manoeuvre_factor(u),recovery=c.recovery_factor(u),shock=c.shock_factor(u),advance=c.advance_factor(u),reload=c.reload_factor(u),accuracy=c.accuracy_factor(u,1),defence=c.defence_factor(u,b.units[1]),policy=asdict(c.policy(u)),scatter=c.scatter_factor(u),redeploy=c.redeploy_factor(u),pursuit=c.pursuit_factor(u),gap=c.pursuit_gap(u,6),frontal=c.frontal_pursuit_penalty(u,b.units[1]),chargeShock=c.charge_shock_factor(u,b.units[1],.7,False))))
 for personality in c.P:
  for cohesion in [40,85]:
   d=auto('prepare-'+personality.value+str(cohesion),[unit(0,400,300),enemy(1,460,300)]);d['units'][0]['commander']=officer(0,personality.value)
   b,_=make(d);b.ai_armies={0};u=b.units[0];u.commander=c.Commander.from_dict(officer(0,personality.value));u.cohesion=cohesion
   result=commander_ai.plan(b,u,[b.units[1]],b.units[1])
   rows.append(dict(input=d,cohesion=cohesion,action='prepare',expected=dict(result=result,kind=u.order.kind.value,retreatUntil=u.commander_retreat_until,reformUntil=u.commander_reform_until)))
 rows.extend(decision_probes())
 return rows

def decision_probes():
 rows=[]
 for personality in c.P:
  for distance in [120,140,200]:
   d=auto('range-'+personality.value+str(distance),[unit(0,400,300),enemy(1,400+distance,300)]);d['units'][0]['commander']=officer(0,personality.value)
   b,_=make(d);b.ai_armies={0};u=b.units[0];u.commander=c.Commander.from_dict(officer(0,personality.value));u.order=Order(OrderKind.ADVANCE,b.units[1].pos)
   point=ai.destination(b,u);rows.append(dict(input=d,action='intent',expected=dict(destination=asdict(point) if point else None,facing=u.facing)))
 for archetype in ['haudenosaunee_skirmishers','revolutionary_rifles']:
  for distance in [40,100,180,250]:
   d=auto(archetype+str(distance),[unit(0,400,300,archetype=archetype),enemy(1,400+distance,300)]);d['commandersEnabled']=False
   b,_=make(d);b.ai_armies={0};u=b.units[0];u.order=Order(OrderKind.SKIRMISH,b.units[1].pos);point=ai.skirmish_destination(b,u,b.units[1])
   rows.append(dict(input=d,action='skirmish',expected=dict(destination=asdict(point) if point else None,retreat=u.skirmish_retreat,until=u.skirmish_until)))
 for archetype,spec in [('infantry','drillmaster'),('cavalry','firebrand')]:
  for lock in [0,20]:
   d=auto('opportunity-'+archetype+str(lock),[unit(0,400,300,archetype=archetype),enemy(1,490,300),dict(enemy(2,550,300),state='wavering',morale=28,cohesion=25)])
   d['units'][0]['commander']=officer(0,'opportunistic',spec)
   b,_=make(d);b.ai_armies={0};u=b.units[0];u.commander=c.Commander.from_dict(officer(0,'opportunistic',spec));u.commander_target_id=1;u.commander_decision_until=lock
   chosen=commander_ai.select_target(b,u,b.units[1:],b.units[1]);rows.append(dict(input=d,action='opportunity',lock=lock,expected=dict(target=chosen.id,until=u.commander_decision_until)))
 for strategy in ai.STRATEGIES:
  d=auto('army-'+strategy,[unit(0,350,300),enemy(1,700,300)]);d['commandersEnabled']=False
  b,_=make(d);b.ai_armies={0};b.ai_strategies={0:strategy,1:'balanced'};ai.army_plan(b);u=b.units[0]
  rows.append(dict(input=d,action='army',strategy=strategy,expected=dict(kind=u.order.kind.value,destination=asdict(u.order.destination) if u.order.destination else None)))
 return rows

def generate():
 FIXTURES.mkdir(exist_ok=True)
 for id,d in scenarios():
  for u in d['units']:u['name']=('Blue' if u['army']==0 else 'Red')+' '+ARCHETYPES[u['archetype']].name+' '+str(u['id']+1)
  (SCENARIOS/(id+'.json')).write_text(json.dumps(d,indent=2)+'\n')
 for count in [12,24,36,60]:
  d=benchmark(count,False);d.update(name=f'Autonomous Combined Arms {count}',aiEnabled=True,commandersEnabled=True,commanderSeed=1729,aiArmies=[0,1],commands=[],duration=70)
  for u in d['units']:u['name']=('Blue' if u['army']==0 else 'Red')+' '+ARCHETYPES[u['archetype']].name+' '+str(u['id']+1)
  (SCENARIOS/f'benchmark-ai-{count}.json').write_text(json.dumps(d,indent=2)+'\n')
 (FIXTURES/'probes.json').write_text(json.dumps(probes(),indent=2)+'\n')
if __name__=='__main__':generate()
