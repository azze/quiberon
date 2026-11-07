"""Small declarative roster and explicit trait rules; no live state or Pygame."""
from dataclasses import dataclass
from enum import Enum
from .unit_stats import UnitStats, UnitType, INFANTRY, CAVALRY, ARTILLERY
from .formations import Formation as F
from . import commanders


class Trait(str, Enum):
    DRILL = 'Prussian Drill'
    WOODLAND = 'Woodland Warfare'
    PRESTIGE = 'Royal Prestige'
    EXPLOIT = 'Exploit the Break'
    AIMED = 'Aimed Fire'
    RAPID = 'Rapid Redeployment'


@dataclass(frozen=True)
class UnitArchetype:
    id: str
    name: str
    faction: str
    stats: UnitStats
    symbol: str
    role: str
    strengths: str
    weaknesses: str
    ability: str = 'Standard battlefield drill.'
    trait: Trait | None = None
    formations: tuple[F, ...] = (F.LINE,F.COLUMN)
    default_formation: F = F.LINE
    initial_morale: float = 85.
    accuracy: float = 1.
    melee: float = 1.
    shock_resistance: float = 1.
    recovery: float = 1.
    forest_slow: float = 1.
    forest_loss: float = 1.
    slope_loss: float = 1.
    concealment: float = 1.
    forest_fire: float = 1.
    limber_seconds: float = 0.
    setup_seconds: float = 0.
    projectile_power: float = 1.
    accent: tuple[int,int,int] = (215,220,195)
    menu_name: str = ''
    charge_speed: float = 1.
    pursuit: float = 1.
    forest_vision: float = 1.
    forest_aim: float = 1.
    guns: int = 0
    melee_damage: float = 1.
    melee_shock: float = 1.
    forest_accuracy: float = 1.
    forest_melee_damage: float = 1.
    forest_melee_shock: float = 1.


