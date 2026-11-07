"""Conservative uniform-grid queries, returning original list order.

Only use during phases with fixed formation geometry. Mutable enemy separation
deliberately retains its original pair traversal.
"""
import math


class SpatialIndex:
    def __init__(self,units,padding=0.,cell_size=100.):
        self.units=units
        self.cell_size=cell_size
        self.cells={}
        for i,u in enumerate(units):
            radius=math.hypot(u.width,u.depth)/2+padding+1e-8
            for cell in self._cells(u.pos.x-radius,u.pos.y-radius,u.pos.x+radius,u.pos.y+radius):
                self.cells.setdefault(cell,[]).append(i)

    def _cells(self,left,top,right,bottom):
        size=self.cell_size
        for x in range(math.floor(left/size),math.floor(right/size)+1):
            for y in range(math.floor(top/size),math.floor(bottom/size)+1): yield x,y

    def pairs(self):
        pairs=set()
        for indices in self.cells.values():
            for i,a in enumerate(indices):
                for b in indices[i+1:]: pairs.add((a,b))
        return ((self.units[i],self.units[j]) for i,j in sorted(pairs))

    def segment(self,start,end,padding=0.):
        indices=set()
        for cell in self._cells(min(start.x,end.x)-padding,min(start.y,end.y)-padding,max(start.x,end.x)+padding,max(start.y,end.y)+padding):
            indices.update(self.cells.get(cell,()))
        return (self.units[i] for i in sorted(indices))


def candidate_pairs(units,padding=0.):
    if len(units)<12:
        return ((a,b) for i,a in enumerate(units) for b in units[i+1:])
    return SpatialIndex(units,padding).pairs()
