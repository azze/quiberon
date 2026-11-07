"""Immutable officers and small, explicit hooks into existing regiment rules.

Name/trait generation receives a seeded RNG; it never consumes combat RNG.
No commander has mutable state or an independently simulated battlefield body.
"""
from dataclasses import dataclass,asdict
from enum import Enum
from .unit_stats import UnitType as U
from .orders import OrderKind as O
from .geometry import angle_delta,angle_to


class Personality(str,Enum):
    AGGRESSIVE='aggressive'
    CAUTIOUS='cautious'
    METHODICAL='methodical'
    OPPORTUNISTIC='opportunistic'
    STALWART='stalwart'


class Specialization(str,Enum):
    DRILLMASTER='drillmaster'
    FIREBRAND='firebrand'
    PATHFINDER='pathfinder'
    SHARPSHOOTER='sharpshooter'
    ARTILLERIST='artillerist'
    INSPIRER='inspirer'
    PURSUIT='pursuit_specialist'
    DEFENSIVE='defensive_tactician'


P=Personality;S=Specialization
PERSONALITIES={
    P.AGGRESSIVE:('Aggressive','Commits quickly; exploits broken enemies.','Overextends and disengages late.'),
    P.CAUTIOUS:('Cautious','Keeps distance; breaks off unfavourable fights early.','Slower commitment and shorter pursuit.'),
    P.METHODICAL:('Methodical','Preserves cohesion; briefly reforms before weak attacks.','Slower exploitation of opportunities.'),
    P.OPPORTUNISTIC:('Opportunistic','Prefers exposed or broken enemies; commits quickly.','May divert from an autonomous objective.'),
    P.STALWART:('Stalwart','Resists shock and steadies defensive positions.','Stays in losing fights longer.'),
}
SPECIALIZATIONS={
    S.DRILLMASTER:('Drillmaster',(U.INFANTRY,U.CAVALRY),'High cohesion: formation time -15%, manoeuvre loss -10%, quiet recovery +10%.','Bonuses fade to zero at 40 cohesion.'),
    S.FIREBRAND:('Firebrand',(U.INFANTRY,U.CAVALRY),'Exposed charge morale shock +12% with momentum above 25%.','Up to 3 extra cohesion lost after impact; autonomous cavalry pursuit +15%.'),
    S.PATHFINDER:('Pathfinder',tuple(U),'Forest slowdown -20%, uphill sensitivity -10%, terrain disruption -15%.','Little benefit on flat open ground.'),
    S.SHARPSHOOTER:('Sharpshooter',(U.INFANTRY,),'Stationary, cohesion >=50: accuracy up to +12%, fading with obscuration.','Reload time +8%, even when the aim bonus is inactive.'),
    S.ARTILLERIST:('Artillerist',(U.ARTILLERY,),'Deployed battery aim scatter -12%; physical projectile rules unchanged.','Limbering and setup time +10%.'),
    S.INSPIRER:('Inspirer',tuple(U),'Visible allies within 125 m: morale +0.12/s, rally +0.18/s; reduced rout shock.','No offensive bonus; unsteady sources inactive; strongest aura only.'),
    S.PURSUIT:('Pursuit Specialist',(U.CAVALRY,),'Pursuit power +12%, contact gap +10%, pursuit congestion disruption -10%.','Frontal combat against steady targets -10%.'),
    S.DEFENSIVE:('Defensive Tactician',(U.INFANTRY,),'Prepared frontal charge impact/cohesion loss -10%; quiet defensive recovery +10%.','Aggressive advance speed -5%; resistance requires holding steady at cohesion >=60.'),
}


