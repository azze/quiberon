"""Metres; angles are radians, clockwise on the screen's downward y axis."""
from dataclasses import dataclass
from functools import lru_cache
import math

@dataclass(frozen=True)
class Vec:
    x: float
    y: float
    def __add__(self, other): return Vec(self.x + other.x, self.y + other.y)
    def __sub__(self, other): return Vec(self.x - other.x, self.y - other.y)
    def __mul__(self, scalar): return Vec(self.x * scalar, self.y * scalar)
    def dot(self, other): return self.x * other.x + self.y * other.y
    def length(self): return math.hypot(self.x, self.y)
    def normalized(self): return self * (1 / self.length()) if self.length() else Vec(0, 0)

@lru_cache(maxsize=4096)
def direction(angle): return Vec(math.cos(angle), math.sin(angle))
def angle_to(a, b): return math.atan2(b.y - a.y, b.x - a.x)
def angle_delta(a, b): return (b - a + math.pi) % math.tau - math.pi

@lru_cache(maxsize=8192)
def _corner_tuple(pos, facing, width, depth):
    forward, side = direction(facing), direction(facing + math.pi / 2)
    return tuple(pos + forward * (d * depth / 2) + side * (w * width / 2)
            for d, w in [(1, 1), (1, -1), (-1, -1), (-1, 1)])

def corners(pos, facing, width, depth):
    # Callers get their own list; immutable cached vectors cannot be corrupted.
    return list(_corner_tuple(pos,facing,width,depth))

@lru_cache(maxsize=64)
def half_diagonal(width,depth): return math.hypot(width,depth)/2

def contains(point, pos, facing, width, depth):
    offset = point - pos
    return (abs(offset.dot(direction(facing))) <= depth / 2 and
            abs(offset.dot(direction(facing + math.pi / 2))) <= width / 2)

def separation(a, b):
    """SAT minimum translation vector moving rectangle a out of b, or None."""
    dx,dy=b.pos.x-a.pos.x,b.pos.y-a.pos.y
    radius=half_diagonal(a.width,a.depth)+half_diagonal(b.width,b.depth)
    # Broad phase is conservative, including floating-point safety at tangency.
    if dx*dx+dy*dy>radius*radius+1e-8: return None
    ca, cb = a.footprint, b.footprint
    best, vector = float('inf'), None
    for axis in [direction(a.facing), direction(a.facing + math.pi / 2),
                 direction(b.facing), direction(b.facing + math.pi / 2)]:
        pa, pb = [p.dot(axis) for p in ca], [p.dot(axis) for p in cb]
        overlap = min(max(pa), max(pb)) - max(min(pa), min(pb))
        if overlap <= 0: return None
        if overlap < best:
            best = overlap
            vector = axis * ((-1 if (b.pos - a.pos).dot(axis) >= 0 else 1) * overlap)
    return vector

def touching(a, b, margin=.75):
    """SAT contact tolerance bridges the small gap left by enemy separation."""
    radius=half_diagonal(a.width,a.depth)+half_diagonal(b.width,b.depth)+margin*2
    if (a.pos-b.pos).length()>radius: return False
    delta=b.pos-a.pos
    for axis in (direction(a.facing),direction(a.facing+math.pi/2),direction(b.facing),direction(b.facing+math.pi/2)):
        extent=lambda u: abs(direction(u.facing).dot(axis))*u.depth/2+abs(direction(u.facing+math.pi/2).dot(axis))*u.width/2
        if abs(delta.dot(axis))>extent(a)+extent(b)+margin: return False
    return True

def segment_rect(start, end, unit, padding=0.):
    """Slab intersection; includes fast projectiles that cross between ticks."""
    delta, offset = end - start, start - unit.pos
    lo, hi = 0., 1.
    for axis, half in [(direction(unit.facing), unit.depth / 2),
                       (direction(unit.facing + math.pi / 2), unit.width / 2)]:
        p, v = offset.dot(axis), delta.dot(axis)
        if abs(v) < 1e-9:
            if abs(p) > half + padding: return None
        else:
            t1, t2 = sorted(((-half - padding - p) / v, (half + padding - p) / v))
            lo, hi = max(lo, t1), min(hi, t2)
            if lo > hi: return None
    return lo


def cross(a: Vec, b: Vec) -> float:
    return a.x * b.y - a.y * b.x


def polygon_area(points: list[Vec]) -> float:
    return abs(sum(cross(a, b) for a, b in zip(points, points[1:] + points[:1]))) / 2


def intersection_area(a, b) -> float:
    """Exact convex rectangle intersection by half-plane polygon clipping."""
    polygon = a.footprint
    clip = b.footprint
    winding = 1 if sum(cross(p, q) for p, q in zip(clip, clip[1:] + clip[:1])) > 0 else -1
    for start, end in zip(clip, clip[1:] + clip[:1]):
        if not polygon: return 0.
        edge = end - start
        output = []
        previous = polygon[-1]
        d_previous = winding * cross(edge, previous - start)
        for current in polygon:
            d_current = winding * cross(edge, current - start)
            if (d_current >= 0) != (d_previous >= 0):
                t = d_previous / (d_previous - d_current)
                output.append(previous + (current - previous) * t)
            if d_current >= 0: output.append(current)
            previous, d_previous = current, d_current
        polygon = output
    return polygon_area(polygon)
