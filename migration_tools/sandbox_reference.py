"""Read-only Python oracle for native sandbox charges, upgrades and terrain recipes."""
import json, math
from dataclasses import asdict
from pathlib import Path
from simulation import commanders as c, archetypes, upgrades, infantry_charge
from simulation.terrain import generate_terrain, TERRAIN_PRESETS
from .ai_reference import officer, auto
from .artillery_reference import unit, enemy
from .dynamics_reference import make

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'migration_tools/sandbox_fixtures'

def probes():
    rows=[]
    for d in upgrades.DEFINITIONS:
        a=next(a for a in archetypes.ARCHETYPES.values() if upgrades.eligible(a,d.id))
        kind=a.stats.kind.value
        for cohesion in (50,85,100):
            spec='artillerist' if kind=='artillery' else 'pursuit_specialist' if kind=='cavalry' else 'drillmaster'
            scenario=auto(f'{d.id}-{cohesion}',[unit(0,300,300,archetype=a.id),enemy(1,350,300)])
            scenario['aiEnabled']=False
            for i,u in enumerate(scenario['units']):u['commander']=dict(officer(i,specialization=spec if i==0 else 'drillmaster'),upgrades=[d.id] if i==0 else [])
            b,_=make(scenario)
            for u,raw in zip(b.units,scenario['units']):u.commander=c.Commander.from_dict(raw['commander'])
            u=b.units[0];u.cohesion=cohesion;u.upgrade_stationary=6.1
            expected=dict(formation=archetypes.formation_time(u,7),manoeuvre=archetypes.manoeuvre_factor(u),recovery=c.recovery_factor(u),shock=c.shock_factor(u),defence=c.defence_factor(u,b.units[1]),redeploy=c.redeploy_factor(u),scatter=c.scatter_factor(u),pursuit=c.pursuit_factor(u),chargeShock=c.charge_shock_factor(u,b.units[1],.7,False),aura=c.upgrades.TUNING.aura_morale if upgrades.has(u,'rallying_presence') else 0)
            rows.append(dict(input=scenario,cohesion=cohesion,action='factors',expected=expected))
    for angle in (0,math.pi/2,math.pi):
        for momentum in (.2,.7,1):
            scenario=auto(f'bayonet-{angle}-{momentum}',[unit(0,300,300,archetype='royal_grenadiers'),enemy(1,330,300,facing=angle)])
            scenario['aiEnabled']=False;scenario['randomDraws']=[.5]*20
            scenario['units'][0]['commander']=dict(officer(0,specialization='firebrand'),upgrades=['shock_commander'])
            scenario['units'][1]['commander']=officer(1)
            b,_=make(scenario)
            for u,raw in zip(b.units,scenario['units']):u.commander=c.Commander.from_dict(raw['commander'])
            u,t=b.units;u.infantry_charging=True;u.charge_momentum=momentum;u.charge_sequence=1
            infantry_charge.impact(b,u,t)
            rows.append(dict(input=scenario,momentum=momentum,action='impact',expected=dict(strength=t.strength,morale=t.morale,cohesion=t.cohesion,attackerCohesion=u.cohesion,cooldown=u.charge_cooldown,lastMomentum=u.charge_last_momentum)))
    return rows

def generate():
    FIXTURES.mkdir(exist_ok=True)
    (ROOT/'simulation_data/commander_upgrades.json').write_text(json.dumps(dict(limit=3,tuning=asdict(upgrades.TUNING),definitions=[dict(id=d.id,name=d.name,description=d.description,categories=[k.value for k in d.kinds],roles=d.roles,lineRequired=d.line_required,maxRank=d.max_rank,prerequisites=d.prerequisites) for d in upgrades.DEFINITIONS]),indent=2)+'\n')
    (FIXTURES/'probes.json').write_text(json.dumps(probes(),indent=2)+'\n')
    rows=[]
    for seed in (0,17,-37,2**50+127,-2**63):
        for preset in TERRAIN_PRESETS:
            t=generate_terrain(preset,1600,1000,seed)
            rows.append(dict(seed=str(seed),preset=preset,width=1600,height=1000,hills=[asdict(h) for h in t.hills],forests=[asdict(f) for f in t.forests]))
    (FIXTURES/'terrain.json').write_text(json.dumps(rows,indent=2)+'\n')
    scenario=auto('Infantry Bayonet Assault',[unit(0,400,300,archetype='royal_grenadiers'),enemy(1,447,300)],duration=90)
    scenario['aiEnabled']=False;scenario['units'][0]['commander']=dict(officer(0,'aggressive','firebrand'),upgrades=['shock_commander','swift_reform'])
    scenario['commands']=[dict(tick=0,regimentId=0,order=dict(kind='charge',targetId=1))]
    (ROOT/'simulation_data/combat_scenarios/infantry-bayonet.json').write_text(json.dumps(scenario,indent=2)+'\n')
    combined=json.loads((ROOT/'simulation_data/combat_scenarios/ai-combined.json').read_text())
    combined['name']='Commander Builds — Upgraded Combined Arms'
    for u in combined['units']:
        a=archetypes.ARCHETYPES[u['archetype']];kind=a.stats.kind.value
        spec='artillerist' if kind=='artillery' else 'firebrand' if kind=='cavalry' else 'drillmaster'
        keys=['mobile_battery','calculated_fire'] if kind=='artillery' else ['controlled_charge','relentless_pursuit'] if kind=='cavalry' else ['woodland_ambush','harassing_fire'] if a.role in ('skirmisher','rifles') else ['rolling_volley','swift_reform','rallying_presence']
        u['commander']=dict(officer(u['id'],specialization=spec),upgrades=keys)
    (ROOT/'simulation_data/combat_scenarios/upgraded-combined.json').write_text(json.dumps(combined,indent=2)+'\n')

if __name__=='__main__':generate()
