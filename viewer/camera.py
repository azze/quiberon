from dataclasses import dataclass
from simulation.geometry import Vec

@dataclass
class Camera:
    center: Vec = Vec(500, 300)
    zoom: float = 1.
    width: int = 1280
    height: int = 720
    def world_to_screen(self, p):
        return ((p.x - self.center.x) * self.zoom + self.width / 2,
                (p.y - self.center.y) * self.zoom + (self.height - 150) / 2)
    def screen_to_world(self, p):
        return Vec((p[0] - self.width / 2) / self.zoom + self.center.x,
                   (p[1] - (self.height - 150) / 2) / self.zoom + self.center.y)
    def zoom_at(self, screen, factor):
        before = self.screen_to_world(screen)
        self.zoom = max(.08, min(4., self.zoom * factor))
        self.center += before - self.screen_to_world(screen)

    def fit(self, world_width, world_height):
        self.center = Vec(world_width/2, world_height/2)
        self.zoom = min((self.width-50)/world_width, (self.height-200)/world_height)
