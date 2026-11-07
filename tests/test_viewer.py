import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
from scenarios.movement_test import create
from viewer.camera import Camera
from viewer.controls import Controls
from viewer.renderer import Renderer
from simulation.formations import Formation
from simulation.orders import OrderKind


def test_input_commands_and_read_only_rendering():
    pygame.init()
    try:
        screen=pygame.display.set_mode((1280,800))
        b=create(); c=Camera(height=800); controls=Controls()
        pos=c.world_to_screen(b.units[0].pos)
        controls.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=pos),b,c)
        assert controls.selected==0
        controls.handle(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_c),b,c)
        controls.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=3,pos=(600,300)),b,c)
        controls.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,button=3,pos=(600,300)),b,c)
        assert len(b.commands)==2
        b.step()
        assert b.units[0].next_formation==Formation.COLUMN
        assert b.units[0].order.kind==OrderKind.MOVE
        before=repr(b.units),repr(b.effects),repr(b.events),b.rng.getstate()
        r=Renderer(screen,c)
        r.draw(b,controls)
        controls.debug=True
        r.draw(b,controls)
        assert before==(repr(b.units),repr(b.effects),repr(b.events),b.rng.getstate())
    finally: pygame.quit()


def test_frontage_smoke_renders_without_changing_simulation():
    import math
    from simulation.battle import Battle
    from simulation.regiment import Regiment
    from simulation.geometry import Vec, direction
    from simulation.combat import fire
    pygame.init()
    try:
        screen=pygame.display.set_mode((1280,800))
        shooter=Regiment(0,'volley',0,Vec(350,300))
        target=Regiment(1,'target',1,Vec(450,300),math.pi)
        battle=Battle([shooter,target])
        fire(battle,shooter,target)
        effect=battle.effects[0]
        assert effect.kind=='smoke' and effect.width==shooter.width
        assert effect.pos==shooter.pos+direction(shooter.facing)*(shooter.depth/2+2)
        # Smoke keeps its original location after the shooter moves away.
        shooter.pos=Vec(300,300)
        before=repr(battle.units),repr(battle.effects),battle.rng.getstate()
        renderer=Renderer(screen,Camera(height=800))
        controls=Controls()
        for tick in (0,8,20):
            battle.tick=tick
            renderer.draw(battle,controls)
        assert before==(repr(battle.units),repr(battle.effects),battle.rng.getstate())
    finally:
        pygame.quit()


def test_selected_target_marker_without_debug_is_read_only():
    from simulation.battle import Battle
    from simulation.regiment import Regiment
    from simulation.geometry import Vec
    from simulation.orders import Order,OrderKind
    from viewer.targeting import TARGET_COLOR,ORDER_COLOR
    pygame.init()
    try:
        screen=pygame.display.set_mode((1280,800))
        shooter=Regiment(0,'Selected',0,Vec(250,300),target_id=1,order=Order(OrderKind.ATTACK,target_id=2))
        actual=Regiment(1,'Current target',1,Vec(500,300))
        requested=Regiment(2,'Ordered target',1,Vec(650,400))
        battle=Battle([shooter,actual,requested])
        controls=Controls(); controls.selected=0
        assert not controls.debug
        camera=Camera(height=800); renderer=Renderer(screen,camera)
        before=repr(battle.units),battle.rng.getstate()
        renderer.draw(battle,controls)
        def has_color(unit,color):
            x,y=camera.world_to_screen(unit.pos)
            top=min(camera.world_to_screen(p)[1] for p in unit.footprint)
            return any(screen.get_at((round(x)+dx,round(top)-18+dy))[:3]==color
                       for dx in range(-19,20) for dy in range(-19,20))
        assert has_color(actual,TARGET_COLOR)
        assert has_color(requested,ORDER_COLOR)
        assert before==(repr(battle.units),battle.rng.getstate())
        controls.selected=None
        renderer.draw(battle,controls)
        assert not has_color(actual,TARGET_COLOR) and not has_color(requested,ORDER_COLOR)
        controls.selected=0; actual.strength=0; requested.withdrawn=True
        renderer.draw(battle,controls)
        assert not has_color(actual,TARGET_COLOR) and not has_color(requested,ORDER_COLOR)
    finally: pygame.quit()
