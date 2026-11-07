"""World-space analytic terrain. Heights are metres; slopes are rise/run."""
from dataclasses import dataclass, asdict, field
from collections import OrderedDict
import math
import random
from .geometry import Vec
from . import commanders

TERRAIN_PRESETS = ('Open Field','Central Hill','Rolling Hills','Wooded Battlefield','Mixed Terrain','Ridge Defence')

@dataclass(frozen=True)
class Hill:
    x: float
    y: float
    radius_x: float
    radius_y: float
    height: float
    compact: bool = False  # Smooth finite support for newly generated maps.

    def elevation(self,x,y):
        if self.compact:
            p=max(0.,1-(((x-self.x)/self.radius_x)**2+((y-self.y)/self.radius_y)**2)/9)
            return self.height*p**4
        return self.height*math.exp(-.5*(((x-self.x)/self.radius_x)**2+((y-self.y)/self.radius_y)**2))

    def gradient(self,x,y):
        if self.compact:
            p=max(0.,1-(((x-self.x)/self.radius_x)**2+((y-self.y)/self.radius_y)**2)/9)
            factor=-8*self.height*p**3/9
            return Vec(factor*(x-self.x)/self.radius_x**2,factor*(y-self.y)/self.radius_y**2)
        z=self.elevation(x,y)
        return Vec(-z*(x-self.x)/self.radius_x**2,-z*(y-self.y)/self.radius_y**2)

@dataclass(frozen=True)
class Forest:
    x: float
    y: float
    radius_x: float
    radius_y: float
    density: float = 1.

    def cover(self,x,y):
        dx,dy=x-self.x,y-self.y
        if abs(dx)>=self.radius_x or abs(dy)>=self.radius_y: return 0.
        radius=math.hypot(dx/self.radius_x,dy/self.radius_y)
        t=max(0.,min(1.,(1-radius)/.2))
        return self.density*t*t*(3-2*t)

@dataclass(frozen=True)
class TerrainProfile:
    forest_slowdown: float
    forest_loss: float  # cohesion per metre travelled in full-density forest
    uphill: float
    slope_loss: float
    route_aversion: float

@dataclass(frozen=True)
class TerrainRules:
    infantry: TerrainProfile = TerrainProfile(.35,.10,4.,.8,0.)
    cavalry: TerrainProfile = TerrainProfile(.65,.25,5.,1.4,1.)
    artillery: TerrainProfile = TerrainProfile(.75,.18,8.,1.,1.4)
    min_speed: float = .2
    max_downhill_speed: float = 1.12
    column_forest_factor: float = .55
    forest_visibility_depth: float = 75.
    forest_accuracy_depth: float = 60.
    canopy_height: float = 12.
    sight_step: float = 4.
    observer_height: float = 1.7
    projectile_step: float = 2.
    projectile_forest_drag: float = .008
    steep_grade: float = .15
    slope_disruption_start: float = .05
    forest_fire_penalty: float = .45
    forest_cover_protection: float = .60
    forest_cover_depth: float = 4.
    forest_firing_depth: float = 40.
    forest_melee_penalty: float = .45
    woodland_composure: float = .95
    woodland_skill_cover: float = .40
    uphill_melee_penalty: float = 2.
    charge_slope_penalty: float = 5.
    charge_downhill_bonus: float = .15
    charge_forest_penalty: float = .8

    def woodland_skill(self,cover):
        """Light woods already support woodland tactics; fade smoothly at edges."""
        return max(0.,min(1.,cover/max(.01,self.woodland_skill_cover)))

@dataclass(frozen=True)
class Visibility:
    visible: bool = True
    transmission: float = 1.
    vegetation: float = 0.
    reason: str = 'clear'

    @property
    def state(self): return 'hidden' if not self.visible else 'obscured' if self.transmission < .9 else 'clear'

@dataclass(frozen=True)
class TerrainEffect:
    speed: float = 1.
    loss_per_metre: float = 0.
    forest: float = 0.
    slope: float = 0.
    grade: float = 0.

