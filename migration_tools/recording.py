"""Incremental, opt-in recording observer. No Pygame or simulation RNG usage."""
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
from analysis.battle_report import battle_report

FORMAT = 'quiberon-battle-recording'
VERSION = 1


def plain(value):
    if isinstance(value, Enum): return value.value
    if is_dataclass(value): return plain(asdict(value))
    if isinstance(value, dict): return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [plain(v) for v in value]
    return value


def encoded(value):
    return (json.dumps(plain(value),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode('utf-8')


class BattleRecorder:
    """Attach once, call capture after every step, and close/context-manage.

    Events stream at emission even between snapshot ticks. Strong references to
    currently observed balls prevent recycled Python object IDs matching a new
    shot. The IDs/references live here, never on authoritative Projectile objects.
    """
    def __init__(self,battle,directory,scenario='custom',interval_ticks=1):
        if type(interval_ticks) is not int or interval_ticks<1:raise ValueError('interval_ticks must be a positive integer.')
        if battle.observer is not None:raise ValueError('Battle already has a recording observer.')
        self.battle=battle;self.path=Path(directory);self.interval=interval_ticks
        self.start_tick=battle.tick;self.last_tick=None;self.count=0;self.sequence=0;self.next_ball=0;self.balls={};self.closed=False
        # Refuse accidental overwrite/mixing with an existing recording.
        self.path.mkdir(parents=True,exist_ok=True)
        if any((self.path/name).exists() for name in ('metadata.json','frames.jsonl','events.jsonl','index.jsonl')):
            raise FileExistsError(f'Recording already exists: {self.path}. Use a new directory.')
        self.metadata=dict(format=FORMAT,version=VERSION,scenario=str(scenario),seed=str(battle.seed),
            world=dict(width=battle.rules.width,height=battle.rules.height,units='metres',y_axis='down',facing='clockwise_radians_from_positive_x',frontage_axis='local_y'),
            dt=battle.rules.dt,interval_ticks=interval_ticks,interval_seconds=interval_ticks*battle.rules.dt,
            start_time=battle.time,end_time=battle.time,start_tick=battle.tick,end_tick=battle.tick,frame_count=0,event_count=0,status='recording',result=None,
            files=dict(frames='frames.jsonl',index='index.jsonl',events='events.jsonl'),
            armies=[dict(id=a,name='Blue' if a==0 else 'Red' if a==1 else f'Army {a}',color=[90,156,238] if a==0 else [226,99,86]) for a in sorted(battle.initial_strength)],
            archetypes=[plain(next(u.archetype for u in battle.units if u.archetype.id==key)) for key in sorted({u.archetype.id for u in battle.units})],
            regiments=[dict(id=u.id,army=u.army,name=u.name,archetype=u.archetype.id,category=u.stats.kind.value,max_strength=u.stats.strength,
                initial_strength=u.strength,commander=u.commander.to_dict() if u.commander else None) for u in battle.units],
            terrain=battle.terrain.to_dict())
        self.frames=(self.path/'frames.jsonl').open('wb');self.index=(self.path/'index.jsonl').open('wb');self.events=(self.path/'events.jsonl').open('wb')
        try:
            self._metadata();battle.observer=self
            for p in battle.projectiles:self._ball_id(p)
            self.capture(force=True)
        except BaseException:
            self.close('incomplete');raise

    def _metadata(self):
        tmp=self.path/'metadata.json.tmp'
        tmp.write_text(json.dumps(plain(self.metadata),indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(self.path/'metadata.json')

    def _ball_id(self,p):
        key=id(p)
        if key not in self.balls:
            self.balls[key]=(p,self.next_ball);self.next_ball+=1
        return self.balls[key][1]

    def projectile(self,p):
        return dict(id=self._ball_id(p),type='cannonball',owner_id=p.owner_id,position=[p.pos.x,p.pos.y],height=p.height,
            ground=self.battle.terrain.get_elevation(p.pos.x,p.pos.y),velocity=[p.velocity.x,p.velocity.y],vertical_speed=p.vertical_speed,
            age=p.age,energy=p.energy,bounces=p.bounces)

    def emit(self,kind,position=None,**fields):
        self.events.write(encoded(dict(seq=self.sequence,time=self.battle.time,tick=self.battle.tick,kind=kind,position=position,**fields)))
        self.sequence+=1

    def event(self,event):
        u=self.battle.unit(event.unit_id)
        self.emit(event.kind,[u.pos.x,u.pos.y] if u else None,unit_id=event.unit_id,message=event.message,duration=3.)

    def effect(self,effect,unit_id=None):
        u=self.battle.unit(unit_id)
        kind=('artillery_fire' if u and u.stats.kind.value=='artillery' else 'volley') if effect.kind=='smoke' else effect.kind
        self.emit(kind,[effect.pos.x,effect.pos.y],unit_id=unit_id,facing=effect.facing,width=effect.width,duration=effect.expires-effect.started)

    def projectile_spawn(self,p):
        self.emit('projectile_spawn',[p.pos.x,p.pos.y],projectile=self.projectile(p),unit_id=p.owner_id,duration=0.)

    def capture(self,force=False):
        if self.closed:raise ValueError('Recording is closed.')
        b=self.battle
        if self.last_tick is not None and b.tick<=self.last_tick:
            if b.tick==self.last_tick:return
            raise ValueError('Simulation tick moved backwards during recording.')
        if force or b.result is not None or (b.tick-self.start_tick)%self.interval==0:
            units=[]
            for u in b.units:
                units.append(dict(id=u.id,position=[u.pos.x,u.pos.y],facing=u.facing,width=u.width,depth=u.depth,formation=u.formation.value,
                    strength=u.strength,morale=u.morale,cohesion=u.cohesion,state=u.state.value,combat_state=u.combat_state,
                    active=u.active,withdrawn=u.withdrawn,speed=u.speed,order=plain(u.order),target_id=u.target_id,
                    charge_state='charging' if u.infantry_charging else u.cavalry_state.value,charge_momentum=u.charge_momentum,
                    pursuit_id=u.pursuit_id,ai_state=u.ai_state))
            snapshot=dict(tick=b.tick,time=b.time,result=b.result,units=units,projectiles=[self.projectile(p) for p in b.projectiles])
            self.index.write(encoded(dict(tick=b.tick,time=b.time,offset=self.frames.tell())))
            self.frames.write(encoded(snapshot));self.count+=1;self.last_tick=b.tick
        active={id(p) for p in b.projectiles}
        self.balls={key:value for key,value in self.balls.items() if key in active}

    def close(self,status=None):
        if self.closed:return
        try:
            self.capture(force=True)
            self.metadata.update(end_tick=self.battle.tick,end_time=self.battle.time,frame_count=self.count,event_count=self.sequence,
                result=self.battle.result,status=status or ('complete' if self.battle.result else 'limit'),report=battle_report(self.battle))
            self.frames.flush();self.index.flush();self.events.flush();self._metadata()
        finally:
            self.closed=True
            if self.battle.observer is self:self.battle.observer=None
            self.frames.close();self.index.close();self.events.close();self.balls.clear()

    def __enter__(self):return self
    def __exit__(self,kind,value,traceback):self.close('incomplete' if kind else None)
