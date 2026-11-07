"""Small Pygame setup form and a transactional deployment editor."""
from dataclasses import replace
import math
from pathlib import Path
import pygame
from scenarios.battle_config import BattleConfig, ConfigError, DeploymentSession, SIZES
from scenarios.presets import PRESETS, load_preset
from simulation.formations import Formation
from simulation.geometry import Vec, contains
from simulation.orders import Order, OrderKind
from simulation.regiment import UnitType
from simulation.terrain import TERRAIN_PRESETS
from simulation.archetypes import ARCHETYPES
from simulation.ai import STRATEGIES, STRATEGY_NAMES
from simulation import commanders as cmd
from .placement import FacingGesture, draw_ghost

class Form:
    """Fixed logical menu coordinates scaled to fit the window, including hit tests."""
    def __init__(self, size=(960,640)):
        self.canvas = pygame.Surface(size)
        self.font = pygame.font.Font(None,24)
        self.title = pygame.font.Font(None,34)
        self.small = pygame.font.Font(None,19)
        self.buttons = {}
        self.origin = (0,0)
        self.scale = 1.

    def text(self,text,pos,color=(232,237,218),big=False,small=False):
        self.canvas.blit((self.title if big else self.small if small else self.font).render(str(text),True,color),pos)

    def button(self,key,label,rect,enabled=True):
        rect=pygame.Rect(rect)
        self.buttons[key]=(rect,enabled)
        pygame.draw.rect(self.canvas,(56,78,73) if enabled else (38,44,43),rect,border_radius=4)
        pygame.draw.rect(self.canvas,(130,159,137) if enabled else (70,78,70),rect,1,border_radius=4)
        text=self.font.render(label,True,(240,236,210) if enabled else (113,124,112))
        if text.get_width()>rect.width-10:
            scale=(rect.width-10)/text.get_width()
            text=pygame.transform.smoothscale(text,(max(1,int(text.get_width()*scale)),max(1,int(text.get_height()*scale))))
        self.canvas.blit(text,text.get_rect(center=rect.center))

    def point(self,pos):
        return ((pos[0]-self.origin[0])/self.scale,(pos[1]-self.origin[1])/self.scale)

    def hit(self,pos):
        point=self.point(pos)
        return next((key for key,(rect,enabled) in self.buttons.items() if enabled and rect.collidepoint(point)),None)

    def present(self,screen,bottom=False):
        w,h=self.canvas.get_size()
        self.scale=min(screen.get_width()/w, (150 if bottom else screen.get_height())/h)
        size=(round(w*self.scale),round(h*self.scale))
        self.origin=((screen.get_width()-size[0])//2,screen.get_height()-size[1] if bottom else (screen.get_height()-size[1])//2)
        screen.blit(pygame.transform.smoothscale(self.canvas,size),self.origin)

    def message(self,text,y=548):
        # Wrap errors rather than clipping the actionable part off the window.
        words=str(text).split(); line=''; row=0
        for word in words:
            candidate=(line+' '+word).strip()
            if self.font.size(candidate)[0]>900 and line:
                self.text(line,(25,y+row*22),(255,202,132)); row+=1; line=word
            else: line=candidate
        self.text(line,(25,y+row*22),(255,202,132))

class SetupScreen:
    def __init__(self, config=None, path='battle_config.json'):
        self.config=config or load_preset(PRESETS[0])
        self.seed_text='' if self.config.seed is None else str(self.config.seed)
        self.path=str(path)
        self.focus=None
        self.select_all=False
        self.message='Choose armies and field, then deploy. Blank seed generates a new one.'
        self.menu_requested=False
        self.next_config=None
        self.quit=False
        self.form=Form((960,740))
        self.scrolls=[0,0]
        self.info_open=None
        self.info_army=0
        self.unit_filter='all'
        self.browser_scroll=0
        self.adding=False
        self.amount=1
        self.show_compositions()

    def show_compositions(self):
        self.scrolls=[0,0]

    def recipe(self):
        try: seed=None if not self.seed_text.strip() else int(self.seed_text)
        except ValueError as exc: raise ConfigError('Seed must be an integer, or blank.') from exc
        return replace(self.config,seed=seed)

    def action(self,key):
        if key=='menu':self.menu_requested=True;return
        try:
            if key.startswith('preset:'):
                self.config=load_preset(key.split(':',1)[1]); self.seed_text=''
                self.show_compositions()
            elif key in ('preset_prev','preset_next'):
                index=PRESETS.index(self.config.name) if self.config.name in PRESETS else 0
                self.config=load_preset(PRESETS[(index+(1 if key=='preset_next' else -1))%len(PRESETS)]); self.seed_text=''
                self.show_compositions()
            elif key.startswith('scroll:'):
                _,army,delta=key.split(':'); army=int(army)
                composition=self.config.blue if army==0 else self.config.red
                self.scrolls[army]=max(0,min(max(0,len(composition.roster())-3),self.scrolls[army]+int(delta)))
            elif key.startswith('info:'): self.adding=False; self.info_open=key.split(':',1)[1]; self.unit_filter='all'; self.browser_scroll=0; return
            elif key.startswith('add:'):
                self.action('browse:'+key.split(':')[1]); self.adding=True; self.amount=1; return
            elif key.startswith('amount:'):
                self.amount=max(1,min(self.config.max_per_type,self.amount+int(key.split(':')[1]))); return
            elif key=='confirm_add':
                composition=self.config.blue if self.info_army==0 else self.config.red
                count=composition.count(self.info_open)+self.amount
                if count>self.config.max_per_type or self.config.blue.total+self.config.red.total+self.amount*(2 if self.config.symmetric else 1)>self.config.max_total:
                    self.message='Amount exceeds unit or army limit.'; return
                self.config=self.config.with_army(self.info_army,composition.with_count(self.info_open,count))
                chosen=[key for key,n in (self.config.blue if self.info_army==0 else self.config.red).roster()]
                self.scrolls[self.info_army]=min(chosen.index(self.info_open),max(0,len(chosen)-3))
                self.info_open=None; self.adding=False; self.message='Regiments added.'; return
            elif key.startswith('strategy:'):
                army=int(key.split(':')[1]); values=list(self.config.ai_strategies)
                values[army]=STRATEGIES[(STRATEGIES.index(values[army])+1)%len(STRATEGIES)]
                self.config=replace(self.config,ai_strategies=tuple(values)); return
            elif key.startswith('browse:'):
                self.adding=False
                self.info_army=int(key.split(':')[1]); self.info_open=list(ARCHETYPES)[self.scrolls[self.info_army]]
                self.unit_filter='all'; self.browser_scroll=0; return
            elif key.startswith('unit:'):
                self.adding=False
                _,army,unit=key.split(':'); self.info_army=int(army); self.info_open=unit
                self.unit_filter='all'; self.browser_scroll=0; return
            elif key.startswith('choose:'): self.info_open=key.split(':')[1]; return
            elif key.startswith('filter:'):
                self.unit_filter=key.split(':')[1]; self.browser_scroll=0
                candidates=self.browser_units()
                if candidates and self.info_open not in {a.id for a in candidates}: self.info_open=candidates[0].id
                return
            elif key.startswith('browser_scroll:'):
                self.browser_scroll=max(0,min(max(0,len(self.browser_units())-9),self.browser_scroll+int(key.split(':')[1]))); return
            elif key=='close_info': self.info_open=None; return
            elif key.startswith('count:'):
                _,army,kind,delta=key.split(':'); army=int(army)
                composition=self.config.blue if army==0 else self.config.red
                count=max(0,min(self.config.max_per_type,composition.count(kind)+int(delta)))
                self.config=self.config.with_army(army,composition.with_count(kind,count))
            elif key=='symmetric':
                on=not self.config.symmetric
                self.config=replace(self.config,symmetric=on,red=self.config.blue if on else self.config.red,placements=() if on and self.config.blue!=self.config.red else self.config.placements)
            elif key=='spectator': self.config=self.config.with_ai_armies((1,) if self.config.ai_armies==(0,1) else (0,1))
            elif key.startswith('size:'):
                width,height=SIZES[key.split(':',1)[1]]
                if (width,height)!=(self.config.width,self.config.height):
                    self.config=replace(self.config,width=width,height=height,placements=(),terrain=None)
            elif key.startswith('terrain:'):
                self.config=replace(self.config,terrain_preset=key.split(':',1)[1],terrain_seed=None,terrain=None,placements=())
            elif key=='terrain_random':
                if self.config.terrain_preset not in TERRAIN_PRESETS: raise ConfigError('Choose a generated terrain preset before regenerating a custom map.')
                self.config=replace(self.config,terrain_seed=self.config.new_seed().seed,terrain=None,placements=())
            elif key=='random': self.seed_text=str(self.config.new_seed().seed)
            elif key=='save':
                config=self.recipe().prepared(); config.save(self.path)
                self.config=config; self.seed_text=str(config.seed)
                self.message=f'Saved {self.path} (seed {config.seed}).'; return
            elif key=='load':
                self.config=BattleConfig.load(self.path); self.seed_text='' if self.config.seed is None else str(self.config.seed)
                self.show_compositions()
                self.message=f'Loaded {self.path}. Custom deployment is retained.'; return
            elif key=='deploy':
                self.next_config=self.recipe().prepared(); return
            elif key=='quit': self.quit=True
            self.message='Setup updated. Composition/field changes regenerate deployment.'
        except (ConfigError,OSError) as exc: self.message=str(exc)

    def handle(self,event):
        if self.info_open:
            if event.type==pygame.KEYDOWN and event.key in (pygame.K_ESCAPE,pygame.K_RETURN): self.info_open=None
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                hit=self.form.hit(event.pos)
                if hit: self.action(hit)
            elif event.type==pygame.MOUSEWHEEL: self.action(f'browser_scroll:{-event.y}')
            return
        if event.type==pygame.MOUSEWHEEL:
            point=self.form.point(pygame.mouse.get_pos())
            if 115<=point[1]<=305: self.action(f'scroll:{0 if point[0]<480 else 1}:{-event.y}')
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            point=self.form.point(event.pos)
            self.focus='seed' if pygame.Rect(25,535,350,36).collidepoint(point) else 'path' if pygame.Rect(25,595,550,36).collidepoint(point) else None
            self.select_all=False
            hit=self.form.hit(event.pos)
            if hit: self.action(hit)
        if event.type==pygame.KEYDOWN:
            if event.key==pygame.K_ESCAPE: self.quit=True
            elif event.key==pygame.K_TAB:
                self.focus='path' if self.focus=='seed' else 'seed'; self.select_all=False
            elif event.key==pygame.K_RETURN: self.action('deploy')
            elif self.focus:
                value=self.seed_text if self.focus=='seed' else self.path
                if event.key==pygame.K_a and getattr(event,'mod',0)&pygame.KMOD_CTRL:
                    self.select_all=True; return
                if event.key==pygame.K_BACKSPACE:
                    value='' if self.select_all else value[:-1]; self.select_all=False
                else:
                    char=getattr(event,'unicode','')
                    if char.isprintable() and (self.focus=='path' or char in '-0123456789'):
                        value=(('' if self.select_all else value)+char)[:240 if self.focus=='path' else 20]
                        self.select_all=False
                if self.focus=='seed': self.seed_text=value
                else: self.path=value

    def draw(self,screen):
        f=self.form; f.canvas.fill((25,36,32)); f.buttons.clear()
        f.text('QUIBERON — Battle testing sandbox',(25,20),big=True)
        f.button('preset_prev','< Previous preset',(25,65,200,34))
        f.button('preset:'+self.config.name if self.config.name in PRESETS else 'preset:'+PRESETS[0],self.config.name,(240,65,475,34))
        f.button('preset_next','Next preset >',(730,65,205,34))
        for army,label in enumerate(('Blue army','Red army')):
            x=25+army*480
            pygame.draw.rect(f.canvas,(35,49,45),(x,115,430,212),border_radius=5)
            composition=self.config.blue if army==0 else self.config.red
            roster=[a for a in ARCHETYPES.values() if composition.count(a.id)]
            self.scrolls[army]=min(self.scrolls[army],max(0,len(roster)-3))
            f.text(f'{label}: {composition.total}',(x+15,125),(130,184,249) if army==0 else (249,148,130),True)
            f.button(f'add:{army}','+ Add',(x+205,125,65,30),army==0 or not self.config.symmetric)
            f.button(f'browse:{army}','…',(x+275,125,25,30))
            f.button(f'scroll:{army}:-3','Up',(x+310,125,48,30),self.scrolls[army]>0)
            f.button(f'scroll:{army}:3','Down',(x+365,125,55,30),self.scrolls[army]<len(roster)-3)
            for row,archetype in enumerate(roster[self.scrolls[army]:self.scrolls[army]+3]):
                y=170+row*42
                f.button(f'unit:{army}:{archetype.id}',f'{archetype.stats.kind.value[0].upper()}: {archetype.menu_name or archetype.name}',(x+10,y,248,23))
                stats=archetype.stats
                f.text(f'{stats.strength} troops | {stats.range:g} m | {stats.reload:g} s reload' if stats.range else f'{stats.strength} riders | {stats.speed:g} m/s base',(x+13,y+25),small=True)
                f.text(composition.count(archetype.id),(x+275,y+7))
                enabled=army==0 or not self.config.symmetric
                f.button(f'count:{army}:{archetype.id}:-1','−',(x+310,y,40,32),enabled)
                f.button(f'count:{army}:{archetype.id}:1','+',(x+365,y,40,32),enabled)
            if not roster: f.text('Click + Add to build this army.',(x+14,185))
            f.button(f'strategy:{army}','AI: '+STRATEGY_NAMES[self.config.ai_strategies[army]]+' >',(x+10,302,410,22))
        f.button('symmetric',('[x]' if self.config.symmetric else '[ ]')+' Symmetric armies',(25,330,300,26))
        f.button('spectator',('[x]' if self.config.ai_armies==(0,1) else '[ ]')+' AI controls both armies',(500,330,435,26))
        for i,(name,(w,h)) in enumerate(SIZES.items()):
            mark='* ' if (w,h)==(self.config.width,self.config.height) else ''
            f.button('size:'+name,f'{mark}{name}: {w:.0f} × {h:.0f} m',(25+(i%3)*310,365+(i//3)*27,290,24))
        for i,name in enumerate(TERRAIN_PRESETS):
            mark='* ' if name==self.config.terrain_preset else ''
            f.button('terrain:'+name,mark+name,(25+(i%3)*310,425+(i//3)*35,290,30))
        f.button('terrain_random','Regenerate map',(680,495,255,28))
        f.text(f'Terrain seed: {self.config.terrain_seed if self.config.terrain_seed is not None else "from initial seed"}',(25,495))
        f.text('Seed (blank = generate)' ,(25,515))
        pygame.draw.rect(f.canvas,(60,78,66) if self.focus=='seed' else (39,51,44),(25,535,350,36))
        f.text(self.seed_text or '(automatic)',(34,542)); f.button('random','New seed',(400,535,160,36))
        f.text(f'{self.config.blue.total+self.config.red.total}/{self.config.max_total} total; 0–{self.config.max_per_type} per type',(590,543))
        f.text('Configuration JSON path (click to edit)',(25,575))
        pygame.draw.rect(f.canvas,(60,78,66) if self.focus=='path' else (39,51,44),(25,595,550,36))
        path=self.path
        while f.font.size(path)[0]>530: path=path[1:]
        f.text(path,(34,603)); f.button('save','Save JSON',(590,595,155,36)); f.button('load','Load JSON',(770,595,165,36))
        f.message(self.message,640)
        f.button('quit','Exit',(25,695,120,32)); f.button('deploy','Deploy armies >',(700,690,235,40))
        if self.info_open: self.draw_browser()
        f.button("menu","Main menu",(790,12,145,30))
        screen.fill((19,27,25)); f.present(screen)

    def browser_units(self):
        return [a for a in ARCHETYPES.values() if self.unit_filter=='all' or a.stats.kind.value==self.unit_filter]

    def draw_browser(self):
        f=self.form; f.buttons.clear()
        pygame.draw.rect(f.canvas,(18,28,26),(20,40,920,650),border_radius=8)
        composition=self.config.blue if self.info_army==0 else self.config.red
        locked=self.info_army==1 and self.config.symmetric
        title='add regiments' if self.adding else 'regiment browser'
        f.text(f'{"Blue" if self.info_army==0 else "Red"} army — {title} ({composition.total} units)',(38,58),big=True)
        for i,kind in enumerate(('all','infantry','cavalry','artillery')):
            f.button('filter:'+kind,('* ' if self.unit_filter==kind else '')+kind.title(),(38+i*110,104,103,30))
        choices=self.browser_units()
        for row,a in enumerate(choices[self.browser_scroll:self.browser_scroll+9]):
            y=151+row*49
            mark='> ' if a.id==self.info_open else ''
            f.button('choose:'+a.id,mark+(a.menu_name or a.name),(38,y,350,27))
            f.text(f'{a.stats.strength} troops | {a.stats.range:g} m | {a.stats.speed:g} m/s base',(44,y+29),small=True)
            f.text(f'×{composition.count(a.id)}',(406,y+6))
        if len(choices)>9:
            f.button('browser_scroll:-9','Up',(38,601,100,28),self.browser_scroll>0)
            f.button('browser_scroll:9','Down',(150,601,100,28),self.browser_scroll+9<len(choices))
        a=ARCHETYPES[self.info_open]; stats=a.stats
        y=151
        def paragraph(text,color=(232,237,218),small=False):
            nonlocal y
            font=f.small if small else f.font
            line=''
            for word in text.split():
                if font.size((line+' '+word).strip())[0]>410 and line:
                    f.text(line,(495,y),color,small=small); y+=21
                    line=''
                line=(line+' '+word).strip()
            f.text(line,(495,y),color,small=small); y+=26
        paragraph(a.name,a.accent)
        paragraph(f'{a.faction} | {stats.kind.value}',small=True)
        paragraph(f'Crew {stats.strength} | Guns {a.guns} | Morale {a.initial_morale:g}' if stats.kind==UnitType.ARTILLERY else f'Strength {stats.strength} | Initial morale {a.initial_morale:g}')
        paragraph(f'Range {stats.range:g} m | Base reload {stats.reload:g} s' if stats.range else 'Melee cavalry — no ranged weapon')
        paragraph(f'Base speed {stats.speed:g} m/s | Turn {stats.turn_rate:g} rad/s')
        paragraph(f'Discipline ×{stats.discipline:g} | Accuracy ×{a.accuracy:g} | Melee ×{a.melee*a.melee_damage:g}',small=True)
        paragraph('Formations: '+', '.join(form.value for form in a.formations),small=True)
        paragraph('Strengths: '+a.strengths,small=True)
        paragraph('Weaknesses: '+a.weaknesses,small=True)
        paragraph('Trait: '+a.ability,a.accent,small=True)
        if self.adding:
            f.text(f'Add amount: {self.amount}',(495,560),big=True)
            f.button('amount:-1','−',(680,554,70,34),self.amount>1)
            f.button('amount:1','+',(765,554,70,34),self.amount<self.config.max_per_type)
            fits=composition.count(a.id)+self.amount<=self.config.max_per_type and self.config.blue.total+self.config.red.total+self.amount*(2 if self.config.symmetric else 1)<=self.config.max_total
            f.button('confirm_add',f'Add {self.amount} regiments',(495,598,340,30),not locked and fits)
        else:
            f.text(f'Count: {composition.count(a.id)}',(495,590),big=True)
            f.button(f'count:{self.info_army}:{a.id}:-1','−',(680,584,70,34),not locked and composition.count(a.id)>0)
            f.button(f'count:{self.info_army}:{a.id}:1','+',(765,584,70,34),not locked and composition.count(a.id)<self.config.max_per_type)
        f.text('Disable symmetry to edit red.' if locked else 'Base stats; formations, traits and terrain modify these.',(38,642),small=True)
        f.button('close_info','Cancel (Esc)' if self.adding else 'Close (Esc)',(755,642,155,30))

class DeploymentScreen:
    def __init__(self,config,path='battle_config.json',campaign_mode=False):
        self.campaign_mode=campaign_mode
        self.session=DeploymentSession(config)
        self.path=path
        self.form=Form((960,150))
        self.selected=None
        self.drag_offset=None
        self.facing_gesture=None
        self.ghost=None
        self.valid=True
        self.message='Select blue; RMB drag places and faces. LMB drag also places; Q/E rotate; Backspace resets.'
        self.action_requested=None
        self.officers=None
        self.refresh()

    def refresh(self):
        self.battle=self.session.config.create_battle()

    def attempt(self,**changes):
        if self.selected is None: return
        self.ghost=next(p for p in self.session.config.placements if p.id==self.selected)
        self.ghost=replace(self.ghost,**changes)
        try:
            self.session.edit(self.selected,**changes)
            self.valid=True; self.ghost=None; self.refresh(); self.message='Deployment updated.'
        except ConfigError as exc:
            self.valid=False; self.message=f'Placement rejected; previous position retained. {exc}'

    def button(self,key):
        if self.campaign_mode and key in ('save','load','officers'):return
        self.cancel_gesture()
        try:
            if key in ('start','back'): self.action_requested=key
            elif key=='reset':
                officers={p.id:p.commander for p in self.session.config.placements}
                self.session.config=replace(self.session.automatic,placements=tuple(replace(p,commander=officers[p.id]) for p in self.session.automatic.placements),commander_roll=self.session.config.commander_roll)
                self.ghost=None; self.refresh()
            elif key=='officers': self.officers=CommanderEditor(self.session.config,self.selected,self.session.automatic)
            elif key=='save': self.session.config.save(self.path); self.message=f'Saved deployment to {self.path}.'
            elif key=='load':
                self.session=DeploymentSession(BattleConfig.load(self.path)); self.selected=None; self.ghost=None; self.refresh()
                self.action_requested='fit'; self.message=f'Loaded {self.path}.'
        except (ConfigError,OSError) as exc: self.message=str(exc)

    def cancel_gesture(self):
        if self.facing_gesture is not None or self.drag_offset is not None:
            self.ghost=None
            self.valid=True
        self.facing_gesture=None
        self.drag_offset=None

    def preview_facing(self,event,camera):
        gesture=self.facing_gesture
        gesture.update(event.pos,camera)
        placement=next(p for p in self.session.config.placements if p.id==gesture.unit_id)
        self.ghost=replace(placement,pos=gesture.destination,facing=gesture.preview_facing)
        try:
            self.session.candidate(gesture.unit_id,pos=self.ghost.pos,facing=self.ghost.facing).validate(True)
            self.valid=True
        except ConfigError: self.valid=False

    def handle(self,event,camera):
        if self.officers is not None:
            self.officers.handle(event)
            if self.officers.closed:
                if self.officers.accepted:
                    self.session.config=self.officers.config
                    self.refresh();self.message='Commander assignments updated; deployment unchanged.'
                self.officers=None
            return
        if event.type==pygame.WINDOWFOCUSLOST: self.cancel_gesture()
        if event.type==pygame.MOUSEWHEEL: camera.zoom_at(pygame.mouse.get_pos(),1.15**event.y)
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==3:
            self.cancel_gesture()
            if self.selected is not None and 36<=event.pos[1]<camera.height-150:
                placement=next(p for p in self.session.config.placements if p.id==self.selected)
                self.facing_gesture=FacingGesture(self.selected,camera.screen_to_world(event.pos),event.pos,placement.facing)
                self.preview_facing(event,camera)
                self.message='Drag to aim the arrow; release RMB to place. Esc cancels. Red = invalid placement.'
        if event.type==pygame.MOUSEMOTION and self.facing_gesture is not None:
            self.preview_facing(event,camera)
        if event.type==pygame.MOUSEBUTTONUP and event.button==3 and self.facing_gesture is not None:
            self.preview_facing(event,camera)
            ghost=self.ghost
            self.facing_gesture=None
            if 0<=event.pos[0]<camera.width and 36<=event.pos[1]<camera.height-150:
                self.attempt(pos=ghost.pos,facing=ghost.facing)
            else:
                self.ghost=None; self.valid=True
                self.message='Placement cancelled; release over the battlefield to place.'
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            self.cancel_gesture()
            if event.pos[1]>=camera.height-150:
                hit=self.form.hit(event.pos)
                if hit: self.button(hit)
                return
            point=camera.screen_to_world(event.pos)
            unit=next((u for u in reversed(self.battle.units) if u.army==0 and contains(point,u.pos,u.facing,u.width,u.depth)),None)
            self.selected=unit.id if unit else None
            self.drag_offset=unit.pos-point if unit else None
            self.ghost=None
        if event.type==pygame.MOUSEMOTION and self.drag_offset is not None:
            placement=next(p for p in self.session.config.placements if p.id==self.selected)
            self.ghost=replace(placement,pos=camera.screen_to_world(event.pos)+self.drag_offset)
            try: self.session.candidate(self.selected,pos=self.ghost.pos).validate(True); self.valid=True
            except ConfigError: self.valid=False
        if event.type==pygame.MOUSEBUTTONUP and event.button==1:
            if self.drag_offset is not None and self.ghost: self.attempt(pos=self.ghost.pos)
            self.drag_offset=None
        if event.type==pygame.KEYDOWN:
            if event.key==pygame.K_o: self.button('officers');return
            if event.key==pygame.K_ESCAPE and (self.facing_gesture is not None or self.drag_offset is not None):
                self.cancel_gesture(); self.message='Placement cancelled.'; return
            if event.key in (pygame.K_RETURN,pygame.K_q,pygame.K_e,pygame.K_l,pygame.K_c,pygame.K_k,
                             pygame.K_h,pygame.K_a,pygame.K_t,pygame.K_r,pygame.K_s,pygame.K_BACKSPACE):
                self.cancel_gesture()
            if event.key==pygame.K_RETURN: self.button('start')
            elif event.key==pygame.K_ESCAPE: self.button('back')
            elif self.selected is not None:
                p=next(p for p in self.session.config.placements if p.id==self.selected)
                if event.key in (pygame.K_q,pygame.K_e): self.attempt(facing=p.facing+math.radians(15)*(1 if event.key==pygame.K_e else -1))
                if event.key in (pygame.K_l,pygame.K_c,pygame.K_k): self.attempt(formation={pygame.K_l:Formation.LINE,pygame.K_c:Formation.COLUMN,pygame.K_k:Formation.SKIRMISH}[event.key])
                orders={pygame.K_h:OrderKind.HOLD,pygame.K_a:OrderKind.ADVANCE,pygame.K_t:OrderKind.ATTACK,pygame.K_r:OrderKind.RESERVE,pygame.K_s:OrderKind.SKIRMISH,pygame.K_b:OrderKind.CHARGE}
                if event.key in orders:
                    kind=orders[event.key]
                    self.attempt(order=Order(kind,Vec(self.session.config.width/2,p.pos.y) if kind==OrderKind.ADVANCE else None))
                if event.key==pygame.K_BACKSPACE:
                    try: self.session.reset(self.selected); self.ghost=None; self.refresh(); self.message='Selected unit reset.'
                    except ConfigError as exc: self.message=str(exc)

    def draw(self,screen,camera,renderer,controls):
        controls.selected=self.selected
        config=self.session.config
        renderer.draw(self.battle,controls,present=False,zones=[config.zone(0),config.zone(1)])
        pygame.draw.rect(screen,(25,36,32),(0,0,screen.get_width(),36))
        renderer.hud.text(screen,f'DEPLOYMENT | seed {config.seed} | blue zone only',(14,10),big=True)
        if self.ghost:
            draw_ghost(screen,camera,self.ghost.regiment(),self.ghost.pos,self.ghost.facing,
                       (100,245,155) if self.valid else (255,75,65))
        f=self.form; f.canvas.fill((22,29,29)); f.buttons.clear()
        for key,label,x,width in [('back','Back to setup',10,160),('save','Save',185,100),('load','Load',300,100),('reset','Reset positions',415,125),('officers','Officers (O)',555,195),('start','Start battle',770,180)]:
            f.button(key,"Back to army" if key=="back" and self.campaign_mode else label,(x,8,width,32),not(self.campaign_mode and key in ("save","load","officers")))
        f.text('RMB drag: place + face | Q/E: rotate | L/C/K: formation | H/A/T/R/S: orders | B: charge',(10,50))
        unit=self.battle.unit(self.selected)
        f.text(f'#{unit.id} {unit.archetype.name} | {unit.formation.value} | {unit.order.kind.value}' if unit else 'Select a blue unit. Arrows pan; wheel zoom. Enter starts; Esc returns to setup.',(10,77))
        f.message(self.message,105)
        pygame.draw.rect(screen,(22,29,29),(0,screen.get_height()-150,screen.get_width(),150))
        f.present(screen,bottom=True)
        if self.officers is not None:self.officers.draw(screen)


class CommanderEditor:
    """Transactional deployment-only modal; edits immutable officer definitions."""
    def __init__(self,config,selected=None,defaults=None):
        self.config=config;self.defaults=defaults or config
        self.ids=[p.id for p in config.placements]
        self.index=self.ids.index(selected) if selected in self.ids else 0
        self.form=Form((960,640));self.closed=False;self.accepted=False
        self.message='Edits apply only after Apply. Both armies are editable; factions do not restrict assignment.'

    @property
    def placement(self):return self.config.placements[self.index]

    def assign(self,officer):
        p=self.placement
        candidate=replace(self.config,placements=tuple(replace(v,commander=officer) if v.id==p.id else v for v in self.config.placements))
        candidate.validate(True);self.config=candidate

    def action(self,key):
        try:
            if key=='cancel':self.closed=True
            elif key=='apply':self.config.validate(True);self.accepted=True;self.closed=True
            elif key in ('prev','next'):self.index=(self.index+(1 if key=='next' else -1))%len(self.ids)
            elif key=='reroll':self.config=self.config.reroll_commander(self.placement.id)
            elif key=='background':
                values=list(cmd.NAME_POOLS);current=self.placement.commander.background
                index=values.index(current) if current in values else -1
                self.config=self.config.reroll_commander(self.placement.id,values[(index+1)%len(values)])
                self.message='Background changed and selected commander rerolled. No faction assignment restrictions.'
            elif key=='reroll_army':
                army=self.placement.army
                for p in self.config.placements:
                    if p.army==army:self.config=self.config.reroll_commander(p.id)
            elif key=='reset':
                defaults={p.id:p.commander for p in self.defaults.placements}
                self.config=replace(self.config,placements=tuple(replace(p,commander=defaults.get(p.id,p.commander)) for p in self.config.placements))
            elif key.startswith('personality:'):
                self.assign(replace(self.placement.commander,personality=cmd.P(key.split(':')[1])))
            elif key.startswith('specialization:'):
                self.assign(replace(self.placement.commander,specialization=cmd.S(key.split(':')[1])))
        except (ConfigError,ValueError) as exc:self.message=str(exc)

    def handle(self,event):
        if event.type==pygame.KEYDOWN:
            if event.key==pygame.K_ESCAPE:self.action('cancel')
            elif event.key==pygame.K_RETURN:self.action('apply')
            elif event.key==pygame.K_LEFT:self.action('prev')
            elif event.key==pygame.K_RIGHT:self.action('next')
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            hit=self.form.hit(event.pos)
            if hit:self.action(hit)

    def draw(self,screen):
        f=self.form;f.canvas.fill((22,29,29));f.buttons.clear()
        p=self.placement;c=p.commander;unit=p.regiment()
        f.text('REGIMENT COMMANDERS — deployment only',(28,20),big=True)
        f.button('prev','< Regiment',(28,65,150,32));f.button('next','Regiment >',(782,65,150,32))
        label=f'{"BLUE" if p.army==0 else "RED"} #{p.id} | {unit.archetype.menu_name or unit.archetype.name} | {unit.stats.kind.value}'
        f.text(label,(198,72))
        f.text(c.display_name,(28,118),big=True)
        f.button('background','Cycle background + reroll',(670,111,262,32))
        f.text(f'Background: {c.background} | ID: {c.id}',(28,151),small=True)
        f.text(c.biography,(28,176),small=True)
        f.text('Personality — autonomous decisions; explicit orders take priority',(28,210))
        for i,personality in enumerate(cmd.P):
            label=cmd.PERSONALITIES[personality][0]
            f.button('personality:'+personality.value,('[x] ' if c.personality==personality else '')+label,(28+i*181,240,169,32))
        f.text(cmd.PERSONALITIES[c.personality][1],(28,282),small=True)
        f.text('Trade-off: '+cmd.PERSONALITIES[c.personality][2],(28,303),small=True)
        f.text('Specialization — only compatible roles are selectable',(28,339))
        for i,spec in enumerate(cmd.S):
            label=cmd.SPECIALIZATIONS[spec][0]
            f.button('specialization:'+spec.value,('[x] ' if c.specialization==spec else '')+label,
                     (28+(i%4)*230,370+(i//4)*40,218,32),spec in cmd.compatible(unit.stats.kind))
        f.text(cmd.SPECIALIZATIONS[c.specialization][2],(28,456),small=True)
        f.text('Trade-off: '+cmd.SPECIALIZATIONS[c.specialization][3],(28,479),small=True)
        f.button('reroll','Reroll selected',(28,515,190,32))
        f.button('reroll_army','Reroll this army',(234,515,190,32))
        f.button('reset','Scenario officers',(440,515,190,32))
        f.text(self.message,(28,559),small=True)
        f.button('cancel','Cancel (Esc)',(610,594,155,32))
        f.button('apply','Apply (Enter)',(780,594,155,32))
        f.present(screen)
