"""Read-only drawing of simulation state. Effects are deterministic simulation records."""
import math
from dataclasses import replace
import pygame
from simulation.geometry import Vec, direction
from simulation.formations import Formation
from .hud import HUD
from .terrain import TerrainPainter
from .targeting import current_target, ordered_target, TARGET_COLOR, ORDER_COLOR
from .placement import draw_ghost
from .ranges import draw_ranges

class Renderer:
    def __init__(self, screen, camera):
        self.screen, self.camera = screen, camera
        self.hud = HUD()
        self.terrain_painter = TerrainPainter()
        self.unit_poses = {}
        self._smoke_surface = None
        self.hovered_id = None
    def draw(self, battle, controls, fps=0, present=True, zones=None, motion=None, alpha=1.):
        s,c = self.screen,self.camera
        self.unit_poses={u.id:motion.unit_pose(u,alpha) if motion else u for u in battle.units if u.active}
        s.fill((40,59,41))
        width, height = battle.rules.width, battle.rules.height
        polygon = [c.world_to_screen(Vec(x,y)) for x,y in [(0,0),(width,0),(width,height),(0,height)]]
        pygame.draw.polygon(s,(76,105,62),polygon)
        for x in range(0,int(width)+1,100): pygame.draw.line(s,(83,113,68),c.world_to_screen(Vec(x,0)),c.world_to_screen(Vec(x,height)))
        for y in range(0,int(height)+1,100): pygame.draw.line(s,(83,113,68),c.world_to_screen(Vec(0,y)),c.world_to_screen(Vec(width,y)))
        self.terrain_painter.draw(s,c,battle.terrain,getattr(controls,'contours',True))
        if zones:
            overlay = pygame.Surface(s.get_size(),pygame.SRCALPHA)
            for army,zone in enumerate(zones):
                points = [c.world_to_screen(Vec(x,y)) for x,y in [(zone.left,zone.top),(zone.right,zone.top),(zone.right,zone.bottom),(zone.left,zone.bottom)]]
                pygame.draw.polygon(overlay,(55,120,240,40) if army == 0 else (230,65,55,40),points)
                pygame.draw.polygon(overlay,(100,175,255) if army == 0 else (250,125,100),points,2)
            s.blit(overlay,(0,0))
        for u in battle.units:
            if not u.active: continue
            pose=self.unit_poses[u.id]
            color = (75,150,235) if u.army == 0 else (218,94,77)
            if not u.effective: color = tuple(int(v*.6) for v in color)
            pts = [c.world_to_screen(p) for p in pose.footprint]
            if u.formation==Formation.SKIRMISH:
                pygame.draw.polygon(s,tuple(int(v*.55) for v in color),pts,1)
                forward,side=direction(pose.facing),direction(pose.facing+math.pi/2)
                for row in (-.28,.28):
                    for file in range(7):
                        marker=pose.pos+forward*(row*pose.depth)+side*((file/6-.5)*pose.width)
                        pygame.draw.circle(s,color,c.world_to_screen(marker),max(2,round(2*c.zoom)))
            else: pygame.draw.polygon(s,color,pts)
            pygame.draw.polygon(s,(250,230,110) if controls.selected == u.id else (25,38,29),pts,3 if controls.selected == u.id else 1)
            p = c.world_to_screen(pose.pos)
            end = c.world_to_screen(pose.pos+direction(pose.facing)*(pose.depth/2+10))
            pygame.draw.line(s,(255,243,197),p,end,2)
            self.hud.text(s,u.archetype.symbol,(p[0]-4,p[1]-8),u.archetype.accent)
            for n,value,col in [(0,u.strength/u.stats.strength,(235,235,210)),(1,u.morale/100,(240,202,66)),(2,u.cohesion/100,(80,225,185))]:
                pygame.draw.rect(s,(28,37,30),(p[0]-20,p[1]+16+n*4,40,3))
                pygame.draw.rect(s,col,(p[0]-20,p[1]+16+n*4,40*value,3))
            if controls.selected == u.id or controls.debug:
                dest = u.order.destination
                if dest:
                    d=c.world_to_screen(dest)
                    pygame.draw.line(s,(240,223,129),p,d,1)
                    pygame.draw.circle(s,(240,223,129),d,5,1)
            if u.congestion > .05:
                pygame.draw.polygon(s, (244,170,71), pts, 2)
            if u.infantry_charging or (u.stats.kind.value=='cavalry' and u.cavalry_state.value in ('charging','pursuit','recoil','reforming')):
                phase='charging' if u.infantry_charging else u.cavalry_state.value
                tint=(255,205,90) if phase=='charging' else (225,160,255) if phase=='pursuit' else (245,150,110)
                self.hud.text(s,{'charging':'CH','pursuit':'P','recoil':'RC','reforming':'RF'}[phase],(p[0]-10,p[1]-47),tint)
                if phase=='charging':
                    tip=c.world_to_screen(pose.pos+direction(pose.facing)*(pose.depth/2+14+u.charge_momentum*18))
                    pygame.draw.line(s,tint,p,tip,3)
                    for sign in (-1,1):
                        wing=c.world_to_screen(pose.pos+direction(pose.facing)*(pose.depth/2+7+u.charge_momentum*18)+direction(pose.facing+math.pi/2)*(sign*5))
                        pygame.draw.line(s,tint,wing,tip,2)
            if u.settling_goal is not None:
                goal=c.world_to_screen(u.settling_goal)
                pygame.draw.circle(s,(215,180,255),goal,5,1)
                if controls.debug: pygame.draw.line(s,(215,180,255),p,goal,1)
                if controls.debug and u.position_preference is not None:
                    pygame.draw.circle(s,(240,223,129),c.world_to_screen(u.position_preference),4,1)
            if controls.debug:
                if u.avoidance_goal:
                    waypoint = c.world_to_screen(u.avoidance_goal)
                    pygame.draw.line(s,(155,235,255),p,waypoint,2)
                    pygame.draw.circle(s,(155,235,255),waypoint,7,2)
                self.hud.text(s,f'#{u.id} {u.state.value}',(p[0]-35,p[1]-32))
                if u.stats.range and u.id!=controls.selected:
                    radius=u.stats.range*c.zoom
                    # Keep the same arithmetic/projection order as Vec math,
                    # without allocating two vectors per debug arc point.
                    arc=[p]
                    for i in range(25):
                        vector=direction(pose.facing-battle.rules.firing_half_arc+i*battle.rules.firing_half_arc/12)
                        arc.append(((pose.pos.x+vector.x*u.stats.range-c.center.x)*c.zoom+c.width/2,
                                    (pose.pos.y+vector.y*u.stats.range-c.center.y)*c.zoom+(c.height-150)/2))
                    pygame.draw.lines(s,(135,150,105),False,arc+[p],1)
                if u.terrain_waypoint:
                    point=c.world_to_screen(u.terrain_waypoint)
                    pygame.draw.line(s,(220,150,255),p,point,2)
                    pygame.draw.circle(s,(220,150,255),point,7,2)
                target=battle.unit(u.target_id) or battle.unit(u.order.target_id)
                if target:
                    sight=battle.visibility(u,target)
                    color=(110,225,140) if sight.state=='clear' else (245,200,80) if sight.visible else (245,100,85)
                    pygame.draw.line(s,color,p,c.world_to_screen(self.unit_poses.get(target.id,target).pos),2)
        has_smoke=any(e.kind=='smoke' for e in battle.effects)
        smoke=None
        if has_smoke:
            if self._smoke_surface is None or self._smoke_surface.get_size()!=s.get_size():
                self._smoke_surface=pygame.Surface(s.get_size(),pygame.SRCALPHA)
            smoke=self._smoke_surface
            smoke.fill((0,0,0,0))
        for e in battle.effects:
            age = max(0., battle.time - e.started)
            life = max(0., e.expires - battle.time)
            if e.kind == 'smoke':
                # Frontage-wide plume, expanding/fading in simulation time. No RNG.
                forward, side = direction(e.facing), direction(e.facing + math.pi/2)
                opacity = int(150 * life / max(.01, e.expires - e.started))
                for i in range(9):
                    offset = (i / 8 - .5) * e.width
                    position = e.pos + side * offset + forward * (age * 5)
                    point = c.world_to_screen(position)
                    radius = max(3, int((4 + age * 4 + (i % 3)) * c.zoom))
                    pygame.draw.circle(smoke,(215,218,200,opacity),point,radius)
                    if age < .22:
                        pygame.draw.circle(smoke,(255,226,115,230),point,max(2,int(3*c.zoom)))
            elif e.kind=='charge_impact':
                point=c.world_to_screen(e.pos)
                pygame.draw.circle(s,(255,219,115),point,max(4,int((8+age*24)*c.zoom)),3)
            else:
                pygame.draw.circle(s,(226,170,70),c.world_to_screen(e.pos),max(2,int((5+life*3)*c.zoom)),1)
        if smoke is not None: s.blit(smoke,(0,0))
        for p in battle.projectiles:
            pose=motion.ball_pose(p,alpha) if motion else p
            location=c.world_to_screen(pose.pos)
            ground=battle.terrain.get_elevation(pose.pos.x,pose.pos.y)
            height=max(ground,pose.height)
            pygame.draw.circle(s,(30,32,24),location,3)
            pygame.draw.circle(s,(255,219,129),(location[0],location[1]-(height-ground)*c.zoom),3)
        draw_ranges(self,battle,controls)
        if zones is None: self.draw_selected_targets(battle,controls)
        if zones is None:
            selected=battle.unit(controls.selected)
            gesture=getattr(controls,'move_gesture',None)
            if selected and selected.effective:
                preview=replace(selected,formation=selected.next_formation or selected.formation)
                if gesture is not None and gesture.unit_id==selected.id:
                    origin=self.unit_poses.get(selected.id,selected).pos
                    pygame.draw.line(s,(100,245,155),c.world_to_screen(origin),c.world_to_screen(gesture.destination),1)
                    draw_ghost(s,c,preview,gesture.destination,gesture.preview_facing,(100,245,155))
                elif selected.order.destination is not None and selected.order.facing is not None:
                    draw_ghost(s,c,preview,selected.order.destination,selected.order.facing,(240,223,129))
        self.hud.draw(s,battle,controls,fps,show_targets=zones is None)
        if controls.debug:
            cursor=c.screen_to_world(pygame.mouse.get_pos())
            if 0<=cursor.x<=width and 0<=cursor.y<=height:
                info=f'{battle.terrain.terrain_type(cursor.x,cursor.y)} | elevation {battle.terrain.get_elevation(cursor.x,cursor.y):.1f} m | slope {battle.terrain.slope(cursor.x,cursor.y):.0%} | forest {battle.terrain.forest_density(cursor.x,cursor.y):.0%}'
                self.hud.text(s,info,(max(14,s.get_width()-610),s.get_height()-171))
            selected=battle.unit(controls.selected)
            if selected:
                speed=selected.terrain_speed if battle.tick else battle.terrain.movement_effect(selected,direction(selected.facing),battle.rules.terrain).speed
                self.hud.text(s,f'Terrain speed x{speed:.2f} | cohesion -{selected.terrain_loss:.2f}/s | elevation {battle.terrain.get_elevation(selected.pos.x,selected.pos.y):.1f} m',(14,106))
        if present: pygame.display.flip()

    def draw_selected_targets(self,battle,controls):
        """Visible without F3 and drawn over smoke; never changes battle state."""
        selected = battle.unit(controls.selected)
        target = current_target(battle,selected)
        requested = ordered_target(battle,selected)
        if target:
            source = self.camera.world_to_screen(self.unit_poses.get(selected.id,selected).pos)
            point = self.camera.world_to_screen(self.unit_poses.get(target.id,target).pos)
            delta = Vec(point[0]-source[0],point[1]-source[1])
            distance = delta.length()
            forward = delta.normalized()
            # Dashed connector does not conceal the intervening formations.
            for start in range(0,int(distance),16):
                a = Vec(*source) + forward * start
                b = Vec(*source) + forward * min(start+8,distance)
                pygame.draw.line(self.screen,TARGET_COLOR,(a.x,a.y),(b.x,b.y),1)
            self.target_marker(target,TARGET_COLOR,reticle=True)
        if requested and requested is not target:
            self.target_marker(requested,ORDER_COLOR,reticle=False)

    def target_marker(self,target,color,reticle):
        pose=self.unit_poses.get(target.id,target)
        points = [self.camera.world_to_screen(p) for p in pose.footprint]
        pygame.draw.polygon(self.screen,(24,29,26),points,5)
        pygame.draw.polygon(self.screen,color,points,2)
        center = self.camera.world_to_screen(self.unit_poses.get(target.id,target).pos)
        x,y = round(center[0]),round(min(p[1] for p in points)-18)
        if reticle:
            pygame.draw.circle(self.screen,(24,29,26),(x,y),12,5)
            pygame.draw.circle(self.screen,color,(x,y),12,2)
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                a,b=(x+dx*8,y+dy*8),(x+dx*17,y+dy*17)
                pygame.draw.line(self.screen,(24,29,26),a,b,5)
                pygame.draw.line(self.screen,color,a,b,2)
        else:
            diamond=[(x,y-10),(x+10,y),(x,y+10),(x-10,y)]
            pygame.draw.polygon(self.screen,(24,29,26),diamond,5)
            pygame.draw.polygon(self.screen,color,diamond,2)