@dataclass(frozen=True)
class Commander:
    id: str
    name: str
    background: str
    personality: Personality
    specialization: Specialization
    rank: str = ''
    biography: str = ''
    upgrades: tuple[str,...] = ()

    @property
    def display_name(self):return f'{self.rank} {self.name}'.strip()

    def validate(self,kind=None):
        for field,limit,required in (('id',96,True),('name',100,True),('background',80,True),('rank',60,False),('biography',300,False)):
            value=getattr(self,field)
            if not isinstance(value,str) or len(value)>limit or (required and not value.strip()) or any(not c.isprintable() for c in value):
                raise ValueError(f'Invalid commander {field}.')
        if not isinstance(self.personality,P) or not isinstance(self.specialization,S):raise ValueError('Unknown commander trait.')
        if kind is not None and kind not in SPECIALIZATIONS[self.specialization][1]:raise ValueError('Commander specialization is incompatible with this regiment category.')
        from .upgrades import REGISTRY
        if not isinstance(self.upgrades,tuple) or len(self.upgrades)>12 or any(not isinstance(k,str) or k not in REGISTRY for k in self.upgrades) or len(set(self.upgrades))!=len(self.upgrades):raise ValueError('Invalid commander upgrades.')
        if kind is not None and any(kind not in REGISTRY[k].kinds for k in self.upgrades):raise ValueError('Upgrade category incompatible with regiment.')

    def to_dict(self):
        data=asdict(self);data['personality']=self.personality.value;data['specialization']=self.specialization.value
        return data

    @classmethod
    def from_dict(cls,data):
        data=dict(data);data['personality']=P(data['personality']);data['specialization']=S(data['specialization'])
        data['upgrades']=tuple(data.get('upgrades',()))
        value=cls(**data);value.validate();return value


# European pools form fictional combinations. Haudenosaunee names are supplied
# by the user and used whole, without invented surnames or European ranks.
HAUDENOSAUNEE_NAMES=(
    'Tyorhansera','Akiatonharónkwen','Tekarihoga','Thayendanegea','Sagoyewatha',
    'Skenandoah','Tewahongalahkon','Tyonajanegen','Atayataghlonghta',
)
NAME_POOLS={
    'Prussia':(('Friedrich','Karl','Johann','Heinrich','Otto','Wilhelm','Ernst','Ludwig'),
               ('von Arnsberg','Adler','Winterfeld','Bergmann','Seidel','Voss','Falkenberg','Brandt')),
    'Bourbon France':(('Étienne','Armand','Louis','Henri','Antoine','Charles','Pierre','Lucien'),
                      ('Morel','de Valcourt','Dupré','Beaumont','Deschamps','Lemaire','Vautrin','Marchand')),
    'Revolutionary Britain':(('Thomas','Edward','Elias','Samuel','William','James','Robert','Henry'),
                             ('Mercer','Harrow','Fenwick','Ashford','Bennett','Whitfield','Hale','Collier')),
    'Polish-Lithuanian Commonwealth':(('Jan','Michał','Kazimierz','Aleksander','Antoni','Tomasz','Stanisław','Józef'),
                                      ('Wysocki','Lipski','Dąbrowski','Zaleski','Kalinowski','Radzik','Sokołowski','Korsak')),
    'Haudenosaunee Confederacy':(HAUDENOSAUNEE_NAMES,()),
    'Generic':(('Johann','Edward','Henri','Anton','Thomas','Karl','Louis','Matthias'),
               ('Adler','Fenwick','Morel','Voss','Mercer','Weber','Beaumont','Keller')),
}


def compatible(kind):return tuple(s for s,definition in SPECIALIZATIONS.items() if kind in definition[1])


def generate(rng,kind,background='Generic',used_names=None,used_ids=None):
    names=used_names if used_names is not None else set();ids=used_ids if used_ids is not None else set()
    first,last=NAME_POOLS.get(background,NAME_POOLS['Generic'])
    if background=='Haudenosaunee Confederacy':
        available=tuple(name for name in first if name not in names)
        name=rng.choice(available or first)
        rank='';bio='Sandbox commander using a user-supplied Haudenosaunee name.'
    else:
        name=''
        for _ in range(20):
            name=f'{rng.choice(first)} {rng.choice(last)}'
            if name not in names:break
        rank=({'Prussia':'Major','Bourbon France':'Colonel','Revolutionary Britain':'Major',
               'Polish-Lithuanian Commonwealth':'Rotmistrz' if kind==U.CAVALRY else 'Major'}.get(background,'Major'))
        bio='Fictional regimental officer; no claim of historical identity.'
    if name in names:
        base=name
        for suffix in range(1,len(names)+2):
            name=f'{base} ({suffix})'
            if name not in names:break
    uid=f'cmd-{rng.getrandbits(96):024x}'
    for _ in range(64):
        if uid not in ids:break
        uid=f'cmd-{rng.getrandbits(96):024x}'
    if uid in ids:uid+=f'-{len(ids)}'
    officer=Commander(uid,name,background,rng.choice(tuple(P)),rng.choice(compatible(kind)),rank,bio)
    officer.validate(kind);names.add(name);ids.add(uid)
    return officer