_ROSTER = (
    UnitArchetype('infantry','Standard Line Infantry','Generic',INFANTRY,'I','line',
                  'Massed volleys; reliable centre.','Slow turns; vulnerable flanks.'),
    UnitArchetype('cavalry','Standard Cavalry','Generic',CAVALRY,'C','cavalry',
                  'Speed and shock charges.','Prepared infantry; woods.',formations=(F.LINE,)),
    UnitArchetype('artillery','Standard Field Artillery','Generic',ARTILLERY,'A','battery',
                  'Six-gun salvos; heavy penetrating cannonballs.','Wide shot scatter; slow relocation; weak crew melee.',formations=(F.LINE,),limber_seconds=3.,setup_seconds=8.,guns=6),
    UnitArchetype('prussian_line','Prussian Line Infantry','Prussia',INFANTRY,'P','line',
                  'Fast coordinated fire while cohesive.','Drill fades with disorder; poor in woods.',
                  'Cohesion 40–90 scales reload, formation and manoeuvre bonuses.',Trait.DRILL,
                  shock_resistance=.9,forest_slow=1.25,forest_loss=1.5,slope_loss=1.25,accent=(235,235,230)),
    UnitArchetype('haudenosaunee_skirmishers','Haudenosaunee Woodland Skirmishers','Haudenosaunee Confederacy',
                  UnitStats(strength=140,speed=3.6,turn_rate=.95,range=145,reload=11,discipline=1.),'W','skirmisher',
                  'Woodland fire, ambush melee, mobility and concealment.','Small volleys and weak melee on open ground; exposed cavalry.',
                  'Forest cover boosts aim and ambush melee; +20% base melee damage/shock. S: skirmish.',Trait.WOODLAND,
                  formations=(F.COLUMN,F.SKIRMISH),default_formation=F.SKIRMISH,accuracy=1.2,melee=.55,
                  forest_slow=.25,forest_loss=.18,slope_loss=.65,concealment=1.55,forest_fire=.25,forest_vision=.7,forest_aim=.5,accent=(135,220,160),menu_name='Woodland Skirmishers',melee_damage=1.2,melee_shock=1.2,
                  forest_accuracy=3.2,forest_melee_damage=4.5,forest_melee_shock=2.),
    UnitArchetype('royal_grenadiers','French Royal Grenadiers','Bourbon France',
                  UnitStats(strength=180,speed=2.5,turn_rate=.6,range=155,reload=12,discipline=1.2),'G','anchor',
                  'Melee and morale anchor.','Small, slow formation; concentrated artillery losses.',
                  'Steady Grenadiers give capped morale and rally support within 125 m.',Trait.PRESTIGE,
                  initial_morale=96,melee=1.5,shock_resistance=.78,recovery=1.25,accent=(250,225,120)),
    UnitArchetype('commonwealth_uhlans','Polish-Lithuanian Uhlans','Polish-Lithuanian Commonwealth',
                  UnitStats(UnitType.CAVALRY,80,9.,1.25,0,5,1.),'U','flanker',
                  'Fast flank charges and pursuit.','Fragile sustained melee; prepared infantry.',
                  'Speed-dependent charge bonus against wavering, routing or disordered enemies.',Trait.EXPLOIT,
                  formations=(F.LINE,),melee=.7,forest_slow=1.1,forest_loss=1.25,slope_loss=1.2,accent=(240,145,210),charge_speed=1.05,pursuit=1.25),
    UnitArchetype('revolutionary_rifles','British Revolutionary Riflemen','Revolutionary Britain',
                  UnitStats(strength=140,speed=3.,turn_rate=.8,range=235,reload=22,discipline=1.),'R','rifles',
                  'Long-range stationary aimed fire.','Slow reload; cavalry and close-range massed fire.',
                  'Stationary, cohesive, unobscured fire gains up to 35% accuracy.',Trait.AIMED,
                  formations=(F.LINE,F.COLUMN,F.SKIRMISH),default_formation=F.SKIRMISH,
                  accuracy=1.65,melee=.6,forest_slow=.8,forest_loss=.75,accent=(195,235,110)),
    UnitArchetype('french_horse_artillery','French Horse Artillery','Bourbon France',
                  UnitStats(UnitType.ARTILLERY,40,3.8,.7,360,17,1.),'H','mobile_battery',
                  'Four-gun salvos; rapid support and redeployment.','Wide scatter; lighter shot; weak crew melee.',
                  '1 s limber / 3 s setup versus field artillery 3 s / 8 s.',Trait.RAPID,
                  formations=(F.LINE,),limber_seconds=1.,setup_seconds=3.,projectile_power=.65,accent=(245,185,100),guns=4),
)
ARCHETYPES = {a.id:a for a in _ROSTER}
GENERIC_IDS = {UnitType.INFANTRY:'infantry',UnitType.CAVALRY:'cavalry',UnitType.ARTILLERY:'artillery'}


def drill(unit):
    return max(0.,min(1.,(unit.cohesion-40)/50)) if unit.archetype.trait==Trait.DRILL else 0.


def reload_time(unit):
    return max(.5,unit.stats.reload*(1-.25*drill(unit))*(1+unit.fatigue*.003)*commanders.reload_factor(unit))


def formation_time(unit,seconds): return max(seconds*(.4 if commanders.upgrades.has(unit,"swift_reform") else .5),seconds*(1-.4*drill(unit))*commanders.formation_factor(unit))
def manoeuvre_factor(unit): return max(.4,(1-.5*drill(unit))*commanders.manoeuvre_factor(unit))


def aimed_bonus(unit, transmission):
    if unit.archetype.trait!=Trait.AIMED or unit.speed>.1 or unit.combat_state=='melee': return 1.
    cohesion=max(0.,min(1.,(unit.cohesion-40)/40))
    clarity=max(0.,min(1.,(transmission-.35)/.55))
    return 1+.35*cohesion*clarity


def exploit_bonus(unit,target,prepared):
    if unit.archetype.trait!=Trait.EXPLOIT or prepared or unit.speed<=3: return 1.
    broken=target.state.value in ('wavering','routing') or target.cohesion<40
    return 1.65 if broken else 1.
