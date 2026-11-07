import pygame
from collections import OrderedDict
from .targeting import current_target, ordered_target, target_status, TARGET_COLOR, ORDER_COLOR
from simulation.commanders import effect_lines
from .command_bar import buttons

class HUD:
    def __init__(self):
        self.font = pygame.font.Font(None, 21)
        self.title = pygame.font.Font(None, 27)
        self._text_cache=OrderedDict()
    def text(self, screen, text, pos, color=(235,239,220), big=False):
        font=self.title if big else self.font
        key=(id(font),text,tuple(color))
        surface=self._text_cache.get(key)
        if surface is None:
            surface=font.render(text,True,color)
            self._text_cache[key]=surface
            if len(self._text_cache)>512: self._text_cache.popitem(last=False)
        else: self._text_cache.move_to_end(key)
        screen.blit(surface,pos)
    def draw(self, screen, battle, controls, fps, show_targets=True):
        width,height = screen.get_size()
        pygame.draw.rect(screen,(22,29,29),(0,height-150,width,150))
        speed=str(controls.speed)+'x'
        if controls.actual_speed is not None: speed+=f' (actual {controls.actual_speed:.1f}x)'
        if controls.slow: speed+=f' [limited; {controls.backlog:.1f}s pending]'
        header=f'QUIBERON | {battle.time:6.1f}s | {"PAUSED" if controls.paused else speed} | seed {battle.seed}'
        self.text(screen,header,(14,10),big=self.title.size(header)[0]<=width-28)
        if show_targets:self.command_bar(screen,battle,controls)
        u = battle.unit(controls.selected)
        if u:
            self.text(screen,f'#{u.id} {u.archetype.name} | {u.strength}/{u.stats.strength}',(14,height-80))
            self.text(screen,f'Morale {u.morale:.0f}  Cohesion {u.cohesion:.0f}  Fatigue {u.fatigue:.0f} | {u.state.value}',(14,height-60))
            reach=f'{u.stats.range:g} m range' if u.stats.range else 'melee only'
            if u.stats.kind.value=='artillery':reach+=f' | {u.available_guns}/{u.archetype.guns} guns'
            self.text(screen,f'{u.formation.value}{" (changing)" if u.transition_left else ""} | {u.order.kind.value} | {u.combat_state} | {reach}',(14,height-40))
            trait=u.archetype.trait.value if u.archetype.trait else 'Standard drill'
            self.text(screen,f'{trait} | {u.archetype.faction}',(14,height-20),u.archetype.accent)
        else: self.text(screen,'Select a blue regiment with left click; issue an order with right click.',(14,height-80))
        for i,e in enumerate(list(battle.events)[-4:]):
            left=max(520,width//2+20);label=f'{e.time:5.0f}s {e.message}'
            while self.font.size(label)[0]>width-left-10 and len(label)>4:label=label[:-4]+'...'
            self.text(screen,label,(left,height-80+i*19),(240,205,155))
        if controls.debug:
            if u:
                self.text(screen, f'AI: {u.ai_state}', (14,62))
                self.text(screen, f'Congestion {u.congestion:.0%} | speed x{u.congestion_speed:.2f} | {u.speed:.2f} m/s', (14,84))
                self.text(screen,f'Overlap {u.stationary_overlap:.1f}s | settling {u.settling_goal is not None} | last volley frontage {u.fire_lane_factor:.0%}',(14,125))
            self.text(screen,f'tick {battle.tick} | fixed dt {battle.rules.dt}s | render {fps:.0f} FPS | balls {len(battle.projectiles)}',(14,40))
        if show_targets and u and not battle.sandbox:
            target = current_target(battle,u)
            requested = ordered_target(battle,u)
            y = 154 if controls.debug else 38
            panel_width = min(515,width-28)
            lines = [(f'Target: {target.name} [#{target.id}]' if target else 'Target: none',TARGET_COLOR),
                     (target_status(battle,u,target or requested),(235,235,215))]
            if requested and requested is not target:
                lines.append((f'Ordered: {requested.name} [#{requested.id}] (cyan diamond)',ORDER_COLOR))
            pygame.draw.rect(screen,(22,29,29),(10,y-3,panel_width+8,len(lines)*21+6))
            for index,(label,color) in enumerate(lines):
                while self.font.size(label)[0] > panel_width:
                    label=label[:-4]+'...'
                self.text(screen,label,(14,y+index*21),color)
        if u and u.archetype.trait:
            top=(154 if controls.debug else 38)+80
            words=u.archetype.ability.split(); line=''; row=0
            for word in words:
                if self.font.size(line+' '+word)[0]>495:
                    self.text(screen,line,(14,top+row*20),u.archetype.accent); row+=1; line=''
                line=(line+' '+word).strip()
            self.text(screen,line,(14,top+row*20),u.archetype.accent)
        if u and (u.stats.kind.value=='cavalry' or u.order.kind.value=='charge'):
            top=320 if controls.debug else 200
            mounted=u.stats.kind.value=='cavalry'
            if mounted:
                maximum=battle.rules.charge_max_speed*u.archetype.charge_speed;phase=u.cavalry_state.value
            else:
                from simulation.formations import PROFILES
                maximum=u.stats.speed*PROFILES[u.formation][2]*battle.rules.infantry_charge_speed
                phase='charging' if u.infantry_charging else 'melee' if u.combat_state=='melee' else 'closing'
            self.text(screen,f'{"Cavalry" if mounted else "Bayonets"}: {phase} | {u.speed:.1f}/{maximum:.1f} m/s | momentum {u.charge_momentum:.0%}',(14,top),(255,215,135))
            if controls.debug:
                target_id=u.cavalry_target_id if mounted else u.infantry_charge_target_id
                reach=battle.rules.charge_range if mounted else battle.rules.infantry_charge_range
                self.text(screen,f'Charge target #{target_id} | initiation {reach:g} m | run {u.charge_distance:.1f} m',(14,top+21))
                self.text(screen,f'Last impact: {u.charge_result} ({u.charge_last_momentum:.0%}) | ready {u.charge_ready}',(14,top+42))
        if u and u.commander:
            top=154 if controls.debug else 110
            max_width=min(570,width//2-28)
            left=width-max_width-14
            lines=effect_lines(u)
            pygame.draw.rect(screen,(22,29,29),(left-4,top-3,max_width+8,len(lines)*19+6))
            for i,label in enumerate(lines):
                while self.font.size(label)[0]>max_width:label=label[:-4]+'...'
                self.text(screen,label,(left,top+i*19),(220,219,165) if i<2 else (210,218,207))
        if battle.result:
            pygame.draw.rect(screen,(24,30,35),(width//2-240,65,480,65))
            self.text(screen,f'Battle result: {battle.result}',(width//2-215,78),big=True)
            self.text(screen,'Tab: statistics and Continue campaign' if controls.campaign else 'Tab stats | F5 restart | F6 new seed | F7 setup.',(width//2-215,107))

    def command_bar(self,screen,battle,controls):
        width,height=screen.get_size()
        self.text(screen,'Formation',(14,height-139))
        self.text(screen,'Orders',(14,height-107))
        for button in buttons(width,height,battle,controls):
            color=(81,96,54) if button.active and button.enabled else (45,68,61) if button.enabled else (32,39,37)
            pygame.draw.rect(screen,color,button.rect,border_radius=3)
            pygame.draw.rect(screen,(209,204,132) if button.active else (100,126,107),button.rect,1,border_radius=3)
            x=button.rect.centerx-self.font.size(button.label)[0]//2
            self.text(screen,button.label,(x,button.rect.y+6),(237,237,215) if button.enabled else (111,120,110))
        kind=controls.pending_order
        if kind is not None:
            hint=f'{kind.value.title()}: left-click an enemy; Esc cancels' if kind.value in ('attack','charge') else f'{kind.value.title()}: left-drag ground for position/facing; Esc cancels' if kind.value in ('move','advance') else 'Defend: left-click ground; Esc cancels'
        elif controls.move_gesture is not None:hint='Drag to set facing; release to issue order. Esc cancels.'
        else:hint='RMB move/attack | L/C/K forms | Space pause | F3 debug'
        limit=width-390
        while self.font.size(hint)[0]>limit and len(hint)>4:hint=hint[:-4]+'...'
        self.text(screen,hint,(382,height-138),(255,216,135) if kind else (207,216,201))
