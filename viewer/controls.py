"""Input emits simulation commands; camera and UI state remain viewer-owned."""
import pygame
from simulation.geometry import Vec, contains, angle_to
from simulation.orders import Command, Order, OrderKind
from simulation.formations import Formation
from simulation.regiment import UnitType
from .placement import FacingGesture, move_destination
from .command_bar import buttons,can_order

class Controls:
    def __init__(self):
        self.campaign = False
        self.selected = None
        self.paused = False
        self.speed = 1
        self.actual_speed = None
        self.slow = False
        self.backlog=0.
        self.debug = False
        self.contours = True
        self.running = True
        self.move_gesture = None
        self.move_kind = OrderKind.MOVE
        self.gesture_button = 3
        self.pending_order = None
        self.pending_unit = None

    def cancel_command(self):
        self.move_gesture=None
        self.pending_order=None
        self.pending_unit=None

    def action(self,key,battle):
        unit=battle.unit(self.selected)
        if battle.result is not None or unit is None or not unit.effective or unit.army!=0:return
        if key.startswith('formation:'):
            formation=Formation(key.split(':')[1])
            if unit.stats.kind==UnitType.INFANTRY and formation in unit.archetype.formations and not unit.transition_left:
                self.cancel_command()
                battle.issue(Command(unit.id,formation=formation))
        elif key.startswith('order:'):
            kind=OrderKind(key.split(':')[1])
            if not can_order(unit,kind):return
            self.cancel_command()
            if kind in (OrderKind.MOVE,OrderKind.ADVANCE,OrderKind.ATTACK,OrderKind.CHARGE,OrderKind.DEFEND):
                self.pending_order=kind;self.pending_unit=unit.id
            else:battle.issue(Command(unit.id,Order(kind)))

    def begin_move(self,unit,point,pos,kind,button,battle):
        self.cancel_command()
        point=move_destination(unit,point,battle.rules)
        self.move_kind=kind;self.gesture_button=button
        self.move_gesture=FacingGesture(unit.id,point,pos,angle_to(unit.pos,point) if (point-unit.pos).length()>=1 else unit.facing)

    def handle(self, event, battle, camera, poses=None):
        if self.pending_order is not None:
            unit=battle.unit(self.pending_unit)
            if self.selected!=self.pending_unit or unit is None or not unit.effective or battle.result is not None:self.cancel_command()
        if event.type == pygame.QUIT:
            self.running = False;self.cancel_command()
        if event.type == pygame.WINDOWFOCUSLOST:self.cancel_command()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.move_gesture is not None or self.pending_order is not None:self.cancel_command()
                elif self.selected is not None:self.selected=None
                else:self.running=False
            if event.key == pygame.K_SPACE:self.paused=not self.paused
            if event.key == pygame.K_F2:self.contours=not self.contours
            if event.key == pygame.K_F3:self.debug=not self.debug
            if event.key in (pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4):self.speed={pygame.K_1:1,pygame.K_2:2,pygame.K_3:4,pygame.K_4:10}[event.key]
            formations={pygame.K_l:Formation.LINE,pygame.K_c:Formation.COLUMN,pygame.K_k:Formation.SKIRMISH}
            if event.key in formations:self.action('formation:'+formations[event.key].value,battle)
            orders={pygame.K_h:OrderKind.HOLD,pygame.K_r:OrderKind.RESERVE,pygame.K_w:OrderKind.WITHDRAW,pygame.K_s:OrderKind.SKIRMISH,
                    pygame.K_m:OrderKind.MOVE,pygame.K_a:OrderKind.ADVANCE,pygame.K_t:OrderKind.ATTACK,pygame.K_d:OrderKind.DEFEND}
            if event.key in orders:self.action('order:'+orders[event.key].value,battle)
            if event.key==pygame.K_b:
                unit=battle.unit(self.selected)
                if unit and unit.army==0 and unit.effective and unit.stats.kind!=UnitType.ARTILLERY and battle.result is None:
                    targets=(battle.unit(uid) for uid in (unit.order.target_id,unit.target_id))
                    target=next((t for t in targets if t and t.active and t.army!=unit.army),None)
                    if target:
                        self.cancel_command();battle.issue(Command(unit.id,Order(OrderKind.CHARGE,target_id=target.id)))
                    else:self.action('order:charge',battle)
        if event.type == pygame.MOUSEWHEEL:camera.zoom_at(pygame.mouse.get_pos(),1.15**event.y)
        if event.type == pygame.MOUSEMOTION and self.move_gesture is not None:self.move_gesture.update(event.pos,camera)
        if event.type == pygame.MOUSEBUTTONUP and event.button==self.gesture_button and self.move_gesture is not None:
            gesture=self.move_gesture;self.move_gesture=None
            unit=battle.unit(gesture.unit_id)
            if (battle.result is None and unit and unit.effective and self.selected==unit.id and
                    0<=event.pos[0]<camera.width and 0<=event.pos[1]<camera.height-150):
                gesture.update(event.pos,camera)
                battle.issue(Command(unit.id,Order(self.move_kind,gesture.destination,facing=gesture.facing)))
        if event.type != pygame.MOUSEBUTTONDOWN:return
        if event.pos[1]>=camera.height-150:
            if event.button==1:
                hit=next((b for b in buttons(camera.width,camera.height,battle,self) if b.rect.collidepoint(event.pos)),None)
                if hit and hit.enabled:self.action(hit.key,battle)
            return # UI never selects units or sends world orders through the panel.
        if not (0<=event.pos[0]<camera.width and 0<=event.pos[1]<camera.height-150):return
        point=camera.screen_to_world(event.pos)
        hit=None
        for u in reversed(battle.units):
            pose=poses.get(u.id,u) if poses else u
            if u.active and contains(point,pose.pos,pose.facing,pose.width,pose.depth):hit=u;break
        if event.button==1 and self.pending_order is not None:
            unit=battle.unit(self.pending_unit);kind=self.pending_order
            if kind in (OrderKind.ATTACK,OrderKind.CHARGE):
                if hit and hit.army!=unit.army:
                    self.cancel_command();battle.issue(Command(unit.id,Order(kind,target_id=hit.id)))
            elif kind==OrderKind.DEFEND:
                self.cancel_command();battle.issue(Command(unit.id,Order(kind,move_destination(unit,point,battle.rules))))
            else:self.begin_move(unit,point,event.pos,kind,1,battle)
            return
        if event.button==1:
            self.cancel_command();self.selected=hit.id if hit and hit.army==0 else None
        if event.button==3 and self.selected is not None and battle.result is None:
            self.cancel_command();unit=battle.unit(self.selected)
            if unit is None or not unit.effective:return
            if hit and hit.army!=unit.army:
                kind=OrderKind.CHARGE if pygame.key.get_mods() & pygame.KMOD_CTRL and unit.stats.kind!=UnitType.ARTILLERY else OrderKind.ATTACK
                battle.issue(Command(unit.id,Order(kind,target_id=hit.id)))
            else:
                kind=OrderKind.ADVANCE if pygame.key.get_mods() & pygame.KMOD_SHIFT else OrderKind.MOVE
                self.begin_move(unit,point,event.pos,kind,3,battle)

    def pan(self, camera, seconds):
        keys = pygame.key.get_pressed()
        dx = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
        dy = keys[pygame.K_DOWN] - keys[pygame.K_UP]
        camera.center += Vec(dx,dy) * (450 * seconds / camera.zoom)
