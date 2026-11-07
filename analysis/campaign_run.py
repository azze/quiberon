"""Headless campaign smoke/balance runs, with AI playing blue for measurement."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from campaign.state import Campaign
from .battle_report import battle_report


def run(seed=17,limit=900.,policy='upgrade',battles=5):
    state=Campaign.new(seed);reports=[];start=perf_counter()
    while state.status=='ready' and len(reports)<battles:
        running=state.start_battle()
        # The live campaign starts with player authority. This analysis-only
        # handoff gives blue its ordinary archetype orders and existing army AI.
        battle=state.encounter.with_ai_armies((0,1)).create_battle()
        before=perf_counter()
        for _ in range(round(limit/battle.rules.dt)):
            battle.step()
            if battle.result is not None:break
        row=dict(encounter=state.title,stage=state.battle_number,wall_seconds=perf_counter()-before,
                 report=battle_report(battle))
        reports.append(row)
        if battle.result is None:break # timeout is not a victory or defeat
        state=running.finish_battle(battle)
        if state.status=='reward':
            offer=next((r for r in state.rewards if r.kind==policy),state.rewards[0])
            if offer.kind=='upgrade':
                cid,options=offer.choices[(state.battle_number-1)%len(offer.choices)]
                state=state.claim(offer.id,cid,options[0])
            else:state=state.claim(offer.id)
    return dict(seed=seed,policy=policy,status=state.status,timeout=bool(reports and reports[-1]['report']['result'] is None),
                wins=state.wins,remaining_strength=sum(r.strength for r in state.army),regiments=len(state.army),
                casualties=state.casualties,wall_seconds=perf_counter()-start,battles=reports)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed',type=int,default=17);p.add_argument('--runs',type=int,default=1)
    p.add_argument('--duration',type=float,default=900,help='Maximum simulated seconds per encounter')
    p.add_argument('--battles',type=int,default=5);p.add_argument('--policy',choices=('upgrade','recruit','replenish'),default='upgrade')
    p.add_argument('--output',type=Path,default=Path('benchmark-results/campaign-run.json'))
    args=p.parse_args()
    if not 1<=args.battles<=5 or args.runs<1 or args.duration<=0:p.error('Use 1–5 battles, positive runs and duration.')
    rows=[]
    for seed in range(args.seed,args.seed+args.runs):
        result=run(seed,args.duration,args.policy,args.battles);rows.append(result)
        print(json.dumps({k:v for k,v in result.items() if k!='battles'}),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

if __name__=='__main__':main()
