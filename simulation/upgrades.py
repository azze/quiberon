"""Acquired commander abilities: small registry and hooks into existing rules."""
from dataclasses import dataclass
from .unit_stats import UnitType as U
from .formations import Formation as F
from .orders import OrderKind as O
from .geometry import Vec


@dataclass(frozen=True)
class Upgrade:
    id: str
    name: str
    description: str
    kinds: tuple
    roles: tuple = ()
    line_required: bool = False
    max_rank: int = 1
    prerequisites: tuple = ()


DEFINITIONS=(
 Upgrade('rolling_volley','Rolling Volley','Line, cohesion >=70, stationary: reload -20% near a steady infantry ally within 90 m.',(U.INFANTRY,),line_required=True),
 Upgrade('swift_reform','Swift Reform','Formation time -25%, manoeuvre disruption -20%, quiet cohesion recovery +35%.',(U.INFANTRY,U.CAVALRY)),
 Upgrade('rallying_presence','Rallying Presence','Steady officer supports allies within 125 m: +0.30 morale/s, +0.45 while rallying; strongest aura only.',tuple(U)),
 Upgrade('controlled_charge','Controlled Charge','Charge turning +20%, alignment +10%, impact disorder -30%, cooldown -20%, reform time -30%.',(U.CAVALRY,)),
 Upgrade('relentless_pursuit','Relentless Pursuit','Pursuit power +20%; recover 8 cohesion once per enemy routed by this regiment, per battle.',(U.CAVALRY,)),
 Upgrade('shock_commander','Shock Commander','Forceful charges against exposed enemies inflict +35% morale shock; prepared fronts resist.',(U.INFANTRY,U.CAVALRY),roles=('anchor','cavalry','flanker')),
 Upgrade('woodland_ambush','Woodland Ambush','First stationary volley from obscured forest cover: +6 morale shock and -8 cohesion. Reset needs 30 s without attacking and a 40 m move.',(U.INFANTRY,),roles=('skirmisher','rifles')),
 Upgrade('harassing_fire','Harassing Fire','A volley causing casualties removes 3 additional target cohesion; no extra casualty damage.',(U.INFANTRY,),roles=('skirmisher','rifles')),
 Upgrade('steadfast_defence','Steadfast Defence','Stationary, steady defensive line at cohesion >=60: charge resistance +20%, morale shock -20%.',(U.INFANTRY,),line_required=True),
 Upgrade('mobile_battery','Mobile Battery','Limber and setup times -40%; existing battery AI can finish repositioning sooner.',(U.ARTILLERY,)),
 Upgrade('calculated_fire','Calculated Fire','After 6 seconds stationary and deployed: horizontal and vertical aim scatter -35%; moving resets preparation.',(U.ARTILLERY,)),
 Upgrade('inspired_attack','Inspired Attack','Damaging wavering/routing enemies inspires visible allies within 100 m for +3 morale; shared army cooldown 20 s.',(U.INFANTRY,U.CAVALRY)),
)
REGISTRY={u.id:u for u in DEFINITIONS}


@dataclass(frozen=True)
class Tuning:
    rolling_reload: float = .8
    swift_formation: float = .75
    swift_manoeuvre: float = .8
    swift_recovery: float = 1.35
    aura_morale: float = .30
    aura_rally: float = .45
    controlled_turn: float = 1.2
    controlled_alignment: float = 1.1
    controlled_disorder: float = .7
    controlled_cooldown: float = .8
    controlled_reform: float = .7
    pursuit_power: float = 1.2
    pursuit_recovery: float = 8.
    shock: float = 1.35
    ambush_shock: float = 6.
    ambush_cohesion: float = 8.
    ambush_reset: float = 30.
    ambush_move: float = 40.
    harassing_cohesion: float = 3.
    defence: float = .8
    mobile: float = .6
    calculated: float = .65
    calculated_seconds: float = 6.
    inspired_morale: float = 3.
    inspired_cooldown: float = 20.
TUNING=Tuning()


def has(unit,key):return unit.commander is not None and key in unit.commander.upgrades
def eligible(archetype,key):
    d=REGISTRY[key]
    return archetype.stats.kind in d.kinds and (not d.roles or archetype.role in d.roles) and (not d.line_required or F.LINE in archetype.formations)


