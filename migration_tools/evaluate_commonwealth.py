"""Stage-1 battle laboratory: repeated comparisons, historical controls, side swaps and native benchmarks.

No campaign costs or progression. Timeouts remain inconclusive. Generic controls retain the
historical personality and use the existing Inspirer specialization; deterministic signature
isolation is covered separately by CommonwealthContentTests.
"""
import argparse,copy,json,math,subprocess
from pathlib import Path
from .evaluate_ai import run,summary
from .movement_reference import ROOT
SCENARIOS=ROOT/'simulation_data/combat_scenarios'
RUNNER=ROOT/'godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll'

def swapped(data):
 data=copy.deepcopy(data)
 for unit in data['units']:
  unit['army']=1-unit['army'];unit['position']['x']=data['width']-unit['position']['x'];unit['facing']=math.pi-unit.get('facing',0)
  if unit.get('order',{}).get('destination') is not None:unit['order']['destination']['x']=data['width']-unit['order']['destination']['x']
  if unit.get('order',{}).get('facing') is not None:unit['order']['facing']=math.pi-unit['order']['facing']
 for command in data.get('commands',[]):
  action=command.get('order',{})
  if action.get('destination') is not None:action['destination']['x']=data['width']-action['destination']['x']
  if action.get('facing') is not None:action['facing']=math.pi-action['facing']
 for leader in data.get('armyCommanders',[]):
  leader['army']=1-leader['army']
  if leader.get('position'):leader['position']['x']=data['width']-leader['position']['x']
 data['aiStrategies']={str(1-int(key)):value for key,value in data.get('aiStrategies',{}).items()}
 data['aiArmies']=[1-side for side in data['aiArmies']]
 for hill in data.get('terrain',{}).get('hills',[]) if data.get('terrain') else []:hill['x']=data['width']-hill['x']
 for forest in data.get('terrain',{}).get('forests',[]) if data.get('terrain') else []:forest['x']=data['width']-forest['x']
 return data

def neutral(data):
 data=copy.deepcopy(data);data['armyCommanders']=[]
 for unit in data['units']:
  c=unit.get('commander',{})
  if c.get('definitionId'):
   c.update(id=f'control-{unit["id"]}',name='Generic comparison officer',definitionId='',specialization='inspirer',biography='Same personality; generic Inspirer control.')
 return data

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--suite',choices=['roster','commanders','battles','benchmarks','all'],default='battles');p.add_argument('--seeds',nargs='+',type=int,default=[17,31,73]);p.add_argument('--swap',action='store_true');p.add_argument('--duration',type=float);p.add_argument('--output',type=Path,default=ROOT/'benchmark-results/commonwealth-stage1-evaluation.json');args=p.parse_args()
 files=sorted(SCENARIOS.glob('commonwealth-*.json'))
 def included(name):
  if args.suite=='all':return True
  if args.suite=='commanders':return name.startswith('commonwealth-commander-')
  if args.suite=='battles':return name.startswith('commonwealth-battle-')
  if args.suite=='roster':return not name.startswith(('commonwealth-commander-','commonwealth-battle-'))
  return False
 rows=[];benchmarks=[]
 for path in files:
  name=path.stem
  if not included(name):continue
  for seed in args.seeds:
   for swap in [False,True] if args.swap else [False]:
    data=json.loads(path.read_text());data['seed']=seed
    if args.duration is not None:data['duration']=args.duration
    if swap:data=swapped(data)
    for control in [False,True] if name.startswith('commonwealth-commander-') else [False]:
     result=run(neutral(data) if control else data);row=summary(result);row.update(scenario=name,seed=seed,swapped=swap,genericControl=control)
     row['participation']=[{k:v for k,v in entry.items() if k!='commander'} for entry in row['participation']];rows.append(row)
     print(name,seed,'swapped' if swap else 'normal','control' if control else 'authored','TIMEOUT' if row['timedOut'] else row['result']['id'],row['seconds'],flush=True)
 if args.suite in ['all','benchmarks']:
  for count in [12,24,36,60]:
   name=f'benchmark-commonwealth-{count}'
   result=subprocess.run(['bash','tools/dotnet.sh',str(RUNNER),'--combat-scenario',name,'--benchmark'],cwd=ROOT,text=True,capture_output=True,check=True,timeout=120)
   report=json.loads(result.stdout);benchmarks.append(report);print(name,'mean',report['meanMs'],'p95',report['p95Ms'],flush=True)
 report=dict(description=__doc__,battles=rows,benchmarks=benchmarks)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
