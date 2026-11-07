"""Campaign menus around the existing deployment, battle and results views."""
from dataclasses import replace
from pathlib import Path
import secrets
import pygame
from campaign.state import Campaign
from simulation import upgrades
from simulation.commanders import PERSONALITIES,SPECIALIZATIONS
from .setup import Form


class CampaignFlow:
    def __init__(self,app,path='saves/campaign.json',seed=None):
        self.app=app;self.path=Path(path);self.state=None;self.active=False
        self.form=Form((960,740));self.seed_text=str(secrets.randbits(63) if seed is None else seed)
        self.focus=False;self.message='Choose a mode. Campaign autosaves between battles.'
        self.selected=0;self.page=0;self.reward_id=None;self.commander_id=None;self.upgrade_id=None

    def commit(self,state):
        state.save(self.path) # write succeeds before replacing the in-memory transaction
        self.state=state

    def show_state(self):
        self.app.phase='reward' if self.state.status=='reward' else 'campaign_end' if self.state.status in ('victory','defeat') else 'campaign'
        self.selected=min(self.selected,max(0,len(self.state.army)-1));self.page=self.selected//8
        self.reward_id=None;self.commander_id=None;self.upgrade_id=None

    def start_battle(self,config):
        checkpoint=replace(self.state,encounter=config)
        self.state.validate_battle_recipe(config)
        running=checkpoint.start_battle()
        self.commit(checkpoint)
        self.state=running;self.app.start(config)

    def finish(self):
        self.commit(self.state.finish_battle(self.app.battle));self.show_state()

    def action(self,key):
        try:
            if key=='custom':self.active=False;self.app.phase='setup'
            elif key=='quit':self.app.running=False
            elif key=='menu':self.app.phase='menu';self.focus=False
            elif key=='new':
                if self.app.phase=='campaign_end':self.seed_text=str(secrets.randbits(63))
                seed=int(self.seed_text) if self.seed_text.strip() else secrets.randbits(63)
                self.commit(Campaign.new(seed));self.active=True;self.selected=0;self.show_state()
            elif key=='continue':
                state=Campaign.load(self.path);self.state=state;self.active=True;self.selected=0;self.show_state()
            elif key=='save':self.commit(self.state);self.message=f'Saved {self.path}.'
            elif key=='deploy':
                if self.state.status!='ready':raise ValueError('No campaign battle is ready.')
                self.app.deploy(self.state.encounter)
            elif key.startswith('unit:'):self.selected=int(key.split(':')[1])
            elif key.startswith('page:'):
                self.page=max(0,min((len(self.state.army)-1)//8,self.page+int(key.split(':')[1])))
            elif key.startswith('reward:'):
                self.reward_id=key.split(':',1)[1];self.commander_id=None;self.upgrade_id=None;self.page=0
            elif key.startswith('officer:'):self.commander_id=key.split(':',1)[1];self.upgrade_id=None
            elif key.startswith('upgrade:'):self.upgrade_id=key.split(':',1)[1]
            elif key=='claim':
                self.commit(self.state.claim(self.reward_id,self.commander_id,self.upgrade_id));self.show_state()
            self.message='Campaign updated.' if key not in ('save',) else self.message
        except (ValueError,OSError) as exc:self.message=str(exc)

    def handle(self,event):
        if event.type==pygame.KEYDOWN:
            if event.key==pygame.K_ESCAPE:self.action('menu')
            elif self.app.phase=='menu' and self.focus:
                if event.key==pygame.K_BACKSPACE:self.seed_text=self.seed_text[:-1]
                elif event.key==pygame.K_RETURN:self.action('new')
                elif getattr(event,'unicode','') in '-0123456789' and getattr(event,'unicode','') and len(self.seed_text)<21:self.seed_text+=event.unicode
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            if self.app.phase=='menu':self.focus=pygame.Rect(260,210,440,38).collidepoint(self.form.point(event.pos))
            hit=self.form.hit(event.pos)
            if hit:self.action(hit)

    def paragraph(self,text,x,y,width=410):
        f=self.form;line=''
        for word in str(text).split():
            if f.small.size((line+' '+word).strip())[0]>width and line:
                f.text(line,(x,y),small=True);y+=20;line=''
            line=(line+' '+word).strip()
        f.text(line,(x,y),small=True);return y+23

    def commander_details(self,r,x,y):
        c=r.commander
        y=self.paragraph(c.display_name,x,y)
        y=self.paragraph(PERSONALITIES[c.personality][0]+' | '+SPECIALIZATIONS[c.specialization][0],x,y)
        y=self.paragraph(PERSONALITIES[c.personality][1],x,y)
        y=self.paragraph(SPECIALIZATIONS[c.specialization][2],x,y)
        y=self.paragraph(f'Acquired upgrades: {len(c.upgrades)}/{self.state.rules.upgrade_limit}',x,y)
        for key in c.upgrades:
            d=upgrades.REGISTRY[key];y=self.paragraph(d.name+': '+d.description,x,y)
        return y

    def draw(self,screen):
        f=self.form;f.canvas.fill((22,32,29));f.buttons.clear()
        phase=self.app.phase
        if phase=='menu':
            f.text('QUIBERON — Battlefield & Campaign',(180,75),big=True)
            f.text('Five battles. Persistent armies. Commanders with growing abilities.',(180,125))
            f.text('New campaign seed (click to edit; blank = random)',(260,180),small=True)
            pygame.draw.rect(f.canvas,(55,75,65) if self.focus else (35,49,43),(260,210,440,38))
            f.text(self.seed_text or '(automatic)',(270,220))
            for key,label,y in [('custom','Custom Battle',290),('new','New Campaign (replaces save)',350),('continue','Continue Campaign',410),('quit','Quit',470)]:
                f.button(key,label,(260,y,440,44),key!='continue' or self.path.exists())
            f.text(f'Save: {self.path}',(180,550),small=True)
        elif phase=='reward':self.draw_rewards()
        else:
            state=self.state
            title=f'Battle {state.battle_number}/5 — {state.title}' if phase=='campaign' else 'CAMPAIGN COMPLETED' if state.status=='victory' else 'CAMPAIGN DEFEAT'
            f.text(title,(25,25),big=True)
            f.text(f'Seed {state.seed} | Battles won {state.wins}/5 | Total casualties {state.casualties}',(25,72))
            f.text(f'Army {len(state.army)}/{state.rules.max_army} | Strength {sum(r.strength for r in state.army)} | Retired commanders {len(state.retired)}',(25,104))
            for n in range(5):
                f.button('node:'+str(n),f'{n+1}: '+('Won' if n<state.wins else 'Next' if n==state.battle_number-1 else 'Later'),(25+n*184,137,172,28),False)
            for i,r in enumerate(state.army[self.page*8:(self.page+1)*8],self.page*8):
                y=185+(i%8)*52
                f.button(f'unit:{i}',('* ' if i==self.selected else '')+r.name,(25,y,420,27))
                f.text(f'{r.strength}/{r.maximum} | {r.commander.display_name}',(31,y+30),small=True)
            if state.army:self.commander_details(state.army[self.selected],490,190)
            f.button('page:-1','< Roster',(25,620,130,28),self.page>0)
            f.button('page:1','Roster >',(315,620,130,28),(self.page+1)*8<len(state.army))
            f.button('save','Save campaign',(25,689,180,35));f.button('menu','Main menu',(230,689,180,35))
            if phase=='campaign':f.button('deploy','Deploy for next battle',(660,689,275,35))
            else:f.button('new','Start new run',(660,689,275,35))
        f.message(self.message,650 if phase!='menu' else 600)
        screen.fill((16,23,21));f.present(screen)

    def draw_rewards(self):
        f=self.form;s=self.state
        f.text(f'Victory {s.wins}/5 — choose ONE reward',(25,24),big=True)
        f.text(f'Survivors already recovered {s.rules.automatic_replenishment:.0%} of missing strength. Confirm one choice below.',(25,70),small=True)
        for i,reward in enumerate(s.rewards):
            x=25+i*310;f.button('reward:'+reward.id,('* ' if reward.id==self.reward_id else '')+reward.label,(x,110,290,42))
            if reward.kind=='recruit':
                r=reward.recruit;text=f'{r.name} | {r.strength} troops. {r.commander.display_name}; {PERSONALITIES[r.commander.personality][0]}, {SPECIALIZATIONS[r.commander.specialization][0]}.'
            elif reward.kind=='upgrade':text='Select an officer, then one of the three compatible offers. Personality and starting specialization stay intact.'
            elif reward.kind=='replenish':
                gain=sum(r.replenish(reward.fraction).strength-r.strength for r in s.army if reward.target_id in (None,r.id))
                text=f'Restores {gain} troops'+(' across the army.' if reward.target_id is None else ' to this regiment.')
            else:text='Every regiment is full and all progression slots are filled. Proceed to the next encounter.'
            self.paragraph(text,x,165,280)
        reward=next((r for r in s.rewards if r.id==self.reward_id),None);valid=reward is not None
        if reward and reward.kind=='upgrade':
            eligible=dict(reward.choices)
            officers=[r for r in s.army if r.commander.id in eligible]
            last=max(0,(len(officers)-1)//8);self.page=min(self.page,last)
            for i,r in enumerate(officers[self.page*8:(self.page+1)*8]):
                f.button('officer:'+r.commander.id,('* ' if self.commander_id==r.commander.id else '')+r.commander.display_name,(25,295+i*33,405,29))
            f.button('page:-1','< Officers',(25,585,150,28),self.page>0)
            f.button('page:1','Officers >',(280,585,150,28),self.page<last)
            r=next((r for r in s.army if r.commander.id==self.commander_id),None)
            if r:
                existing=', '.join(upgrades.REGISTRY[k].name for k in r.commander.upgrades) or 'No acquired upgrades'
                self.paragraph('Existing: '+existing,460,260,465)
                f.text(PERSONALITIES[r.commander.personality][0]+' | '+SPECIALIZATIONS[r.commander.specialization][0],(460,300),small=True)
                y=330
                for key in eligible[r.commander.id]:
                    d=upgrades.REGISTRY[key]
                    f.button('upgrade:'+key,('* ' if self.upgrade_id==key else '')+d.name,(460,y,465,30))
                    y=self.paragraph(d.description,465,y+35,450)+15
            valid=r is not None and self.upgrade_id in eligible.get(self.commander_id,())
        f.button('menu','Main menu',(25,689,180,35));f.button('save','Save choices',(230,689,180,35))
        f.button('claim','Confirm reward',(700,689,235,35),valid)