@dataclass(frozen=True)
class CommanderTuning:
    drill_formation: float = .15
    drill_manoeuvre: float = .10
    drill_recovery: float = .10
    methodical_manoeuvre: float = .08
    stalwart_shock: float = .10
    firebrand_shock: float = .12
    firebrand_disorder: float = 3.
    pathfinder_forest: float = .20
    pathfinder_uphill: float = .10
    pathfinder_disruption: float = .15
    sharpshooter_accuracy: float = .12
    sharpshooter_reload: float = .08
    artillerist_scatter: float = .12
    artillerist_redeploy: float = .10
    inspirer_morale: float = .12
    inspirer_rally: float = .18
    pursuit_power: float = .12
    pursuit_disruption: float = .10
    defensive_resistance: float = .10
    defensive_advance: float = .05


TUNING=CommanderTuning()


from . import upgrades


def has(unit,specialty):return unit.commander is not None and unit.commander.specialization==specialty
def personality(unit,p):return unit.commander is not None and unit.commander.personality==p
def drill_strength(unit):return max(0.,min(1.,(unit.cohesion-40)/50)) if has(unit,S.DRILLMASTER) else 0.
def defending(unit):return unit.speed<.1 and not unit.transition_left and unit.order.kind in (O.HOLD,O.DEFEND,O.RESERVE)
def formation_factor(unit):return (1-TUNING.drill_formation*drill_strength(unit))*(upgrades.TUNING.swift_formation if upgrades.has(unit,"swift_reform") else 1.)
def manoeuvre_factor(unit):return (1-TUNING.drill_manoeuvre*drill_strength(unit))*(1-TUNING.methodical_manoeuvre if personality(unit,P.METHODICAL) else 1.)*(upgrades.TUNING.swift_manoeuvre if upgrades.has(unit,"swift_reform") else 1.)
def recovery_factor(unit):return min(1.8,min(1.25,1+TUNING.drill_recovery*drill_strength(unit)+(.10 if has(unit,S.DEFENSIVE) and defending(unit) else 0.))*(upgrades.TUNING.swift_recovery if upgrades.has(unit,"swift_reform") else 1.))
def shock_factor(unit):return (1-TUNING.stalwart_shock if personality(unit,P.STALWART) else 1.)*(upgrades.TUNING.defence if upgrades.has(unit,"steadfast_defence") and upgrades.prepared_defence(unit) else 1.)
def advance_factor(unit):return 1-TUNING.defensive_advance if has(unit,S.DEFENSIVE) and unit.order.kind in (O.ATTACK,O.ADVANCE,O.CHARGE) else 1.
def reload_factor(unit):return 1+TUNING.sharpshooter_reload if has(unit,S.SHARPSHOOTER) else 1.
def redeploy_factor(unit):return (1+TUNING.artillerist_redeploy if has(unit,S.ARTILLERIST) else 1.)*(upgrades.TUNING.mobile if upgrades.has(unit,"mobile_battery") else 1.)


def accuracy_factor(unit,transmission):
    if not has(unit,S.SHARPSHOOTER) or unit.speed>.1 or unit.cohesion<50 or unit.combat_state=='melee':return 1.
    return 1+TUNING.sharpshooter_accuracy*max(0.,min(1.,(transmission-.2)/.8))


def defence_factor(unit,attacker=None):
    if not defending(unit) or unit.state.value!='steady' or unit.cohesion<60:return 1.
    if attacker is not None and abs(angle_delta(unit.facing,angle_to(unit.pos,attacker.pos)))>1.0472:return 1.
    return max(.65,(1-TUNING.defensive_resistance if has(unit,S.DEFENSIVE) else 1.)*(upgrades.TUNING.defence if upgrades.has(unit,"steadfast_defence") and upgrades.prepared_defence(unit) else 1.))


def frontal_pursuit_penalty(unit,target):
    return .9 if has(unit,S.PURSUIT) and target.state.value=='steady' and abs(angle_delta(target.facing,angle_to(target.pos,unit.pos)))<1.0472 else 1.


def charge_shock_factor(unit,target,momentum,prepared=False):
    exposed=target.state.value!='steady' or target.cohesion<60 or abs(angle_delta(target.facing,angle_to(target.pos,unit.pos)))>1.0472
    base=1+TUNING.firebrand_shock if has(unit,S.FIREBRAND) and momentum>.25 and exposed and not prepared else 1.
    return min(1.8,base*upgrades.attack_shock(unit,target,momentum,prepared))


