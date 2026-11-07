"""Personality decisions at existing AI seams; no independent tactical planner."""
import math
from . import commanders as cmd
from .geometry import Vec,angle_delta,angle_to
from .orders import Order,OrderKind as O
from .unit_stats import UnitType as U


def autonomous(battle,u):return u.commander is not None and u.army in battle.ai_armies and not u.player_order
def vulnerable(enemy):return enemy.state.value in ('wavering','routing') or enemy.cohesion<40


def note(battle,u,message):
    battle.activate(u,f'{u.commander.display_name}: {message}')


def retreat(battle,u,enemy,reason):
    away=(u.pos-enemy.pos).normalized()
    if away.length()<.1:away=Vec(-1 if u.army==0 else 1,0)
    point=u.pos+away*40
    radius=math.hypot(u.width,u.depth)/2+1
    u.commander_retreat_goal=Vec(max(radius,min(battle.rules.width-radius,point.x)),max(radius,min(battle.rules.height-radius,point.y)))
    u.commander_retreat_until=battle.time+10
    u.commander_next_retreat=battle.time+40
    u.order=Order(O.MOVE,u.commander_retreat_goal)
    u.ai_state=f'commander: {reason}'
    note(battle,u,reason)


def plan(battle,u,enemies,nearest):
    """Return True when a bounded retreat/preparation overrides this AI plan."""
    if not autonomous(battle,u):return False
    if battle.time<u.commander_retreat_until:
        u.order=Order(O.MOVE,u.commander_retreat_goal)
        u.ai_state='commander: committed local disengagement'
        return True
    p=u.commander.personality
    if p==cmd.P.METHODICAL and u.cohesion<55 and u.combat_state!='melee':
        if battle.time>=u.commander_next_reform:
            u.commander_reform_until=battle.time+8;u.commander_next_reform=battle.time+28
            note(battle,u,'briefly reforming before attack')
        if battle.time<u.commander_reform_until:
            u.order=Order(O.HOLD);u.ai_state='commander: methodical preparation (bounded)'
            return True
    policy=cmd.policy(u)
    distance=(nearest.pos-u.pos).length()
    own=u.strength*u.archetype.melee*(.3+u.cohesion/100)
    hostile=nearest.strength*nearest.archetype.melee*(.3+nearest.cohesion/100)
    if battle.terrain.forests:
        from .combat import forest_melee_factors
        formation,power,_=forest_melee_factors(battle,u);own*=formation*power*u.archetype.melee_damage
        formation,power,_=forest_melee_factors(battle,nearest);hostile*=formation*power*nearest.archetype.melee_damage
    in_melee=u.commander_melee_since is not None and battle.time-u.commander_melee_since>=policy.disengage_seconds
    threatened=p==cmd.P.CAUTIOUS and distance<90
    if (u.stats.kind!=U.ARTILLERY and not vulnerable(nearest) and battle.time>=u.commander_next_retreat and
        (in_melee or threatened) and hostile>own*policy.overmatch):
        retreat(battle,u,nearest,'preserving the regiment from an unfavourable fight')
        return True
    return False


def select_target(battle,u,enemies,nearest):
    if not autonomous(battle,u) or u.commander.personality!=cmd.P.OPPORTUNISTIC:return nearest
    current=next((e for e in enemies if e.id==u.commander_target_id),None)
    if current is not None and battle.time<u.commander_decision_until:return current
    def score(e):
        flank=abs(angle_delta(e.facing,angle_to(e.pos,u.pos)))
        return (e.pos-u.pos).length()*.12+e.cohesion*.4-(80 if vulnerable(e) else 0)-(20 if flank>1.5 else 0)
    best=min(enemies,key=lambda e:(score(e),e.id))
    if current is not None and score(best)>score(current)-15:best=current
    if best.id!=u.commander_target_id:
        u.commander_target_id=best.id;u.commander_decision_until=battle.time+10
        if u.stats.kind==U.CAVALRY:
            u.cavalry_target_id=best.id;u.cavalry_waypoint=None
            u.order=Order(O.ATTACK,target_id=best.id)
        if vulnerable(best):note(battle,u,f'exploiting vulnerable {best.name}')
    return best


def pursuit_limit(battle,u,target):
    """Only autonomous close pursuit is limited; explicit attacks remain literal."""
    if not autonomous(battle,u) or target.state.value!='routing':return False
    if u.cavalry_state.value!='pursuit':return False
    if u.commander_pursuit_target!=target.id:
        u.commander_pursuit_target=target.id;u.commander_pursuit_origin=u.pos
        note(battle,u,'committing to pursuit')
    limit=cmd.policy(u).pursuit_distance*(1.15 if cmd.has(u,cmd.S.FIREBRAND) else 1.)
    if (u.pos-u.commander_pursuit_origin).length()<=limit:return False
    retreat(battle,u,target,'breaking off extended pursuit')
    u.commander_avoid_target=target.id;u.commander_avoid_until=battle.time+30
    u.commander_pursuit_origin=None;u.commander_pursuit_target=None
    return True
