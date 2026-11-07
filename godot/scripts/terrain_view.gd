class_name BattlefieldTerrain
extends Node2D
## Build once per map. Camera changes transform retained CanvasItem commands.
const Frame = preload("res://scripts/battle_frame.gd")
var terrain: Frame.TerrainData
var texture: ImageTexture
var trees: Array = []
var build_ms: float = 0.0
var builds: int = 0

func configure(value: Frame.TerrainData) -> void:
    var start := Time.get_ticks_usec()
    terrain = value;trees.clear()
    # Bounded visual raster only; the original analytic features are retained.
    var scale := minf(1.0, 640.0 / maxf(terrain.size.x, terrain.size.y))
    var w := maxi(2, int(terrain.size.x * scale))
    var h := maxi(2, int(terrain.size.y * scale))
    var image := Image.create(w, h, false, Image.FORMAT_RGB8)
    var previous: PackedFloat32Array = PackedFloat32Array();previous.resize(w)
    for y in range(h):
        var left := 0.0
        for x in range(w):
            var point := Vector2(float(x) / (w - 1), float(y) / (h - 1)) * terrain.size
            var elevation := terrain.elevation(point)
            var density := terrain.forest_density(point)
            var ground := Color(0.22, 0.34, 0.22).lerp(Color(0.51, 0.54, 0.32), clampf(elevation / 65.0, 0.0, 1.0))
            if elevation < 0:ground = ground.darkened(minf(0.2, -elevation / 100.0))
            if (x > 0 and floorf(elevation / 5.0) != floorf(left / 5.0)) or (y > 0 and floorf(elevation / 5.0) != floorf(previous[x] / 5.0)):
                ground = ground.darkened(0.16)
            ground = ground.lerp(Color(0.07, 0.21, 0.13), density * 0.78)
            image.set_pixel(x, y, ground);left = elevation;previous[x] = elevation
    texture = ImageTexture.create_from_image(image)
    for forest in terrain.forests:
        var spacing := lerpf(30.0, 18.0, forest.density)
        for x in range(int((forest.center.x - forest.radius.x) / spacing), int((forest.center.x + forest.radius.x) / spacing) + 1):
            for y in range(int((forest.center.y - forest.radius.y) / spacing), int((forest.center.y + forest.radius.y) / spacing) + 1):
                var point := Vector2(x * spacing + sin(float(y) * 3.1) * 4.0, y * spacing)
                if not terrain.is_water(point) and Rect2(Vector2.ZERO, terrain.size).has_point(point) and terrain.forest_density(point) > 0.15:
                    trees.append(point)
    builds += 1;build_ms = (Time.get_ticks_usec() - start) / 1000.0
    queue_redraw()

func _draw() -> void:
    if terrain == null:return
    draw_texture_rect(texture, Rect2(Vector2.ZERO, terrain.size), false)
    for water in terrain.environment.get("water",[]):draw_colored_polygon(PackedVector2Array(water.points),Color("#4d8b9d"))
    for road in terrain.environment.get("roads",[]):draw_polyline(PackedVector2Array(road.points),Color("#968469"),road.width)
    for crossing in terrain.environment.get("crossings",[]):draw_line(crossing.entry,crossing.exit,Color("#aa9169") if crossing.kind=="bridge" else Color("#93aaab"),crossing.width)
    for work in terrain.environment.get("defences",[]):
        var side: Vector2=Vector2.UP.rotated(work.facing)*work.width/2
        draw_line(work.position-side,work.position+side,Color("#74593e"),work.depth)
    for point in trees:
        draw_line(point, point + Vector2(0, 5), Color(0.15, 0.16, 0.10), 1.5)
        draw_colored_polygon(PackedVector2Array([point + Vector2(0, -5), point + Vector2(-4, 2), point + Vector2(4, 2)]), Color(0.12, 0.28, 0.16, 0.85))
    draw_rect(Rect2(Vector2.ZERO, terrain.size), Color(0.65, 0.71, 0.49), false, 2.0)
