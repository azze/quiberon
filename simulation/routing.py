"""Deterministic local escape steering; no orders, pathfinder or extra RNG."""
import math
from .geometry import Vec,direction,angle_to,segment_rect
from .unit_stats import UnitType


def destination(battle,unit):
    rules=battle.rules
    home=Vec(-1 if unit.army==0 else 1,0)
    if unit.rout_heading is None:
        unit.transition_left=0.;unit.next_formation=None
        unit.settling_goal=None;unit.settling_facing=None
    if unit.rout_heading is None or battle.time>=unit.rout_next_plan:
        threats=[]
        for enemy in battle.units:
            if enemy.army==unit.army or not enemy.effective:continue
            distance=(enemy.pos-unit.pos).length()
            if distance>rules.rout_threat_radius:continue
            # Contact is dangerous even in vegetation; otherwise use perception.
            if distance>60 and not battle.perceives(unit,enemy):continue
            weight=(.5+.5*min(1.,enemy.strength/max(1,enemy.stats.strength)))
            if enemy.stats.kind==UnitType.CAVALRY:weight*=1.5
            threats.append((enemy,distance,weight))
        heading=unit.rout_heading or home
        if threats:
            away=Vec(0,0)
            for enemy,distance,weight in threats:
                delta=(unit.pos-enemy.pos).normalized()
                away+=delta*(weight/max(10.,distance)**2)
            if away.length()<1e-9:
                nearest=min(threats,key=lambda item:(item[1],item[0].id))[0]
                away=(unit.pos-nearest.pos).normalized()
                if away.length()<1e-9:away=home
            angle=angle_to(Vec(0,0),away)
            base=sum(weight/max(8.,distance) for _,distance,weight in threats)
            candidates=[]
            for offset in (0,-math.pi/4,math.pi/4,-math.pi/2,math.pi/2,-3*math.pi/4,3*math.pi/4,math.pi):
                step=direction(angle+offset)
                # Evaluate the full escape ray, including an exit through the
                # field edge. Movement still clips the real footprint to bounds.
                point=unit.pos+step*rules.rout_lookahead
                middle=(unit.pos+point)*.5
                risk=sum(weight*(1/max(8.,(point-enemy.pos).length())+
                         .5/max(8.,(middle-enemy.pos).length())) for enemy,_,weight in threats)
                # Reject paths through another enemy, but allow escape from an
                # existing contact/overlap rather than penalizing every exit.
                blocked=any((entry:=segment_rect(unit.pos,point,enemy)) is not None and entry>1e-6
                            for enemy,_,_ in threats)
                persistence=.08*step.dot(unit.rout_heading) if unit.rout_heading is not None else 0.
                score=(1.5*base-risk)/base+persistence+.02*step.dot(home)-(2 if blocked else 0)
                candidates.append((score,step))
            heading=max(candidates,key=lambda item:item[0])[1]
        # Keep an established escape direction after danger drops out of range;
        # immediately turning home would lead straight back into the pursuer.
        unit.rout_heading=heading
        unit.rout_next_plan=battle.time+rules.rout_plan_seconds
        unit.ai_state='routing: escape nearby danger' if threats else 'routing: continue escape'
    heading=unit.rout_heading
    corners=unit.footprint;margin=rules.rout_exit_margin
    exiting=(heading.x<-.25 and min(p.x for p in corners)<=margin or
             heading.x>.25 and max(p.x for p in corners)>=rules.width-margin or
             heading.y<-.25 and min(p.y for p in corners)<=margin or
             heading.y>.25 and max(p.y for p in corners)>=rules.height-margin)
    if exiting:
        unit.withdrawn=True
        battle.log('withdraw',f'{unit.name} escaped the battlefield while routing',unit.id)
        return None
    return unit.pos+heading*rules.rout_lookahead
