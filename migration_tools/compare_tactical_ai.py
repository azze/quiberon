"""Side-swapped old/new AI tournament in an isolated copy of the current simulation.

The previous controller is read from a frozen source snapshot (or an explicit Git
revision), not approximated by switching off a subset of new features. Both controllers run against the same current combat engine.
No playable source files, balance parameters, or user saves are changed.
"""
import argparse, hashlib, json, math, shutil, subprocess, tempfile
from pathlib import Path
from .movement_reference import ROOT

BASELINE = '9a23276044df6526c7422c6777eef71bc1438732'
SEEDS = [17,31,73,101,149,211,307,401,503,601]

def formations(types, positions, army):
    rows=[]
    for i,(kind,(x,y)) in enumerate(zip(types,positions)):
        artillery='artillery' in kind
        cavalry=kind in ('commonwealth_uhlans','commonwealth_national_cavalry')
        rows.append(dict(id=army*100+i,army=army,name=f'{army}:{kind}:{i}',archetype=kind,
            position=dict(x=x if army==0 else 1400-x,y=y),facing=army*math.pi,
            commander=dict(id=f'officer-{army}-{i}',name=f'Test Officer {army}-{i}',
                personality=['methodical','cautious','aggressive','stalwart','opportunistic'][i%5],
                specialization='artillerist' if artillery else 'firebrand' if cavalry else 'drillmaster')))
    return rows

def scenarios():
    line=['commonwealth_regulars']*4
    combined=['commonwealth_regulars','prussian_line','royal_grenadiers','commonwealth_uhlans','revolutionary_rifles','commonwealth_field_artillery']
    layouts={
      'line-engagement':(line,[(350,220),(350,350),(350,480),(350,610)],None),
      'combined-arms':(combined,[(350,110+i*115) for i in range(6)],None),
      'blocked-firing-lanes':(line,[(350,270),(275,270),(350,550),(275,550)],None),
      'wooded-flanks':(combined,[(350,110+i*115) for i in range(6)],dict(hills=[],forests=[dict(x=500,y=240,radiusX=160,radiusY=180,density=.7),dict(x=900,y=240,radiusX=160,radiusY=180,density=.7),dict(x=700,y=600,radiusX=130,radiusY=140,density=.55)])),
      'concentrated-support':(line+['commonwealth_national_cavalry'],[(350,250),(350,340),(350,430),(440,680),(280,570)],None),
      'capture-centre':(line+['commonwealth_national_cavalry'],[(350,220),(350,350),(350,480),(350,610),(280,700)],None),
    }
    for name,(types,positions,terrain) in layouts.items():
        d=dict(version=1,name=name,seed=17,width=1400,height=900,duration=900,combatEnabled=True,moraleEnabled=True,cavalryEnabled=True,artilleryEnabled=True,specialistsEnabled=True,aiEnabled=True,commandersEnabled=True,aiArmies=[0,1],aiStrategies={'0':'balanced','1':'balanced'},units=formations(types,positions,0)+formations(types,positions,1),terrain=terrain,commands=[],sampleTicks=[0,9000])
        if name=='capture-centre':d['mission']=dict(objectives=[dict(id='centre',type='capture',description='Secure central road',position=dict(x=700,y=420),radius=100,duration=30,army=0)],timeout=900)
        yield name,d

def prepare(work,baseline):
    sim=work/'godot/Simulation';shutil.copytree(ROOT/'godot/Simulation',sim,ignore=shutil.ignore_patterns('bin','obj'))
    for directory in ['simulation_data','scenarios']:(work/directory).symlink_to(ROOT/directory,target_is_directory=True)
    if baseline=='previous':
        frozen=ROOT/'migration_tools/ai_tournament/baselines/tactical-v1'
        old=(frozen/'TacticalAi.cs').read_text()
        context=(frozen/'TacticalContext.cs').read_text()
        (sim/'AI/LegacyTacticalAi.cs').write_text(old.replace('TacticalAi','LegacyTacticalAi'))
        context='namespace Quiberon.Simulation;\n'+context[context.index('public sealed partial class TacticalAi'):]
        (sim/'AI/LegacyTacticalContext.cs').write_text(context.replace('TacticalAi','LegacyTacticalAi'))
        source=(frozen/'TacticalAi.cs').read_bytes()+(frozen/'TacticalContext.cs').read_bytes()
    else:
        old=subprocess.check_output(['git','show',f'{baseline}:godot/Simulation/AI/TacticalAi.cs'],cwd=ROOT,text=True)
        (sim/'AI/LegacyTacticalAi.cs').write_text(old.replace('TacticalAi','LegacyTacticalAi'))
        source=old.encode()
    p=sim/'AI/TacticalAi.cs';s=p.read_text()
    s=s.replace('    public SortedDictionary<int,string> Armies', '    public HashSet<int> EvaluationLegacyArmies {get;}=new();\n    public HashSet<int> EvaluationDisablePositions {get;}=new();\n    private LegacyTacticalAi? evaluationLegacy;\n    public SortedDictionary<int,string> Armies')
    before='''    public void Plan(Regiment u,string strategy)
    {'''
    after=before+'''
        if(EvaluationLegacyArmies.Contains(u.Army))
        {evaluationLegacy??=new(battle);evaluationLegacy.Armies[u.Army]=strategy;evaluationLegacy.Plan(u,strategy);return;}'''
    if baseline=='previous':after=after.replace('evaluationLegacy.Plan(u,strategy);','foreach(var a in Assignments)evaluationLegacy.Assign(a);evaluationLegacy.Plan(u,strategy);')
    assert before in s;s=s.replace(before,after)
    before='''    public Vec2? Skirmish(Regiment u,Regiment target)
    {'''
    assert before in s;s=s.replace(before,before+'''
        if(EvaluationLegacyArmies.Contains(u.Army)){evaluationLegacy??=new(battle);evaluationLegacy.Armies[u.Army]=Armies[u.Army];return evaluationLegacy.Skirmish(u,target);}''')
    p.write_text(s)
    context=sim/'AI/TacticalContext.cs';text=context.read_text()
    before="    private bool TryFiringPosition(Regiment u,Regiment target,string strategy)\n    {"
    assert before in text;context.write_text(text.replace(before,before+"\n        if(EvaluationDisablePositions.Contains(u.Army))return false;"))
    runner=work/'Evaluation';runner.mkdir();shutil.copy(ROOT/'migration_tools/ai_tournament/Program.cs',runner/'Program.cs')
    (runner/'Evaluation.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><ProjectReference Include="../godot/Simulation/Simulation.csproj" /></ItemGroup></Project>')
    subprocess.run(['bash','tools/dotnet.sh','build',str(runner/'Evaluation.csproj'),'-c','Release','-v','quiet'],cwd=ROOT,check=True)
    return runner/'bin/Release/net10.0/Evaluation.dll',hashlib.sha256(source).hexdigest()

