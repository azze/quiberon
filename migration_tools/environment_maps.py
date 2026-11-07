"""Small JSON authoring helpers and eight environmental laboratories (not campaign missions).

Coordinates are simulation metres, facing is radians, +X is forward. No simulation
or naming RNG is used. Use --custom for a deployment recipe and --write-bundled
when intentionally regenerating the checked-in examples.
"""
import argparse,copy,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def point(x,y):return dict(x=x,y=y)
def river(id='vistula',x=600,width=70):return dict(id=id,name='River laboratory',points=[point(x,-100),point(x,1100)],width=width,waterHeight=-.4,depth=2)
def crossing(id,y,kind='bridge',guns=True):return dict(id=id,riverId='vistula',position=point(600,y),facing=0,length=112,width=26 if kind=='bridge' else 42,kind=kind,fordDepth='shallow' if guns else 'moderate',speed=.85 if kind=='bridge' else .45)
def road(id,y,track=False):return dict(id=id,name='Track' if track else 'Main road',points=[point(100,y),point(600,y),point(1100,y)],width=7 if track else 10,surface='track' if track else 'mainRoad')
def defence(id,x,y,kind='earthwork'):return dict(id=id,position=point(x,y),facing=math.pi,width=90,depth=3,kind=kind,musketExposure=.7,chargeResistance=.65,protectionDepth=36)
def unit(id,type,army,x,y,order=None,formation=None):
 d=dict(id=id,archetype=type,army=army,name=f'{"Blue" if army==0 else "Red"} {type} {id}',position=point(x,y),facing=0 if army==0 else math.pi,autonomy='ordered')
 if order:d['order']=order
 if formation:d['formation']=formation
 return d
def move(x,y,via=None):
 d=dict(kind='move',destination=point(x,y))
 if via:d['viaCrossing']=via
 return d
def environment(rivers=None,crossings=None,roads=None,defences=None,weather='clear'):
 return dict(version=1,rivers=rivers or [],crossings=crossings or [],roads=roads or [],defences=defences or [],weather=dict(type=weather,visibilityLimit=180))
def scenario(name,env,units,hills=None,forests=None):return dict(version=1,name=name,width=1200,height=900,seed=1796,duration=400,sampleTicks=[0,100,1000,4000],combatEnabled=True,moraleEnabled=True,cavalryEnabled=True,artilleryEnabled=True,specialistsEnabled=True,commandersEnabled=True,aiEnabled=True,aiArmies=[],units=units,terrain=dict(hills=hills or [],forests=forests or [],environment=env))
def maps():
 units=[unit(0,'infantry',0,280,300,move(940,300)),unit(1,'cavalry',0,240,500,move(940,500)),unit(2,'artillery',0,240,650,move(940,650)),unit(3,'infantry',1,940,400)]
 result={}
 result['river']=scenario('Environment A — River without crossing',environment([river()]),copy.deepcopy(units))
 result['bridge']=scenario('Environment B — Single narrow bridge',environment([river()],[crossing('main_bridge',400)]),copy.deepcopy(units))
 result['ford']=scenario('Environment C — Bridge and restricted ford',environment([river()],[crossing('main_bridge',400),crossing('south_ford',650,'ford',False)]),copy.deepcopy(units))
 result['ford']['units'][1]['order']=move(940,650,'south_ford')
 march=[unit(i,t,0,180,160+i*140,move(1000,160+i*140),'column' if i==1 else None) for i,t in enumerate(['infantry','infantry','cavalry','artillery'])]+[unit(4,'infantry',1,1050,800)]
 result['roads']=scenario('Environment D — Main road and track march',environment(roads=[road('column_road',300),road('gun_road',580),road('cavalry_track',440,True)]),march)
 result['defences']=scenario('Environment E — Directional earthworks and barricades',environment(defences=[defence('earthwork',850,300),defence('barricade',850,500,'barricade')]),[unit(0,'infantry',0,730,300),unit(1,'infantry',0,730,500),unit(2,'infantry',1,870,300),unit(3,'infantry',1,870,500)])
 result['rain']=copy.deepcopy(result['roads']);result['rain']['name']='Environment F — Rain and road movement';result['rain']['terrain']['environment']['weather']['type']='rain'
 result['fog']=scenario('Environment G — Fog, forest and target acquisition',environment(weather='fog'),[unit(0,'infantry',0,250,300,move(560,300)),unit(1,'revolutionary_rifles',0,250,550,move(560,550)),unit(2,'infantry',1,850,300,move(650,300)),unit(3,'artillery',1,900,550,move(690,550))],forests=[dict(x=610,y=560,radiusX=55,radiusY=95,density=.45)])
 demo=copy.deepcopy(units);demo[0]['archetype']='commonwealth_regulars';demo[1]['archetype']='commonwealth_national_cavalry';demo[2]['archetype']='commonwealth_field_artillery';demo[3]['archetype']='prussian_line';demo+= [unit(4,'prussian_line',1,940,600),unit(5,'artillery',1,1060,750)]
 result['vistula']=scenario('Environment H — Vistula-style crossing laboratory',environment([river(width=90)],[crossing('main_bridge',400) | dict(length=140),crossing('south_ford',650,'ford',False) | dict(length=140)],[road('bridge_road',400),road('ford_track',650,True)],[defence('north_bank_work',905,400),defence('ford_barricade',905,650,'barricade')]),demo,hills=[dict(x=950,y=170,radiusX=85,radiusY=100,height=12,compact=True)],forests=[dict(x=440,y=170,radiusX=150,radiusY=95,density=.65)])
 return result
