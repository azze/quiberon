"""Read-only battle report data, usable by the viewer and headless callers."""
from simulation.regiment import MoraleState


def battle_report(battle):
    rows=[]
    for u in battle.units:
        initial=battle.initial_unit_strength.get(u.id,u.stats.strength)
        status='destroyed' if u.strength<=0 else 'withdrawn' if u.withdrawn else u.state.value
        rows.append(dict(id=u.id,name=u.name,label=f'#{u.id} {u.archetype.menu_name or u.archetype.name}',
                         army=u.army,archetype_id=u.archetype.id,archetype=u.archetype.name,
                         initial=initial,remaining=u.strength,lost=max(0,initial-u.strength),status=status,
                         effective=u.effective,morale=u.morale,cohesion=u.cohesion,
                         commander=u.commander.to_dict() if u.commander else None,
                         guns=u.available_guns,**dict(u.analysis)))
    armies=[]
    for army,initial in sorted(battle.initial_strength.items()):
        units=[u for u in battle.units if u.army==army]
        own=[r for r in rows if r['army']==army]
        remaining=sum(u.strength for u in units)
        armies.append(dict(army=army,initial=initial,remaining=remaining,lost=max(0,initial-remaining),
                           effective=sum(u.strength for u in units if u.effective),
                           destroyed=sum(u.strength<=0 for u in units),withdrawn=sum(u.withdrawn for u in units),
                           routing=sum(u.active and u.state==MoraleState.ROUTING for u in units),
                           **{key:sum(r[key] for r in own) for key in ('volleys','charges','casualties_inflicted','rout_events','rallies','trait_activations')}))
    groups=[]
    for army,key in sorted({(r['army'],r['archetype_id']) for r in rows}):
        own=[r for r in rows if r['army']==army and r['archetype_id']==key]
        group=dict(army=army,archetype_id=key,label=own[0]['archetype'],status=f'{len(own)} units')
        group.update({name:sum(r[name] for r in own) for name in ('initial','remaining','lost','casualties_inflicted','volleys','charges','rout_events','rallies')})
        groups.append(group)
    return dict(seed=battle.seed,result=battle.result,duration=battle.time,width=battle.rules.width,height=battle.rules.height,
                metrics=dict(battle.metrics),armies=armies,regiments=rows,archetypes=groups)
