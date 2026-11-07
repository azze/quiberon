"""Cached terrain shading, approximate contours and cosmetic tree symbols."""
import math
import random
import pygame
from simulation.geometry import Vec

class TerrainPainter:
    def __init__(self):
        self.key=None
        self.surface=None
        self.contours=None
        self._view_key=None
        self._view=None

    def build(self,terrain):
        # Bound cosmetic painting cost on kilometre-scale maps. Simulation
        # elevation/visibility sampling remains unchanged.
        step=max(6.,terrain.width/320,terrain.height/240)
        size=(max(1,math.ceil(terrain.width/step)),max(1,math.ceil(terrain.height/step)))
        surface=pygame.Surface(size)
        contours=[]
        for x in range(size[0]):
            for y in range(size[1]):
                wx,wy=(x+.5)*step,(y+.5)*step
                z=terrain.get_elevation(wx,wy); slope=terrain.gradient(wx,wy)
                forest=terrain.forest_density(wx,wy)
                light=max(-25,min(35,z*.65-slope.x*28-slope.y*18))
                surface.set_at((x,y),tuple(max(0,min(255,int(base+light-forest*shade))) for base,shade in ((76,32),(105,35),(62,24))))
                if terrain.hills:
                    corners=[Vec(x*step,y*step),Vec(min(terrain.width,(x+1)*step),y*step),Vec(min(terrain.width,(x+1)*step),min(terrain.height,(y+1)*step)),Vec(x*step,min(terrain.height,(y+1)*step))]
                    heights=[terrain.get_elevation(p.x,p.y) for p in corners]
                    for band in range(math.floor(min(heights)/5)+1,math.floor(max(heights)/5)+1):
                        level=band*5; hits=[]
                        for j in range(4):
                            a,b=heights[j],heights[(j+1)%4]
                            if (a<level<=b) or (b<level<=a):
                                hits.append(corners[j]+(corners[(j+1)%4]-corners[j])*((level-a)/(b-a)))
                        for j in range(0,len(hits)-1,2): contours.append((hits[j],hits[j+1]))
        rng=random.Random(terrain.seed)
        for forest in terrain.forests:
            count=min(220,int(forest.radius_x*forest.radius_y*forest.density/250))
            for _ in range(count):
                x=rng.uniform(forest.x-forest.radius_x,forest.x+forest.radius_x)
                y=rng.uniform(forest.y-forest.radius_y,forest.y+forest.radius_y)
                if forest.cover(x,y)>.15:
                    p=(round(x/step),round(y/step))
                    pygame.draw.circle(surface,(39,69,40),p,2)
                    pygame.draw.circle(surface,(61,87,47),(p[0]-1,p[1]-1),1)
        self.key=terrain; self.surface=surface; self.contours=contours
        self._view_key=None

    def draw(self,screen,camera,terrain,contours=True):
        if terrain.empty: return
        if terrain!=self.key: self.build(terrain)
        key=(screen.get_size(),camera.width,camera.height,camera.center,camera.zoom,contours)
        if key!=self._view_key:
            self._view=pygame.Surface(screen.get_size(),pygame.SRCALPHA)
            self._draw_view(self._view,camera,terrain,contours)
            self._view_key=key
        screen.blit(self._view,(0,0))

    def _draw_view(self,screen,camera,terrain,contours):
        top=camera.screen_to_world((0,0)); bottom=camera.screen_to_world((screen.get_width(),screen.get_height()-150))
        dx=terrain.width/self.surface.get_width(); dy=terrain.height/self.surface.get_height()
        left=max(0,math.floor(top.x/dx)); right=min(self.surface.get_width(),math.ceil(bottom.x/dx))
        upper=max(0,math.floor(top.y/dy)); lower=min(self.surface.get_height(),math.ceil(bottom.y/dy))
        if right<=left or lower<=upper: return
        crop=pygame.Rect(left,upper,right-left,lower-upper)
        origin=camera.world_to_screen(Vec(left*dx,upper*dy))
        size=(max(1,round(crop.width*dx*camera.zoom)),max(1,round(crop.height*dy*camera.zoom)))
        screen.blit(pygame.transform.smoothscale(self.surface.subsurface(crop),size),origin)
        if contours:
            for a,b in self.contours:
                pygame.draw.line(screen,(100,119,73),camera.world_to_screen(a),camera.world_to_screen(b),1)
