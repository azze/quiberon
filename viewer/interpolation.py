"""Viewer-owned copies of previous poses; no writes to authoritative entities."""
from dataclasses import dataclass
from simulation.geometry import Vec, angle_delta, corners

@dataclass(frozen=True)
class UnitPose:
    pos: Vec
    facing: float
    width: float
    depth: float

    @property
    def footprint(self): return corners(self.pos,self.facing,self.width,self.depth)

@dataclass(frozen=True)
class BallPose:
    pos: Vec
    height: float
    bounces: int

class MotionFrame:
    def __init__(self,battle):
        self.capture(battle)

    def capture(self,battle):
        self.units={u.id:UnitPose(u.pos,u.facing,u.width,u.depth) for u in battle.units if u.active}
        # Retain the object to prevent recycled Python IDs matching a new ball.
        self.balls={id(p):(p,BallPose(p.pos,p.height,p.bounces)) for p in battle.projectiles}

    def unit_pose(self,unit,alpha):
        previous=self.units.get(unit.id)
        if previous is None or alpha>=1: return UnitPose(unit.pos,unit.facing,unit.width,unit.depth)
        alpha=max(0.,alpha)
        pos=previous.pos+(unit.pos-previous.pos)*alpha
        facing=previous.facing+angle_delta(previous.facing,unit.facing)*alpha
        return UnitPose(pos,facing,unit.width,unit.depth)

    def ball_pose(self,ball,alpha):
        previous=self.balls.get(id(ball))
        if previous is None or previous[0] is not ball or alpha>=1 or previous[1].bounces!=ball.bounces:
            return BallPose(ball.pos,ball.height,ball.bounces)
        pose=previous[1]; alpha=max(0.,alpha)
        return BallPose(pose.pos+(ball.pos-pose.pos)*alpha,pose.height+(ball.height-pose.height)*alpha,ball.bounces)
