class_name TerrainSurface3D
extends RefCounted
## One canonical sampled surface for mesh vertices, camera rays and grounding.
## Triangular interpolation matches the actual indexed mesh, not a flat plane.
const Frame = preload("res://scripts/battle_frame.gd")
var model: Frame.TerrainData
var size: Vector2
var nx: int
var nz: int
var step: Vector2
var heights := PackedFloat32Array()
var minimum: float = 0
var maximum: float = 0
var forest_densities := PackedFloat32Array()
var forest_cells: Dictionary = {}
var crossings: Array=[]
var bridge_decks: Array[BridgeDeck]=[]
const FOREST_CELL := 200.0

func configure(data: Frame.TerrainData, resolution: float = 5.0, budget: int = 200000) -> void:
    model = data;size = data.size;crossings=data.environment.get("crossings",[])
    bridge_decks.clear()
    for c in crossings:
        if c.kind!="bridge":continue
        var deck:=BridgeDeck.new();deck.center=c.position;deck.axis=Vector2.RIGHT.rotated(c.facing);deck.side=deck.axis.orthogonal()
        deck.length=c.length*.5;deck.width=c.width*.5;deck.height=c.height;deck.radius_squared=deck.length*deck.length+deck.width*deck.width;bridge_decks.append(deck)
    if not data.canonical_grid.is_empty():
        nx=data.canonical_grid.nx;nz=data.canonical_grid.nz;step=size/Vector2(nx,nz);heights=PackedFloat32Array(data.canonical_grid.heights)
        minimum=INF;maximum=-INF
        for value in heights:minimum=minf(minimum,value);maximum=maxf(maximum,value)
        forest_cells.clear();forest_densities.resize(heights.size());forest_densities.fill(0)
        for z in range(nz+1):
            for x in range(nx+1):forest_densities[z*(nx+1)+x]=model.forest_density(Vector2(x,z)*step)
        return
    var spacing := maxf(0.5, resolution)
    spacing = maxf(spacing, sqrt(size.x * size.y / maxf(4.0, budget - 2000)))
    nx = maxi(1, int(ceil(size.x / spacing)));nz = maxi(1, int(ceil(size.y / spacing)))
    step = size / Vector2(nx, nz)
    var count := (nx + 1) * (nz + 1)
    var sums := PackedFloat64Array();sums.resize(count)
    forest_densities.resize(count);forest_densities.fill(0);forest_cells.clear()
    # Same analytic functions and feature order, restricted to their exact
    # finite supports. Legacy infinite Gaussians still visit the whole grid.
    for h in model.hills:
        var bounds := feature_bounds(h.center,h.radius*3) if h.compact else Rect2i(0,0,nx+1,nz+1)
        for z in range(bounds.position.y,bounds.end.y):
            for x in range(bounds.position.x,bounds.end.x):
                var delta: Vector2=(Vector2(x,z)*step-h.center)/h.radius
                var squared: float=delta.length_squared()
                var value: float=h.height*pow(maxf(0,1-squared/9),4) if h.compact else h.height*exp(-.5*squared)
                sums[z*(nx+1)+x]+=value
    for f in model.forests:
        var low: Vector2i=Vector2i(floor((f.center.x-f.radius.x)/FOREST_CELL),floor((f.center.y-f.radius.y)/FOREST_CELL))
        var high: Vector2i=Vector2i(floor((f.center.x+f.radius.x)/FOREST_CELL),floor((f.center.y+f.radius.y)/FOREST_CELL))
        for cx in range(low.x,high.x+1):
            for cz in range(low.y,high.y+1):
                var cell:=Vector2i(cx,cz)
                if not forest_cells.has(cell):forest_cells[cell]=[]
                forest_cells[cell].append(f)
        var bounds:=feature_bounds(f.center,f.radius)
        for z in range(bounds.position.y,bounds.end.y):
            for x in range(bounds.position.x,bounds.end.x):
                var density:=forest_value(f,Vector2(x,z)*step)
                var index:=z*(nx+1)+x;forest_densities[index]=maxf(forest_densities[index],density)
    heights.resize(count);minimum=INF;maximum=-INF
    for i in range(count):
        heights[i]=sums[i];minimum=minf(minimum,sums[i]);maximum=maxf(maximum,sums[i])

