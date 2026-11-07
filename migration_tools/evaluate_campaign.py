"""Run native campaign progression/encounter laboratories; never label timeouts as wins."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seeds',type=int,nargs='+',default=[17,31,73]);p.add_argument('--suite',choices=['runs','encounters','builds','fixtures'],default='runs');p.add_argument('--output-dir',type=Path,default=ROOT/'benchmark-results/campaign');a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
 commands=[]
 if a.suite=='fixtures':commands=[('fixture-'+b,['--campaign-fixture','--branch',b]) for b in ['rescue','intercept']]
 for seed in a.seeds:
  if a.suite=='runs':commands.extend((f'default-{b}-{seed}',['--campaign-run','--seed',str(seed),'--branch',b]) for b in ['rescue','intercept'])
  if a.suite=='encounters':commands.extend((f'stage-{n}-{b}-seed{seed}',['--campaign-stage',str(n),'--seed',str(seed),'--branch',b]) for n in range(1,7) for b in (['rescue','intercept'] if n==4 else ['rescue']))
  if a.suite=='builds':commands.extend((f'run-{b}-{seed}',['--campaign-run','--build',b,'--seed',str(seed)]) for b in ['people','mobile','firepower'])
 for name,args in commands:
  out=a.output_dir/(name+'.json');r=subprocess.run(['bash','tools/dotnet.sh','godot/Simulation.Runner/bin/Release/net10.0/Simulation.Runner.dll',*args,'--output',str(out)],cwd=ROOT,text=True,capture_output=True)
  if r.returncode:raise SystemExit(r.stderr)
  d=json.loads(r.stdout);print(name,d['ending'],[(b['stage'],b['outcome']) for b in d['reports']],flush=True)
if __name__=='__main__':main()