def custom(data):
 def counts(side):
  d=dict(infantry=0,cavalry=0,artillery=0,specialists={})
  for u in data['units']:
   if u['army']==side:
    target=d if u['archetype'] in ['infantry','cavalry','artillery'] else d['specialists'];target[u['archetype']]=target.get(u['archetype'],0)+1
  return d
 t=data['terrain'];terrain=dict(width=data['width'],height=data['height'],environment=t['environment'],hills=[dict(x=h['x'],y=h['y'],radius_x=h['radiusX'],radius_y=h['radiusY'],height=h['height'],compact=h.get('compact',False)) for h in t['hills']],forests=[dict(x=f['x'],y=f['y'],radius_x=f['radiusX'],radius_y=f['radiusY'],density=f['density']) for f in t['forests']])
 return dict(version=1,name=data['name'],width=data['width'],height=data['height'],seed=data['seed'],symmetric=False,max_total=60,max_per_type=12,blue=counts(0),red=counts(1),terrain_preset='Open Field',terrain_seed=1796,terrain=terrain,placements=[],ai_armies=[1],ai_strategies=['balanced','hold_the_line'])
def benchmark(count,kind):
 roster=['infantry','infantry','cavalry','artillery','revolutionary_rifles','haudenosaunee_skirmishers'];u=[]
 for army in [0,1]:
  for n in range(count//2):
   x=220-(n//10)*75 if army==0 else 980+(n//10)*75;y=70+(n%10)*80
   u.append(unit(len(u),roster[n%len(roster)],army,x,y,move(950 if army==0 else 250,y)))
 e=environment()
 if kind=='river':e=environment([river()],[crossing('main_bridge',400),crossing('ford',680,'ford',False)])
 if kind in ['roads','rain']:e=environment(roads=[road('main',310),road('track',550,True)],defences=[defence('work',780,310)],weather='rain' if kind=='rain' else 'clear')
 if kind=='fog':e=environment(weather='fog')
 d=scenario(f'Environment performance {kind} {count}',e,u);d.update(height=950,duration=70);return d
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--map',choices=list(maps()),default='vistula');p.add_argument('--weather',choices=['clear','rain','fog']);p.add_argument('--output',type=Path);p.add_argument('--custom',action='store_true');p.add_argument('--write-bundled',action='store_true');a=p.parse_args()
 if a.write_bundled:
  for name,d in maps().items():
   (ROOT/f'simulation_data/combat_scenarios/environment-{name}.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
  for count in [12,24,36,60]:
   for kind in ['baseline','river','roads','rain','fog']:(ROOT/f'simulation_data/combat_scenarios/benchmark-environment-{kind}-{count}.json').write_text(json.dumps(benchmark(count,kind),ensure_ascii=False,indent=2)+'\n')
  (ROOT/'scenarios/presets/environment_vistula_lab.json').write_text(json.dumps(custom(maps()['vistula']),ensure_ascii=False,indent=2)+'\n')
 else:
  d=maps()[a.map]
  if a.weather:d['terrain']['environment']['weather']['type']=a.weather
  text=json.dumps(custom(d) if a.custom else d,ensure_ascii=False,indent=2)+'\n'
  if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text)
  else:print(text,end='')
if __name__=='__main__':main()
