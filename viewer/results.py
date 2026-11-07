"""Frozen, paginated post-battle statistics; no writes to live simulation state."""
import pygame
from analysis.battle_report import battle_report
from .setup import Form


class BattleResults:
    PAGE_SIZE=8

    def __init__(self,battle,campaign=False):
        self.campaign=campaign
        self.message=""
        self.report=battle_report(battle)
        self.form=Form((960,740))
        self.grouped=False
        self.army=None
        self.page=0
        self.sort='casualties_inflicted'

    def rows(self):
        rows=self.report['archetypes' if self.grouped else 'regiments']
        rows=[r for r in rows if self.army is None or r['army']==self.army]
        return sorted(rows,key=lambda r:(-r[self.sort],r['army'],r.get('id',0),r['label']))

    def action(self,key):
        if key=='continue' and self.campaign:return key
        if key in ('restart','rematch','setup') and self.campaign:return None
        if key in ('restart','rematch','setup','close'): return key
        if key.startswith('view:'): self.grouped=key=='view:archetypes'; self.page=0
        elif key.startswith('army:'): self.army=None if key=='army:all' else int(key.split(':')[1]); self.page=0
        elif key.startswith('page:'):
            last=max(0,(len(self.rows())-1)//self.PAGE_SIZE)
            self.page=max(0,min(last,self.page+int(key.split(':')[1])))
        elif key.startswith('sort:'): self.sort=key.split(':')[1]; self.page=0

    def handle(self,event):
        if event.type==pygame.KEYDOWN:
            if self.campaign and event.key==pygame.K_RETURN: return 'continue'
            if event.key in (pygame.K_ESCAPE,pygame.K_TAB): return 'close'
            if event.key in (pygame.K_PAGEDOWN,pygame.K_DOWN): self.action('page:1')
            if event.key in (pygame.K_PAGEUP,pygame.K_UP): self.action('page:-1')
        elif event.type==pygame.MOUSEWHEEL: self.action('page:'+str(-event.y))
        elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            key=self.form.hit(event.pos)
            if key: return self.action(key)

    def draw(self,screen):
        f=self.form; data=self.report; f.canvas.fill((22,32,29)); f.buttons.clear()
        result=data['result']
        title='Draw' if result=='draw' else 'Blue victory' if result=='army_0' else 'Red victory' if result=='army_1' else 'Battle statistics'
        f.text(title+' — Battle report',(25,22),big=True)
        seconds=data['duration']
        f.text(f'{int(seconds//60):02d}:{seconds%60:04.1f} elapsed | seed {data["seed"]} | {data["width"]:g} × {data["height"]:g} m',(25,65))
        for i,army in enumerate(data['armies']):
            x=25+i*470
            pygame.draw.rect(f.canvas,(34,49,45),(x,103,440,166),border_radius=5)
            color=(125,185,255) if army['army']==0 else (245,145,125)
            f.text('Blue army' if army['army']==0 else 'Red army',(x+14,114),color,True)
            f.text(f'Started {army["initial"]} | Survived {army["remaining"]} | Lost {army["lost"]}',(x+14,151))
            f.text(f'Effective {army["effective"]} | Destroyed units {army["destroyed"]}',(x+14,179))
            f.text(f'Routs {army["rout_events"]} | Rallies {army["rallies"]} | Withdrawn {army["withdrawn"]}',(x+14,207))
            f.text(f'Volleys {army["volleys"]} | Charges {army["charges"]}',(x+14,235))
        metrics=data['metrics']
        f.text(f'Friendly-fire incidents {metrics["friendly_fire"]} | Cascade shocks {metrics["cascade_shocks"]} | Rout transitions {metrics["routs"]}',(25,284))
        f.button('view:regiments',('* ' if not self.grouped else '')+'Regiments',(25,321,180,31))
        f.button('view:archetypes',('* ' if self.grouped else '')+'Archetypes',(215,321,180,31))
        for i,(value,label) in enumerate((('all','Both armies'),('0','Blue'),('1','Red'))):
            selected=self.army is None if value=='all' else self.army==int(value)
            f.button('army:'+value,('* ' if selected else '')+label,(505+i*145,321,135,31))
        f.text('Regiment / archetype',(25,368))
        f.text('Side',(336,368))
        f.text('Start',(400,368))
        for key,label,x in (('remaining','Left',462),('lost','Lost',525),('casualties_inflicted','Caused',588),('volleys','Volleys',679),('charges','Charges',760)):
            f.button('sort:'+key,label,(x,363,78 if key=='casualties_inflicted' else 65,28))
        f.text('Status',(839,368))
        rows=self.rows(); last=max(0,(len(rows)-1)//self.PAGE_SIZE); self.page=min(self.page,last)
        for i,row in enumerate(rows[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE]):
            y=405+i*26
            if i%2==0: pygame.draw.rect(f.canvas,(30,43,38),(22,y-2,915,25))
            label=row['label']
            while f.font.size(label)[0]>300: label=label[:-4]+'...'
            f.text(label,(25,y))
            f.text('Blue' if row['army']==0 else 'Red',(336,y),(125,185,255) if row['army']==0 else (245,145,125))
            for key,x in (('initial',400),('remaining',462),('lost',525),('casualties_inflicted',588),('volleys',679),('charges',760)):
                f.text(f'{row[key]:g}',(x+3,y))
            f.text(row['status'],(839,y),small=True)
        f.button('page:-1','< Previous',(25,620,150,30),self.page>0)
        f.text(f'Page {self.page+1}/{last+1} | {len(rows)} entries',(200,627))
        f.button('page:1','Next >',(485,620,120,30),self.page<last)
        f.text('Lost = casualties; survivors include routed/withdrawn troops. Caused includes friendly fire.',(25,658),small=True)
        if self.message:f.message(self.message,668)
        buttons=(('close','Tab: Battlefield',25,205),('continue','Continue campaign',635,300)) if self.campaign else (('close','Tab: Battlefield',25,205),('restart','F5 Restart',260,185),('rematch','F6 New seed',475,200),('setup','F7 Edit setup',705,230))
        for key,label,x,w in buttons:
            f.button(key,label,(x,693,w,33))
        screen.fill((16,23,21)); f.present(screen)