def check_parity(output,runner):
    """Optional exact legacy-vs-legacy comparison with the baseline engine build."""
    cases=json.loads((output/'cases.json').read_text())
    rows=[json.loads(line) for line in (output/'results.jsonl').read_text().splitlines()]
    checked=[]
    with tempfile.TemporaryDirectory(prefix='rtt-ai-parity-') as directory:
        path=Path(directory)/'case.json'
        for c in cases:
            if c['cohort']!='old-old':continue
            path.write_text(json.dumps(c['scenario']))
            r=next(r for r in rows if r['name']==c['name'] and r['seed']==c['seed'] and r['cohort']=='old-old')
            original=json.loads(subprocess.check_output(['bash','tools/dotnet.sh',str(runner.resolve()),'--scenario',str(path)],cwd=ROOT,text=True))
            snapshot=original['snapshots'][-1]
            keys=['id','army','position','facing','strength','morale','cohesion']
            state=[dict({k:u[k] for k in keys},state=u['dynamics']['state'],withdrawn=u['dynamics']['withdrawn']) for u in snapshot['units']]
            equal=state==r['state'] and original['randomDraws']==r['randomDraws'] and snapshot['time']==r['seconds'] and (original['result'] or {}).get('winnerArmy')==r['winner']
            checked.append(dict(scenario=c['name'],seed=c['seed'],exact=equal))
            if not equal:raise RuntimeError(f"Legacy controller parity failure: {c['name']} {c['seed']}")
    (output/'parity.json').write_text(json.dumps(checked,indent=2)+'\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seeds',nargs='+',type=int,default=SEEDS);parser.add_argument('--scenarios',nargs='+');parser.add_argument('--control-seeds',type=int,default=2);parser.add_argument('--ablate-positioning',action='store_true');parser.add_argument('--legacy-runner',type=Path);parser.add_argument('--baseline',default='previous');parser.add_argument('--output',type=Path,default=ROOT/'benchmark-results/ai-tournament')
    a=parser.parse_args();
    if len(set(a.seeds))!=len(a.seeds) or a.control_seeds<0:parser.error('Use unique seeds and a nonnegative control count')
    a.output.mkdir(parents=True,exist_ok=True)
    cases=[]
    for name,d in scenarios():
        if a.scenarios and name not in a.scenarios:continue
        for index,seed in enumerate(a.seeds):
            d=d|dict(seed=seed)
            for new_army in [0,1]:cases.append(dict(name=name,seed=seed,cohort='mixed',newArmy=new_army,legacyArmies=[1-new_army],disablePositioningArmies=[new_army] if a.ablate_positioning else [],scenario=d))
            if index<a.control_seeds:
                for cohort,legacy in [('old-old',[0,1]),('new-new',[])]:cases.append(dict(name=name,seed=seed,cohort=cohort,newArmy=None,legacyArmies=legacy,disablePositioningArmies=[0,1] if a.ablate_positioning else [],scenario=d))
    if not cases:parser.error('No matching scenarios')
    (a.output/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='rtt-ai-tournament-') as directory:
        runner,sha=prepare(Path(directory),a.baseline)
        (a.output/'method.json').write_text(json.dumps(dict(baseline=a.baseline,legacySourceSha256=sha,newAISourceSha256=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'godot/Simulation/AI').glob('*.cs')))).hexdigest(),seeds=a.seeds,controlSeeds=a.control_seeds,caseCount=len(cases),positioningAblated=a.ablate_positioning,engine='current shared combat engine; per-army legacy Plan and Skirmish dispatch; same schedule and RNG'),indent=2)+'\n')
        subprocess.run(['bash','tools/dotnet.sh',str(runner),str((a.output/'cases.json').resolve()),str((a.output/'results.jsonl').resolve())],cwd=ROOT,check=True)
    if a.legacy_runner:check_parity(a.output,a.legacy_runner)
if __name__=='__main__':main()