@dataclass(frozen=True)
class TerrainMap:
    width: float = 1000.
    height: float = 600.
    hills: tuple[Hill,...] = ()
    forests: tuple[Forest,...] = ()
    preset: str = 'Open Field'
    seed: int = 0
    _footprint_cache: dict = field(default_factory=OrderedDict,compare=False,repr=False)
    _hill_cells: dict | None = field(default=None,init=False,compare=False,repr=False)
    _forest_cells: dict | None = field(default=None,init=False,compare=False,repr=False)
    _global_hills: tuple = field(default=(),init=False,compare=False,repr=False)
    _global_forests: tuple = field(default=(),init=False,compare=False,repr=False)

    def __post_init__(self):
        # Exact static candidates. Legacy infinite Gaussian hills stay global;
        # generated compact hills and forests have finite, smooth support.
        for name,features,kind in (('hill',self.hills,Hill),('forest',self.forests,Forest)):
            if len(features)<=16 or not all(isinstance(f,kind) and all(math.isfinite(v) for v in
                    (f.x,f.y,f.radius_x,f.radius_y)) and min(f.radius_x,f.radius_y)>=1 for f in features): continue
            cells={};global_items=[]
            for i,f in enumerate(features):
                if type(f) is not kind or (kind is Hill and not f.compact):
                    global_items.append((i,f));continue
                extent=3. if kind is Hill else 1.
                left,right=math.floor((f.x-extent*f.radius_x)/200),math.floor((f.x+extent*f.radius_x)/200)
                top,bottom=math.floor((f.y-extent*f.radius_y)/200),math.floor((f.y+extent*f.radius_y)/200)
                if (right-left+1)*(bottom-top+1)>4096:
                    global_items.append((i,f));continue
                for x in range(left,right+1):
                    for y in range(top,bottom+1):cells.setdefault((x,y),[]).append((i,f))
            object.__setattr__(self,f'_{name}_cells',{cell:tuple(f for _,f in sorted(items+global_items)) for cell,items in cells.items()})
            object.__setattr__(self,f'_global_{name}s',tuple(f for _,f in global_items))

    @property
    def empty(self): return not self.hills and not self.forests

    def get_elevation(self,x: float,y: float) -> float:
        # Preserve both expression order and Python's float sum semantics.
        hills=self.hills if self._hill_cells is None else self._hill_cells.get((math.floor(x/200),math.floor(y/200)),self._global_hills)
        return sum((h.height*math.exp(-.5*(((x-h.x)/h.radius_x)**2+((y-h.y)/h.radius_y)**2))
                    if type(h) is Hill and not h.compact else h.elevation(x,y) for h in hills),0.)

    def gradient(self,x: float,y: float) -> Vec:
        gx=gy=0.
        hills=self.hills if self._hill_cells is None else self._hill_cells.get((math.floor(x/200),math.floor(y/200)),self._global_hills)
        for hill in hills:
            if hill.compact:
                p=max(0.,1-(((x-hill.x)/hill.radius_x)**2+((y-hill.y)/hill.radius_y)**2)/9)
                factor=-8*hill.height*p**3/9
                gx+=factor*(x-hill.x)/hill.radius_x**2;gy+=factor*(y-hill.y)/hill.radius_y**2
                continue
            z=hill.elevation(x,y)
            gx+=-z*(x-hill.x)/hill.radius_x**2
            gy+=-z*(y-hill.y)/hill.radius_y**2
        return Vec(gx,gy)

    def slope(self,x: float,y: float) -> float: return self.gradient(x,y).length()
    def forest_density(self,x: float,y: float) -> float:
        density=0.
        forests=self.forests if self._forest_cells is None else self._forest_cells.get((math.floor(x/200),math.floor(y/200)),self._global_forests)
        for f in forests:
            if type(f) is not Forest:
                density=max(density,f.cover(x,y)); continue
            dx,dy=x-f.x,y-f.y
            if abs(dx)>=f.radius_x or abs(dy)>=f.radius_y: continue
            radius=math.hypot(dx/f.radius_x,dy/f.radius_y)
            t=max(0.,min(1.,(1-radius)/.2))
            value=f.density*t*t*(3-2*t)
            if value>density: density=value
        return density
    def terrain_type(self,x: float,y: float) -> str: return 'dense forest' if self.forest_density(x,y)>.65 else 'light forest' if self.forest_density(x,y)>.05 else 'open'

    def sample_step(self,maximum):
        return min(maximum,min((min(h.radius_x,h.radius_y)/4 for h in self.hills),default=maximum),
                   min((min(f.radius_x,f.radius_y)/4 for f in self.forests),default=maximum))

    def visibility(self,a: Vec,b: Vec,rules: TerrainRules = TerrainRules(),vegetation_scale: float = 1.):
        if self.empty: return Visibility()
        dx,dy=b.x-a.x,b.y-a.y
        distance=math.hypot(dx,dy)
        if distance<1e-8: return Visibility()
        count=max(1,math.ceil(distance/self.sample_step(rules.sight_step)))
        start=self.get_elevation(a.x,a.y)+rules.observer_height
        end=self.get_elevation(b.x,b.y)+rules.observer_height
        vegetation=0.
        for i in range(count):
            t=(i+.5)/count
            x,y=a.x+dx*t,a.y+dy*t
            ground=self.get_elevation(x,y); z=start+(end-start)*t
            if ground>z: return Visibility(False,0.,vegetation,'ridge')
            if z<ground+rules.canopy_height:
                vegetation+=self.forest_density(x,y)*distance/count*vegetation_scale
                # Once opaque for this observer, later samples cannot restore
                # sight. Hidden vegetation is a lower bound, not a full integral.
                if vegetation>=rules.forest_visibility_depth:
                    return Visibility(False,0.,vegetation,'forest')
        if vegetation>=rules.forest_visibility_depth:
            return Visibility(False,0.,vegetation,'forest')
        return Visibility(True,math.exp(-vegetation/rules.forest_accuracy_depth),vegetation,'forest' if vegetation>1 else 'clear')

    def movement_effect(self,unit,motion: Vec,rules: TerrainRules = TerrainRules()):
        if self.empty: return TerrainEffect()
        key=(unit.pos,unit.facing,unit.width,unit.depth)
        sample=self._footprint_cache.get(key)
        if sample is None:
            points=[unit.pos]+unit.footprint
            forest=sum(self.forest_density(p.x,p.y) for p in points)/len(points)
            gradients=tuple(self.gradient(p.x,p.y) for p in points)
            slope=sum(g.length() for g in gradients)/len(gradients)
            sample=(forest,gradients,slope)
            self._footprint_cache[key]=sample
            if len(self._footprint_cache)>2048: self._footprint_cache.popitem(last=False)
        else: self._footprint_cache.move_to_end(key)
        forest,gradients,slope=sample
        heading=motion.normalized()
        grade=sum(g.dot(heading) for g in gradients)/len(gradients)
        profile=getattr(rules,unit.stats.kind.value)
        column=rules.column_forest_factor if unit.formation.value=='column' else (.45 if unit.formation.value=='skirmish' else 1.)
        archetype=unit.archetype
        pathfinder=commanders.has(unit,commanders.S.PATHFINDER)
        forest_speed=1-profile.forest_slowdown*forest*column*archetype.forest_slow*(1-commanders.TUNING.pathfinder_forest if pathfinder else 1.)
        uphill=profile.uphill*(1-commanders.TUNING.pathfinder_uphill if pathfinder else 1.)
        if grade>=0: slope_speed=1/(1+uphill*grade)
        else:
            slope_speed=min(rules.max_downhill_speed,1-grade*.5)/(1+uphill*max(0.,-grade-rules.steep_grade))
        loss=forest*profile.forest_loss*column*archetype.forest_loss+max(0.,slope-rules.slope_disruption_start)*profile.slope_loss*archetype.slope_loss
        if pathfinder:loss*=1-commanders.TUNING.pathfinder_disruption
        return TerrainEffect(max(rules.min_speed,min(rules.max_downhill_speed,forest_speed*slope_speed)),loss,forest,slope,grade)

    def validate(self):
        if not all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (self.width,self.height)): raise ValueError('Terrain dimensions must be positive finite numbers.')
        if type(self.seed) is not int or not -(2**63)<=self.seed<2**63: raise ValueError('Terrain seed must be a signed 64-bit integer.')
        if not isinstance(self.preset,str): raise ValueError('Terrain preset must be a string.')
        if not isinstance(self.hills,tuple) or not isinstance(self.forests,tuple) or not all(isinstance(h,Hill) for h in self.hills) or not all(isinstance(f,Forest) for f in self.forests): raise ValueError('Terrain geometry must contain Hill and Forest tuples.')
        if len(self.hills)>256 or len(self.forests)>256: raise ValueError('At most 256 hills and 256 forests per map.')
        for feature in (*self.hills,*self.forests):
            values=(feature.x,feature.y,feature.radius_x,feature.radius_y,feature.height if isinstance(feature,Hill) else feature.density)
            if not all(type(v) in (int,float) and math.isfinite(v) for v in values): raise ValueError('Terrain coordinates must be finite numbers.')
            if not (0<=feature.x<=self.width and 0<=feature.y<=self.height): raise ValueError('Terrain feature centres must lie in the field.')
            if not (1<=feature.radius_x<=self.width*2 and 1<=feature.radius_y<=self.height*2): raise ValueError('Terrain radii must be positive and at least one metre.')
            if isinstance(feature,Forest) and not 0<=feature.density<=1: raise ValueError('Forest density must be 0–1.')
            if isinstance(feature,Hill) and abs(feature.height)>200: raise ValueError('Hill heights must be within ±200 metres.')
            if isinstance(feature,Hill) and type(feature.compact) is not bool: raise ValueError('Hill compact flag must be boolean.')

    def to_dict(self):
        return dict(width=self.width,height=self.height,preset=self.preset,seed=self.seed,
                    hills=[asdict(h) for h in self.hills],forests=[asdict(f) for f in self.forests])

    @classmethod
    def from_dict(cls,data):
        terrain=cls(data['width'],data['height'],tuple(Hill(**h) for h in data.get('hills',[])),
                    tuple(Forest(**f) for f in data.get('forests',[])),data.get('preset','Custom'),data.get('seed',0))
        terrain.validate(); return terrain