func feature_bounds(center: Vector2,radius: Vector2) -> Rect2i:
    var low: Vector2i=Vector2i(((center-radius)/step).floor()).clamp(Vector2i.ZERO,Vector2i(nx,nz))
    var high: Vector2i=Vector2i(((center+radius)/step).ceil()).clamp(Vector2i.ZERO,Vector2i(nx,nz))
    return Rect2i(low,high-low+Vector2i.ONE)

func forest_value(f: Dictionary,point: Vector2) -> float:
    var delta: Vector2=(point-f.center)/f.radius
    var t:=clampf((1-delta.length())/.2,0,1)
    return f.density*t*t*(3-2*t)

func exact_forest_density(point: Vector2) -> float:
    if not model.canonical_grid.is_empty():return model.forest_density(point)
    var density:=0.0
    var cell:=Vector2i(floor(point.x/FOREST_CELL),floor(point.y/FOREST_CELL))
    for f in forest_cells.get(cell,[]):density=maxf(density,forest_value(f,point))
    return density

func vertex_height(x: int, z: int) -> float:
    return heights[clampi(z, 0, nz) * (nx + 1) + clampi(x, 0, nx)]

func height_at(point: Vector2) -> float:
    for deck in bridge_decks:
        var delta:=point-deck.center
        if delta.length_squared()<=deck.radius_squared and absf(delta.dot(deck.axis))<=deck.length and absf(delta.dot(deck.side))<=deck.width:return deck.height
    var cell := (point / step).clamp(Vector2.ZERO, Vector2(nx, nz))
    var x := mini(nx - 1, int(floor(cell.x)));var z := mini(nz - 1, int(floor(cell.y)))
    var f := cell - Vector2(x, z)
    var a := vertex_height(x, z);var b := vertex_height(x + 1, z)
    var c := vertex_height(x, z + 1);var d := vertex_height(x + 1, z + 1)
    return a + (b - a) * f.x + (c - a) * f.y if f.x + f.y <= 1 else d + (c - d) * (1 - f.x) + (b - d) * (1 - f.y)

func normal_at(point: Vector2) -> Vector3:
    var dx := (height_at(point + Vector2(step.x, 0)) - height_at(point - Vector2(step.x, 0))) / (2 * step.x)
    var dz := (height_at(point + Vector2(0, step.y)) - height_at(point - Vector2(0, step.y))) / (2 * step.y)
    return Vector3(-dx, 1, -dz).normalized()

func raycast(origin: Vector3, direction: Vector3) -> Variant:
    # Slab clip includes hills and valleys, then finds first surface crossing.
    var lo := 0.0;var hi := 100000.0
    var low := Vector3(0, minimum - 0.1, 0);var high := Vector3(size.x, maximum + 0.1, size.y)
    for axis in range(3):
        if absf(direction[axis]) < 0.0000001:
            if origin[axis] < low[axis] or origin[axis] > high[axis]:return null
        else:
            var a: float = (low[axis] - origin[axis]) / direction[axis]
            var b: float = (high[axis] - origin[axis]) / direction[axis]
            lo = maxf(lo, minf(a, b));hi = minf(hi, maxf(a, b))
    if hi < lo:return null
    var stride := minf(step.x, step.y) * 0.5 / maxf(0.01, Vector2(direction.x, direction.z).length())
    var before := lo
    var point := origin + direction * lo
    if point.y <= height_at(Vector2(point.x, point.z)):
        return Vector3(point.x, height_at(Vector2(point.x, point.z)), point.z)
    while lo < hi:
        lo = minf(hi, lo + stride);point = origin + direction * lo
        if point.y <= height_at(Vector2(point.x, point.z)):
            var left := before;var right := lo
            for _i in range(18):
                var middle := (left + right) * 0.5;point = origin + direction * middle
                if point.y > height_at(Vector2(point.x, point.z)):left = middle
                else:right = middle
            point = origin + direction * ((left + right) * 0.5)
            return Vector3(point.x, height_at(Vector2(point.x, point.z)), point.z)
        before = lo
    return null

class BridgeDeck:
    var center: Vector2
    var axis: Vector2
    var side: Vector2
    var length: float
    var width: float
    var height: float
    var radius_squared: float