def charge_aftermath(battle,unit,momentum,boost):
    if boost>1 and upgrades.has(unit,"shock_commander"):
        battle.activate(unit,"Shock Commander: exposed enemy shaken by impact")
    if boost>1 and has(unit,S.FIREBRAND):
        unit.cohesion=max(0.,unit.cohesion-TUNING.firebrand_disorder*momentum)
        battle.activate(unit,f'{unit.commander.display_name}: Firebrand shock; formation disrupted')


def pursuit_factor(unit):return (1+TUNING.pursuit_power if has(unit,S.PURSUIT) else 1.)*(upgrades.TUNING.pursuit_power if upgrades.has(unit,"relentless_pursuit") else 1.)
def pursuit_cohesion_factor(unit):return 1-TUNING.pursuit_disruption if has(unit,S.PURSUIT) and unit.pursuit_id is not None else 1.
def pursuit_gap(unit,base):return base*1.10 if has(unit,S.PURSUIT) else base
def scatter_factor(unit):
    if unit.speed>=.1 or unit.limbered or unit.setup_left>0:return 1.
    base=1-TUNING.artillerist_scatter if has(unit,S.ARTILLERIST) else 1.
    if upgrades.has(unit,"calculated_fire") and unit.upgrade_stationary>=upgrades.TUNING.calculated_seconds:base*=upgrades.TUNING.calculated
    return max(.45,base)


@dataclass(frozen=True)
class Policy:
    commitment: float = 1.
    pursuit_distance: float = 200.
    disengage_seconds: float = 10.
    overmatch: float = 1.5
    firing_distance: float = .85


POLICIES={P.AGGRESSIVE:Policy(.65,320,18,2.4,.78),P.CAUTIOUS:Policy(1.35,120,6,1.15,.95),
          P.METHODICAL:Policy(1.2,180,12,1.65,.85),P.OPPORTUNISTIC:Policy(.5,280,12,1.6,.85),
          P.STALWART:Policy(1.,140,24,2.7,.85)}
DEFAULT_POLICY=Policy()
def policy(unit):return POLICIES[unit.commander.personality] if unit.commander else DEFAULT_POLICY


def effect_lines(unit):
    """Read-only, cheap situational information; no terrain or visibility rays."""
    if unit.commander is None:return ['No commander assigned']
    c=unit.commander;s=c.specialization
    if s==S.DRILLMASTER:active=f'Drill strength {drill_strength(unit):.0%}: formation, turns, recovery'
    elif s==S.FIREBRAND:active='Exposed charge shock +12%; extra post-impact disorder'
    elif s==S.PATHFINDER:active='Terrain benefits active' if unit.forest_cover>.05 or unit.ground_slope>.05 else 'Terrain benefits inactive on open level ground'
    elif s==S.SHARPSHOOTER:active='Stationary aim +up to 12% (clear sights)' if unit.speed<.1 and unit.cohesion>=50 and unit.combat_state!='melee' else 'Aim inactive: moving, melee or low cohesion'
    elif s==S.ARTILLERIST:active='Tighter aim active; limber/setup +10%' if scatter_factor(unit)<1 else 'Tighter aim inactive until stationary and deployed'
    elif s==S.INSPIRER:active='Morale aura active' if unit.effective and unit.state.value=='steady' and unit.morale>60 else 'Aura inactive while unsteady/routing/rallying'
    elif s==S.PURSUIT:active='Pursuit power +12%; prepared frontal combat -10%'
    else:active='Defensive benefits active' if defence_factor(unit)<1 else 'Defensive benefits inactive: must hold steady'
    lines=[c.display_name,f'{PERSONALITIES[c.personality][0]} | {SPECIALIZATIONS[s][0]}',active,SPECIALIZATIONS[s][3]]
    for key in c.upgrades:
        label=upgrades.REGISTRY[key].name
        if key=='calculated_fire':label+=f' ({min(6.,unit.upgrade_stationary):.1f}/6 s ready)'
        elif key=='steadfast_defence':label+=' (active)' if upgrades.prepared_defence(unit) else ' (requires steady defensive line)'
        elif key=='rolling_volley':label+=' (needs steady support, line, cohesion 70)'
        lines.append('+ '+label)
    return lines