def available(archetype,commander,limit=3):
    if len(commander.upgrades)>=limit:return ()
    return tuple(k for k,d in REGISTRY.items() if eligible(archetype,k) and k not in commander.upgrades and all(p in commander.upgrades for p in d.prerequisites))


def validate_assignment(unit):
    if unit.commander and any(not eligible(unit.archetype,k) for k in unit.commander.upgrades):raise ValueError('Commander upgrade cannot be used by this archetype.')


def prepared_defence(u):
    return u.speed<.1 and u.state.value=='steady' and u.cohesion>=60 and not u.transition_left and u.formation==F.LINE and u.order.kind in (O.HOLD,O.DEFEND,O.RESERVE)


def update_stationary(u,dt):
    if not u.commander or not u.commander.upgrades:return
    ready=u.speed<.1 and not u.limbered and u.setup_left<=0 and not u.transition_left
    u.upgrade_stationary=u.upgrade_stationary+dt if ready else 0.


def volley_reload(battle,u):
    if not has(u,'rolling_volley') or u.formation!=F.LINE or u.cohesion<70 or u.speed>.1:return 1.
    index=battle._fire_index
    candidates=index.segment(u.pos-Vec(90,90),u.pos+Vec(90,90)) if index else battle.units
    if any(f.id!=u.id and f.army==u.army and f.effective and f.state.value=='steady' and f.stats.kind==U.INFANTRY and
           (f.pos-u.pos).length()<=90 and battle.visibility(u,f).visible for f in candidates):
        battle.activate(u,'Rolling Volley: supporting infantry fire')
        return TUNING.rolling_reload
    return 1.


def on_volley(battle,u,target,losses):
    cover=u.forest_cover if battle.tick else battle.terrain.movement_effect(u,Vec(0,0),battle.rules.terrain).forest
    state=u.upgrade_state
    if has(u,'woodland_ambush'):
        used=state.get('ambush_position')
        reset=used is None or (battle.time-state.get('last_attack',0)>=TUNING.ambush_reset and (u.pos-used).length()>=TUNING.ambush_move)
        if reset and cover>=.4 and u.speed<.1 and battle.visibility(target,u).transmission<.7:
            from .combat import damage
            state['ambush_position']=u.pos
            damage(battle,target,0,'woodland ambush',u,shock=TUNING.ambush_shock)
            target.cohesion=max(0.,target.cohesion-TUNING.ambush_cohesion)
            battle.activate(u,'Woodland Ambush: concealed opening volley')
    if losses>0 and has(u,'harassing_fire'):
        target.cohesion=max(0.,target.cohesion-TUNING.harassing_cohesion)
        battle.activate(u,'Harassing Fire: formation disrupted')
    state['last_attack']=battle.time


def inspired(battle,u,target,losses):
    if losses<=0 or not has(u,'inspired_attack') or target.state.value not in ('wavering','routing'):return
    key=('inspiration',u.army)
    if battle.time<battle.upgrade_next.get(key,0):return
    battle.upgrade_next[key]=battle.time+TUNING.inspired_cooldown
    for f in battle.units:
        if f.id!=u.id and f.army==u.army and f.active and f.state.value!='routing' and (f.pos-u.pos).length()<100 and battle.visibility(u,f).visible:
            f.morale=min(100.,f.morale+TUNING.inspired_morale)
    battle.activate(u,'Inspired Attack: nearby allies encouraged')


def on_rout(battle,target,attacker):
    if attacker is None or attacker.army==target.army or not attacker.effective or not has(attacker,'relentless_pursuit'):return
    seen=attacker.upgrade_state.setdefault('pursuit_routs',set())
    if target.id in seen:return
    seen.add(target.id);attacker.cohesion=min(100.,attacker.cohesion+TUNING.pursuit_recovery)
    battle.activate(attacker,'Relentless Pursuit: exploiting an enemy rout')


def attack_shock(u,target,momentum,prepared):
    if not has(u,'shock_commander') or prepared or momentum<=.25:return 1.
    from .geometry import angle_delta,angle_to
    exposed=target.state.value!='steady' or target.cohesion<60 or abs(angle_delta(target.facing,angle_to(target.pos,u.pos)))>1.0472
    return TUNING.shock if exposed else 1.
