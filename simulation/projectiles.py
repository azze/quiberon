"""Cannonballs use absolute world elevation; regiments remain 2D footprints."""
from dataclasses import dataclass, field
import math
from .geometry import Vec, segment_rect, direction
from . import commanders

@dataclass
class Projectile:
    pos: Vec
    velocity: Vec
    height: float
    vertical_speed: float
    owner_id: int
    age: float = 0.
    energy: float = 1.
    bounces: int = 0
    hit_ids: set[int] = field(default_factory=set)


def launch_salvo(battle,unit,target):
    """One independent ballistic shot per crew-supported gun, one reload cycle."""
    count=unit.available_guns
    side=direction(unit.facing+math.pi/2)
    for i in range(count):
        origin=unit.pos+side*(((i+.5)/count-.5)*unit.width*.8)
        launch(battle,unit,target,origin)
    unit.analysis['artillery_shots']+=count


def launch(battle, unit, target, origin=None):
    """Single gun primitive, also used by focused ballistics tests."""
    origin=unit.pos if origin is None else origin
    cover=battle.terrain.movement_effect(unit,Vec(0,0),battle.rules.terrain).forest if not battle.terrain.empty else 0.
    # Wider normal-range scatter must not aim behind a gun at point-blank range.
    scatter=min(battle.rules.artillery_scatter*(1+cover),(target.pos-origin).length()*.5)*commanders.scatter_factor(unit)
    aim=target.pos+Vec(battle.rng.uniform(-scatter,scatter),battle.rng.uniform(-scatter,scatter))
    distance=(aim-origin).length()
    speed=100.; flight=max(.1,distance/speed)
    start_z=battle.terrain.get_elevation(origin.x,origin.y)+1.2
    target_z=battle.terrain.get_elevation(aim.x,aim.y)
    vz=(target_z-start_z+.5*battle.rules.gravity*flight*flight)/flight
    # Preserve the original flat-field near-range muzzle behaviour.
    if battle.terrain.empty: vz=max(0.,vz)
    # An independent gun elevation error makes some shots graze/bounce early
    # and others loft over the aim point. Terrain collision remains authoritative.
    if battle.rules.artillery_vertical_scatter>0:
        spread=battle.rules.artillery_vertical_scatter*commanders.scatter_factor(unit)
        vz+=battle.rng.uniform(-spread,spread)
    p=Projectile(origin,(aim-origin).normalized()*speed,start_z,vz,unit.id,energy=unit.archetype.projectile_power)
    battle.projectiles.append(p)
    if battle.observer is not None:battle.observer.projectile_spawn(p)


def advance_piece(battle,p,dt,terrain_enabled):
    from .combat import damage
    terrain=battle.terrain; gravity=battle.rules.gravity
    old,old_z=p.pos,p.height
    velocity,vertical=p.velocity,p.vertical_speed
    end=old+velocity*dt
    end_z=old_z+vertical*dt-.5*gravity*dt*dt
    ground=terrain.get_elevation(end.x,end.y)
    collision=end_z<=ground
    fraction=1.
    if collision and terrain_enabled:
        # Clip to the first surface impact before testing footprints behind it.
        lo,hi=0.,1.
        for _ in range(16):
            t=(lo+hi)/2; point=old+velocity*(dt*t)
            z=old_z+vertical*dt*t-.5*gravity*(dt*t)**2
            if z<=terrain.get_elevation(point.x,point.y): hi=t
            else: lo=t
        fraction=hi
        end=old+velocity*(dt*fraction)
        ground=terrain.get_elevation(end.x,end.y)
        end_z=ground
    p.pos=end; p.height=end_z
    p.vertical_speed=vertical-gravity*dt*fraction
    hits=[]
    for unit in battle.units:
        if not unit.active or unit.id==p.owner_id or unit.id in p.hit_ids: continue
        entry=segment_rect(old,end,unit)
        if entry is None: continue
        point=old+(end-old)*entry
        base=terrain.get_elevation(point.x,point.y)
        z=old_z+(end_z-old_z)*entry
        if z<=base+3: hits.append((entry,unit.id,unit))
    for _,_,unit in sorted(hits):
        losses=int(battle.rng.uniform(5,13)*p.energy*(.75 if unit.formation.value=='skirmish' else 1.))
        damage(battle,unit,losses,'cannonball',battle.unit(p.owner_id),shock=5*p.energy)
        p.hit_ids.add(unit.id); p.energy*=.75
        battle.effect('impact',unit.pos,.8)
    if terrain_enabled and terrain.forests:
        middle=(old+end)*.5
        if (old_z+end_z)/2 < terrain.get_elevation(middle.x,middle.y)+battle.rules.terrain.canopy_height:
            density=terrain.forest_density(middle.x,middle.y)
            p.energy*=math.exp(-density*(end-old).length()*battle.rules.terrain.projectile_forest_drag)
    if collision:
        p.height=ground+(.01 if terrain_enabled else 0.)
        gradient=terrain.gradient(end.x,end.y)
        norm=math.sqrt(1+gradient.dot(gradient))
        nx,ny,nz=-gradient.x/norm,-gradient.y/norm,1/norm
        dot=p.velocity.x*nx+p.velocity.y*ny+p.vertical_speed*nz
        if dot<0:
            p.velocity=p.velocity*.78-Vec(nx,ny)*(1.26*dot)
            p.vertical_speed=p.vertical_speed*.78-nz*1.26*dot
        else:
            p.velocity=p.velocity*.78; p.vertical_speed=abs(p.vertical_speed)*.48
        p.energy*=.72; p.bounces+=1
        battle.effect('impact',p.pos,1.)


def update(battle):
    dt=battle.rules.dt; terrain=battle.terrain
    survivors=[]
    for p in battle.projectiles:
        pieces=1
        if not terrain.empty:
            step=terrain.sample_step(battle.rules.terrain.projectile_step)
            pieces=max(1,math.ceil(p.velocity.length()*dt/step),math.ceil(dt/.025))
        p.age+=dt
        for _ in range(pieces):
            advance_piece(battle,p,dt/pieces,not terrain.empty)
            if p.bounces>=5 or p.energy<=.15: break
        if p.age<battle.rules.projectile_lifetime and p.bounces<5 and p.energy>.15 and -50<p.pos.x<battle.rules.width+50 and -50<p.pos.y<battle.rules.height+50:
            survivors.append(p)
    battle.projectiles=survivors
