"""Setup → frozen deployment preview → fresh running battle; restart uses recipes."""
from time import perf_counter
from dataclasses import replace
import pygame
from scenarios.battle_config import ConfigError
from scenarios.presets import PRESETS, load_preset
from .camera import Camera
from .controls import Controls
from .renderer import Renderer
from .interpolation import MotionFrame
from .setup import SetupScreen, DeploymentScreen
from .results import BattleResults

class Application:
    def __init__(self,screen,config=None,path='battle_config.json',legacy_factory=None,legacy_seed=1, clock=perf_counter):
        self.screen=screen
        self.camera=Camera(width=screen.get_width(),height=screen.get_height())
        self.controls=Controls()
        self.renderer=Renderer(screen,self.camera)
        self.setup=SetupScreen(config,path)
        self.deployment=None
        self.start_config=None
        self.battle=None
        self.phase='setup'
        self.running=True
        self.accumulator=0.
        self.clock=clock
        self.step_budget=.008  # Approximate 8 ms; one indivisible tick can overrun.
        self.max_steps=4
        self.motion=None
        self._rate_wall=0.
        self._rate_sim=0.
        self._rate_slow=False
        self._reported_slow=False
        self.legacy_factory=legacy_factory
        self.legacy_seed=legacy_seed
        self.legacy_commanders=None
        self.toolbar={}
        self.results=None
        self.results_visible=False
        self.campaign_flow=None
        if legacy_factory: self.restart()

    @property
    def in_campaign(self):
        return self.campaign_flow is not None and self.campaign_flow.active

    def open_menu(self,path=None,seed=None):
        if self.campaign_flow is None:
            from .campaign import CampaignFlow
            self.campaign_flow=CampaignFlow(self,path or "saves/campaign.json",seed)
        self.phase="menu"

    def reset_timing(self):
        self.accumulator=0.
        self._rate_wall=self._rate_sim=0.
        self._rate_slow=False
        self._reported_slow=False
        self.controls.actual_speed=None
        self.controls.slow=False
        self.controls.backlog=0.
        self.motion=MotionFrame(self.battle) if self.phase=='battle' else None
        self.renderer.unit_poses={}
        self.results=None
        self.results_visible=False

    def ensure_results(self):
        if self.battle and self.battle.result is not None and self.results is None:
            self.results=BattleResults(self.battle,campaign=self.in_campaign)
            self.results_visible=True
            self.controls.cancel_command()

    def fit(self):
        self.camera.width,self.camera.height=self.screen.get_size()
        battle=self.deployment.battle if self.phase=='deployment' else self.battle
        self.camera.fit(battle.rules.width,battle.rules.height)

    def deploy(self,config):
        self.deployment=DeploymentScreen(config,self.setup.path,campaign_mode=self.in_campaign)
        self.phase='deployment'
        self.controls=Controls(); self.controls.paused=True
        self.reset_timing()
        self.fit()

    def start(self,config):
        self.start_config=config.prepared()
        self.legacy_factory=None
        self.battle=self.start_config.create_battle()
        self.phase='battle'
        self.controls=Controls(); self.controls.campaign=self.in_campaign; self.reset_timing()
        self.fit()

    def restart(self,new_seed=False):
        if self.in_campaign: return
        if self.legacy_factory:
            if new_seed: self.legacy_seed=load_preset(PRESETS[0]).new_seed().seed
            self.battle=self.legacy_factory(self.legacy_seed)
            if self.legacy_commanders is None:
                self.legacy_commanders={(u.id,u.stats.kind):u.commander for u in self.battle.units}
            else:
                for u in self.battle.units:
                    if (u.id,u.stats.kind) in self.legacy_commanders:
                        u.commander=self.legacy_commanders[u.id,u.stats.kind]
            self.phase='battle'; self.controls=Controls(); self.reset_timing(); self.fit()
        elif self.start_config:
            self.start(self.start_config.new_seed() if new_seed else self.start_config)

    def edit_setup(self):
        if self.in_campaign:
            if self.phase!="deployment":return
            try:
                config=self.deployment.session.config
                self.campaign_flow.state.validate_battle_recipe(config)
                self.campaign_flow.commit(replace(self.campaign_flow.state,encounter=config))
                self.campaign_flow.show_state()
            except (ValueError,OSError) as exc:self.deployment.message=str(exc)
            return
        config=self.deployment.session.config if self.phase=='deployment' else self.start_config
        self.setup=SetupScreen(config or load_preset(PRESETS[0]),self.setup.path)
        self.phase='setup'; self.reset_timing()

    def handle(self,event):
        if event.type==pygame.QUIT: self.running=False; return
        self.camera.width,self.camera.height=self.screen.get_size()
        if self.phase in ('menu','campaign','reward','campaign_end'):
            self.campaign_flow.handle(event); return
        if self.phase=='setup':
            self.setup.handle(event)
            if self.setup.menu_requested:
                self.setup.menu_requested=False; self.open_menu(); return
            if self.setup.quit: self.running=False
            if self.setup.next_config:
                self.deploy(self.setup.next_config); self.setup.next_config=None
        elif self.phase=='deployment':
            if event.type==pygame.KEYDOWN and event.key==pygame.K_F3: self.controls.debug=not self.controls.debug
            if event.type==pygame.KEYDOWN and event.key==pygame.K_F2: self.controls.contours=not self.controls.contours
            self.deployment.handle(event,self.camera)
            action=self.deployment.action_requested
            self.deployment.action_requested=None
            if action=='back': self.edit_setup()
            elif action=='fit': self.fit()
            elif action=='start':
                try:
                    if self.in_campaign: self.campaign_flow.start_battle(self.deployment.session.config)
                    else: self.start(self.deployment.session.config)
                except (ValueError,OSError) as exc: self.deployment.message=str(exc)
        else:
            self.ensure_results()
            action=None
            if event.type==pygame.KEYDOWN:
                action={pygame.K_F5:'restart',pygame.K_F6:'rematch',pygame.K_F7:'setup'}.get(event.key)
            if self.results is not None and event.type==pygame.KEYDOWN and event.key==pygame.K_TAB and not self.results_visible:
                self.results_visible=True; return
            if self.in_campaign and action in ('restart','rematch','setup'): return
            if action is None and self.results_visible:
                action=self.results.handle(event)
                if action=='close': self.results_visible=False; return
                if action is None: return
            if not self.results_visible and event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                action=next((key for key,rect in self.toolbar.items() if rect.collidepoint(event.pos)),None)
            if action=='continue' and self.in_campaign:
                try: self.campaign_flow.finish()
                except (ValueError,OSError) as exc: self.results.message=str(exc)
            elif action=='restart': self.restart()
            elif action=='rematch': self.restart(True)
            elif action=='setup': self.edit_setup()
            elif action=='results': self.results_visible=True
            else:
                paused=self.controls.paused
                self.controls.handle(event,self.battle,self.camera,poses=self.renderer.unit_poses)
                if paused!=self.controls.paused: self.motion.capture(self.battle)
                self.running=self.controls.running

    def update(self,elapsed):
        wall_elapsed=max(0.,elapsed)
        elapsed=min(.25,wall_elapsed)
        if self.phase in ('battle','deployment'): self.controls.pan(self.camera,elapsed)
        if self.phase!='battle': return
        if self.controls.paused or self.battle.result is not None:
            self.motion.capture(self.battle)
            self._rate_wall=self._rate_sim=0.
            self._rate_slow=self._reported_slow=False
            self.controls.actual_speed=None
            self.controls.slow=False
            return
        self.accumulator+=wall_elapsed*self.controls.speed
        start=self.clock(); steps=0
        while self.accumulator+1e-9>=self.battle.rules.dt and steps<self.max_steps:
            if steps and self.clock()-start>=self.step_budget: break
            self.motion.capture(self.battle)
            self.battle.step()
            self.accumulator=max(0.,self.accumulator-self.battle.rules.dt)
            steps+=1
            if self.battle.result is not None: break
        slow=self.accumulator+1e-9>=self.battle.rules.dt and self.battle.result is None
        # Retain all outstanding simulated time. The budget limits UI latency,
        # not the amount of time requested; the HUD exposes overload/backlog.
        self.controls.backlog=self.accumulator if slow else 0.
        self._rate_slow|=slow
        self.controls.slow=slow or self._reported_slow
        self._rate_wall+=wall_elapsed
        self._rate_sim+=steps*self.battle.rules.dt
        if self._rate_wall>=.5:
            self.controls.actual_speed=self._rate_sim/self._rate_wall
            self._reported_slow=self._rate_slow
            self.controls.slow=self._reported_slow
            self._rate_wall=self._rate_sim=0.
            self._rate_slow=False

    def draw(self,fps=0):
        if self.phase in ('menu','campaign','reward','campaign_end'): self.campaign_flow.draw(self.screen)
        elif self.phase=='setup': self.setup.draw(self.screen)
        elif self.phase=='deployment': self.deployment.draw(self.screen,self.camera,self.renderer,self.controls)
        else:
            self.ensure_results()
            if self.results_visible:
                self.results.draw(self.screen)
                pygame.display.flip()
                return
            alpha=1. if self.controls.paused or self.battle.result is not None else min(1.,self.accumulator/self.battle.rules.dt)
            self.renderer.draw(self.battle,self.controls,fps,present=False,motion=self.motion,alpha=alpha)
            self.toolbar.clear()
            labels=[] if self.in_campaign else [('restart','F5 Restart'),('rematch','F6 New seed'),('setup','F7 Edit setup')]
            width=min(420,self.screen.get_width()//2)
            for i,(key,label) in enumerate(labels):
                rect=pygame.Rect(self.screen.get_width()-width+i*width//3,36,width//3-3,28)
                self.toolbar[key]=rect
                pygame.draw.rect(self.screen,(40,65,57),rect)
                font=self.renderer.hud.font
                self.screen.blit(font.render(label,True,(240,235,205)),rect.move(5,7))
            if self.results is not None:
                rect=pygame.Rect(self.screen.get_width()-180,71,175,28)
                self.toolbar['results']=rect
                pygame.draw.rect(self.screen,(40,65,57),rect)
                self.screen.blit(self.renderer.hud.font.render('Tab: Battle statistics',True,(240,235,205)),rect.move(5,7))
        pygame.display.flip()
