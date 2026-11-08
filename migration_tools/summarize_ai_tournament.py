"""Summarize side-swapped tournaments without treating timed-out battles as victories."""
import argparse,json,random,statistics,collections
from pathlib import Path

def summarize(rows):
    mixed=[r for r in rows if r['cohort']=='mixed']
    def outcome(r):
        return 'unresolved' if r['timedOut'] or r['winner'] is None else 'new' if r['winner']==r['newArmy'] else 'old'
    def result(rs):
        counts=collections.Counter(outcome(r) for r in rs);n=len(rs);resolved=counts['new']+counts['old']
        pairs=collections.defaultdict(list)
        for r in rs:pairs[(r['name'],r['seed'])].append(r)
        def side_metrics(r,new):return next(a for a in r['armies'] if a['army']==(r['newArmy'] if new else 1-r['newArmy']))
        metrics={}
        for label,new in [('new',True),('old',False)]:
            metrics[label]={k:statistics.mean(side_metrics(r,new)[k] for r in rs) for k in ['lost','remaining','salvos','charges','targetChanges','formationChanges','movingSeconds','firingSeconds','blockedFiringRegimentSeconds']}
            metrics[label]['meanLostFraction']=statistics.mean(side_metrics(r,new)['lost']/side_metrics(r,new)['initial'] for r in rs)
        return dict(games=n,newWins=counts['new'],oldWins=counts['old'],unresolved=counts['unresolved'],newWinFraction=counts['new']/n,resolvedNewWinFraction=counts['new']/resolved if resolved else None,eventualNewWinBounds=[counts['new']/n,(counts['new']+counts['unresolved'])/n],pairsNewSweep=sum(len(p)==2 and all(outcome(r)=='new' for r in p) for p in pairs.values()),pairsOldSweep=sum(len(p)==2 and all(outcome(r)=='old' for r in p) for p in pairs.values()),meanSeconds=statistics.mean(r['seconds'] for r in rs),metrics=metrics)
    overall=result(mixed)
    seeds=sorted({r['seed'] for r in mixed});rng=random.Random(1796);samples=[]
    blocks={s:[r for r in mixed if r['seed']==s] for s in seeds}
    for _ in range(10000):
        rs=[r for s in rng.choices(seeds,k=len(seeds)) for r in blocks[s]]
        samples.append(sum(1 if outcome(r)=='new' else .5 if outcome(r)=='unresolved' else 0 for r in rs)/len(rs))
    samples.sort();overall['seedClusterBootstrap95ScoreInterval']=[samples[249],samples[9749]]
    overall['scoreConvention']='Win=1, loss=0, unresolved=0.5 for this interval only; unresolved are not victories.'
    controls={}
    for cohort in ['old-old','new-new']:
        rs=[r for r in rows if r['cohort']==cohort]
        controls[cohort]=dict(games=len(rs),army0Wins=sum(r['winner']==0 for r in rs),army1Wins=sum(r['winner']==1 for r in rs),unresolved=sum(r['timedOut'] or r['winner'] is None for r in rs))
    return dict(overall=overall,scenarios={name:result([r for r in mixed if r['name']==name]) for name in dict.fromkeys(r['name'] for r in mixed)},controls=controls)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args()
    rows=[json.loads(line) for line in (a.directory/'results.jsonl').read_text().splitlines()]
    summary=summarize(rows);(a.directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Scenario | New wins | Old wins | Unresolved')
    for name,r in summary['scenarios'].items():print(f"{name} | {r['newWins']} | {r['oldWins']} | {r['unresolved']}")
    print(json.dumps(summary['overall'],indent=2))
if __name__=='__main__':main()
