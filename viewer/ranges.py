"""Geometric weapon range and arc, deliberately independent of visibility."""
import pygame
from simulation.geometry import contains, direction

SELECTED_RANGE = (240,223,129)
FRIENDLY_RANGE = (125,215,255)
ENEMY_RANGE = (255,145,120)


def hovered_unit(battle,camera,poses,screen_pos):
    if not (0<=screen_pos[0]<camera.width and 36<=screen_pos[1]<camera.height-150): return None
    point=camera.screen_to_world(screen_pos)
    return next((u for u in reversed(battle.units) if u.active and
                 contains(point,poses[u.id].pos,poses[u.id].facing,poses[u.id].width,poses[u.id].depth)),None)


def draw_range(screen,camera,unit,pose,half_arc,color):
    if not unit.stats.range: return
    centre=camera.world_to_screen(pose.pos)
    radius=unit.stats.range*camera.zoom
    pygame.draw.circle(screen,color,centre,max(1,round(radius)),1)
    arc=[camera.world_to_screen(pose.pos+direction(pose.facing-half_arc+i*half_arc/24)*unit.stats.range) for i in range(49)]
    pygame.draw.lines(screen,color,False,arc,3)
    for edge in (arc[0],arc[-1]): pygame.draw.line(screen,color,centre,edge,1)


def draw_ranges(renderer,battle,controls):
    screen,camera=renderer.screen,renderer.camera
    cursor=pygame.mouse.get_pos()
    hovered=hovered_unit(battle,camera,renderer.unit_poses,cursor)
    renderer.hovered_id=hovered.id if hovered else None
    selected=battle.unit(controls.selected)
    old_clip=screen.get_clip()
    screen.set_clip(pygame.Rect(0,36,camera.width,max(0,camera.height-186)))
    candidates=[(selected,SELECTED_RANGE)]
    if hovered is not selected: candidates.append((hovered,FRIENDLY_RANGE if hovered and hovered.army==0 else ENEMY_RANGE))
    for unit,color in candidates:
        if unit is None or not unit.active: continue
        draw_range(screen,camera,unit,renderer.unit_poses[unit.id],battle.rules.firing_half_arc,color)
    screen.set_clip(old_clip)
    if hovered:
        text=f'{hovered.archetype.menu_name or hovered.archetype.name}: {hovered.stats.range:g} m' if hovered.stats.range else f'{hovered.archetype.name}: melee only'
        label=renderer.hud.font.render(text,True,(245,240,210))
        x=max(4,min(cursor[0]+16,screen.get_width()-label.get_width()-12))
        y=max(38,min(cursor[1]+22,screen.get_height()-175))
        pygame.draw.rect(screen,(22,29,29),(x-4,y-3,label.get_width()+8,label.get_height()+6))
        screen.blit(label,(x,y))
