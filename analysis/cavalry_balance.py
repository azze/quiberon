"""Small seeded, side-swapped cavalry experiments, independent of Pygame."""
import argparse
import json
from pathlib import Path
import statistics
import math

from simulation.geometry import touching
from simulation.regiment import MoraleState as S
from scenarios.cavalry_tests import MATCHUPS, create



def run(name,seed=1,duration=240,swapped=False):
    battle=create(name,seed,swapped)
    count=2 if name=='double-pursuit' else 1
    horses=battle.units[:count]; target=battle.units[count]
    originally_routing=target.state==S.ROUTING
    contacted=False; result='timeout';pursuit_duration=0.
    for _ in range(math.ceil(duration/battle.rules.dt)):
        battle.step()
        if any(u.combat_state=='pursuit' for u in horses):pursuit_duration+=battle.rules.dt
        contacted=contacted or any(touching(u,target) for u in horses)
        if target.withdrawn: result='escaped'; break
        if not target.active or (not originally_routing and target.state==S.ROUTING): result='cavalry'; break
        if not any(u.effective for u in horses): result='infantry'; break
    totals={key:sum(u.analysis.get(key,0) for u in horses) for key in horses[0].analysis}
    impacts=totals.get('charges',0)
    return dict(matchup=name,seed=seed,swapped=swapped,result=result,duration=round(battle.time,1),
                cavalry_lost=sum(u.stats.strength-u.strength for u in horses),infantry_lost=target.stats.strength-target.strength,
                charge_initiations=totals.get('charge_initiations',impacts),impacts=impacts,
                mean_impact_damage=totals.get('impact_casualties',0)/max(1,impacts) if 'impact_casualties' in totals else None,
                mean_impact_momentum=totals.get('impact_momentum',0)/max(1,impacts),
                impact_morale_shock=totals.get('impact_morale_shock',0),
                morale_shock=totals.get('morale_shock',0),successful_charges=totals.get('charge_successes',0),
                failed_charges=totals.get('failed_charges',0),aborted_charges=totals.get('aborted_charges',0),
                pursuit_duration=pursuit_duration,pursuit_seconds=totals.get('pursuit_seconds',0),pursuit_casualties=totals.get('pursuit_casualties',0),
                cavalry_pursuit_losses=totals.get('pursuit_losses',0),contacted=contacted,
                failed_to_catch=originally_routing and not contacted,
                cavalry_remaining=sum(u.strength for u in horses))


def aggregate(rows):
    groups={}
    for name in dict.fromkeys(r['matchup'] for r in rows):
        own=[r for r in rows if r['matchup']==name]
        groups[name]=dict(runs=len(own),results={k:sum(r['result']==k for r in own) for k in sorted({r['result'] for r in own})},
                         means={key:statistics.mean(r[key] for r in own) for key in own[0]
                                if key not in ('matchup','seed','swapped','result') and own[0][key] is not None})
        group=groups[name];impacts=sum(r['impacts'] for r in own)
        group['cavalry_win_rate']=sum(r['result']=='cavalry' for r in own)/len(own)
        group['charge_success_rate']=sum(r['successful_charges'] for r in own)/max(1,impacts)
        if own[0]['mean_impact_damage'] is not None:
            group['means']['mean_impact_damage']=sum(r['mean_impact_damage']*r['impacts'] for r in own)/max(1,impacts)
    return groups


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--matchups',nargs='+',choices=MATCHUPS,default=MATCHUPS)
    p.add_argument('--runs',type=int,default=5); p.add_argument('--seed',type=int,default=1)
    p.add_argument('--duration',type=float,default=240)
    p.add_argument('--one-sided',action='store_true',help='Skip mirrored, side-swapped repetitions')
    p.add_argument('--output',type=Path,default=Path('benchmark-results/cavalry-balance.json'))
    args=p.parse_args()
    if args.runs<1 or not math.isfinite(args.duration) or args.duration<=0:p.error('Positive runs and finite duration required')
    rows=[run(name,seed,args.duration,swapped) for name in args.matchups
          for seed in range(args.seed,args.seed+args.runs) for swapped in ((False,) if args.one_sided else (False,True))]
    report=dict(duration_limit=args.duration,battles=rows,aggregate=aggregate(rows))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['aggregate'],indent=2))


if __name__=='__main__':main()
