"""Shared destination-and-facing gesture and read-only footprint preview."""
from dataclasses import dataclass
import math
import pygame
from simulation.geometry import Vec, angle_to, corners, direction
from simulation.formations import PROFILES
from simulation.regiment import UnitType


@dataclass
class FacingGesture:
    unit_id: int
    destination: Vec
    start_screen: tuple[float, float]
    default_facing: float
    facing: float | None = None

    def update(self, screen_pos, camera):
        # Screen-space deadzone makes click tolerance independent of zoom.
        # Once dragged, returning near the anchor retains the last heading.
        if math.hypot(screen_pos[0]-self.start_screen[0], screen_pos[1]-self.start_screen[1]) >= 8:
            point = camera.screen_to_world(screen_pos)
            if (point-self.destination).length() > 1e-6:
                self.facing = angle_to(self.destination, point)

    @property
    def preview_facing(self):
        return self.default_facing if self.facing is None else self.facing


def move_destination(unit, point, rules):
    # Leave room for the entire formation throughout its final turn. World-space
    # sizes/ranges never depend on zoom. Deployment uses exact zone validation.
    sizes = [(unit.width,unit.depth)]
    if unit.stats.kind == UnitType.INFANTRY:
        # A formation command can still be queued while paused or during a drag.
        sizes.extend(profile[:2] for profile in PROFILES.values())
    radius = max(math.hypot(w,d) for w,d in sizes)/2 + 1
    return Vec(max(radius,min(rules.width-radius,point.x)),
               max(radius,min(rules.height-radius,point.y)))


def draw_ghost(screen, camera, unit, pos, facing, color):
    points = [camera.world_to_screen(p) for p in corners(pos,facing,unit.width,unit.depth)]
    bounds = pygame.Rect(math.floor(min(p[0] for p in points))-2,
                         math.floor(min(p[1] for p in points))-2,
                         math.ceil(max(p[0] for p in points)-min(p[0] for p in points))+5,
                         math.ceil(max(p[1] for p in points)-min(p[1] for p in points))+5)
    # Allocate only the visible footprint, never another full-screen layer.
    bounds = bounds.clip(screen.get_rect())
    if bounds.width and bounds.height:
        fill = pygame.Surface(bounds.size,pygame.SRCALPHA)
        pygame.draw.polygon(fill,(*color,48),[(x-bounds.x,y-bounds.y) for x,y in points])
        screen.blit(fill,bounds)
    pygame.draw.polygon(screen,color,points,2)
    forward,side = direction(facing),direction(facing+math.pi/2)
    tip = pos+forward*(unit.depth/2+22)
    pygame.draw.line(screen,color,camera.world_to_screen(pos),camera.world_to_screen(tip),2)
    pygame.draw.lines(screen,color,False,[camera.world_to_screen(tip-forward*7+side*5),
                                        camera.world_to_screen(tip),
                                        camera.world_to_screen(tip-forward*7-side*5)],2)
