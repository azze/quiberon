"""Run reproducible autonomous battles, report timeouts honestly and swap deployments."""
import argparse,json,math,subprocess,tempfile
from pathlib import Path
from .movement_reference import ROOT
from .ai_reference import SCENARIOS

def run(data):
 with tempfile.TemporaryDirectory(prefix='rtt-ai-') as work:
  path=Path(work)/'scenario.json';path.write_text(json.dumps(data))
  result=subprocess.run(['bash','tools/dotnet.sh','godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll','--scenario',str(path)],cwd=ROOT,text=True,capture_output=True,check=True,timeout=120)
 return json.loads(result.stdout)
def summary(r):
 frame=r['snapshots'][-1];m=r['metrics'];p=r.get('participation',[])
 initial={u['id']:u['strength'] for u in r['snapshots'][0]['units']};final={u['id']:u['strength'] for u in frame['units']};casualties={}
 for u in p:casualties[u['category']]=casualties.get(u['category'],0)+initial[u['id']]-final[u['id']]
 return dict(casualtiesByCategory=casualties,chargeSuccessRate=m['chargeSuccesses']/m['chargeImpacts'] if m['chargeImpacts'] else None,result=r['result'],timedOut=r['timedOut'],seconds=frame['time'],firstEngagement=m['firstEngagement'],volleys=m['volleys'],artilleryShots=m['artilleryShots'],charges=m['chargeStarts'],impacts=m['chargeImpacts'],chargeSuccesses=m['chargeSuccesses'],routs=m['routs'],rallies=m['rallies'],targetChanges=m['aiTargetChanges'],formationChanges=m['aiFormationChanges'],neverParticipated=[u['id'] for u in p if u['inflicted']==0 and u['shots']==0],participation=p,randomDraws=r['randomDraws'],finalStrengths=[u['strength'] for u in frame['units']])
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--scenarios',nargs='+',default=['ai-infantry','ai-combined']);parser.add_argument('--seeds',nargs='+',type=int,default=[17,31,73]);parser.add_argument('--swap',action='store_true');parser.add_argument('--output',type=Path,default=ROOT/'benchmark-results/m5-battles.json');args=parser.parse_args();rows=[]
 for name in args.scenarios:
  for seed in args.seeds:
   for swap in [False,True] if args.swap else [False]:
    data=json.loads((SCENARIOS/(name+'.json')).read_text());data['seed']=seed
    if swap:
     for u in data['units']:u['army']=1-u['army'];u['position']['x']=data['width']-u['position']['x'];u['facing']=math.pi-u.get('facing',0)
     data['aiStrategies']={str(1-int(k)):v for k,v in data['aiStrategies'].items()}
    r=summary(run(data));r.update(scenario=name,seed=seed,swapped=swap);rows.append(r)
    print(name,seed,swap,'TIMEOUT' if r['timedOut'] else r['result']['id'],r['seconds'],'s',r['volleys'],'volleys',r['artilleryShots'],'rounds',r['charges'],'charges',flush=True)
 args.output.parent.mkdir(exist_ok=True,parents=True);args.output.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