def generate_terrain(preset,width,height,seed):
    if preset not in TERRAIN_PRESETS: raise ValueError('Unknown terrain preset.')
    rng=random.Random(seed); hills=[]; forests=[]
    # Sector count and feature count grow; metre-sized radii/heights do not.
    columns=max(1,math.ceil(width/1000));rows=max(1,math.ceil(height/600))
    cell_width,cell_height=width/columns,height/rows
    density=cell_width*cell_height/600000
    forest_shapes=((.3,.3,120,108,.5),(.65,.65,140,120,1.),(.5,.18,100,78,.75),(.8,.32,90,84,.6))
    for col in range(columns):
        for row in range(rows):
            ox,oy=col*cell_width,row*cell_height
            if preset=='Central Hill': hills.append(Hill(ox+cell_width*.5,oy+cell_height*.5,120,150,25,compact=True))
            elif preset in ('Rolling Hills','Mixed Terrain'):
                for _ in range(max(1,round(5*density))):
                    sign=-.5 if len(hills)%5==4 else 1.
                    hills.append(Hill(ox+cell_width*rng.uniform(.2,.8),oy+cell_height*rng.uniform(.18,.82),rng.uniform(70,130),rng.uniform(72,132),rng.uniform(12,26)*sign,compact=True))
            elif preset=='Ridge Defence':
                hills.append(Hill(width*(.55+(col+.5)*.26/columns),oy+cell_height*.5,55,252,32,compact=True))
            if preset in ('Wooded Battlefield','Mixed Terrain'):
                for i in range(max(1,round(4*density))):
                    x,y,rx,ry,cover=forest_shapes[i%len(forest_shapes)]
                    forests.append(Forest(ox+cell_width*x+rng.uniform(-25,25),oy+cell_height*y+rng.uniform(-15,15),rx,ry,cover))
    terrain=TerrainMap(width,height,tuple(hills),tuple(forests),preset,seed)
    terrain.validate(); return terrain
