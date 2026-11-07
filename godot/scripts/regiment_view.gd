class_name RegimentView
extends Node2D
## One batched visual node. Decorative dots are not independent entities.
const Frame = preload("res://scripts/battle_frame.gd")
const World = preload("res://scripts/world_coordinates.gd")
var current: Frame
var following: Frame
var fraction: float = 0.0
var events: Array = []
var time: float = 0.0
var selected: int = -1
var zoom: float = 1.0
var army_colors: Dictionary = {}
var last_draw_us: int = 0
var font: Font = ThemeDB.fallback_font

func display(a: Frame, b: Frame, alpha: float, at: float, visible_events: Array) -> void:
    current = a;following = b;fraction = alpha;time = at;events = visible_events
    queue_redraw()

func unit_pose(u: Frame.UnitState) -> Dictionary:
    var next: Variant = following.units.get(u.info.id) if following != null else null
    return {"position": World.position_between(u, next, fraction), "facing": World.facing_between(u, next, fraction)}

func pick(point: Vector2) -> int:
    if current == null:return -1
    # Reverse draw order selects the topmost formation; no input writes to DTOs.
    var units := current.units.values();units.reverse()
    for u in units:
        if not u.observed or not u.active and u.info.id != selected:continue
        var pose := unit_pose(u)
        if World.contains(point, pose.position, pose.facing, u.width, u.depth):return u.info.id
    return -1

func _draw() -> void:
    var start := Time.get_ticks_usec()
    if current == null:return
    var width := 1.0 / maxf(zoom, 0.05)
    var bounds := get_viewport_rect().grow(120)
    var transform := get_global_transform_with_canvas()
    for u in current.units.values():
        if not u.observed or not u.active and u.info.id != selected:continue
        var pose := unit_pose(u)
        if not bounds.has_point(transform * pose.position):continue
        draw_regiment(u, pose.position, pose.facing, width)
    for p in current.shots.values():
        var next: Variant = following.shots.get(p.id) if following != null else null
        var ground := World.position_between(p, next, fraction)
        var point := World.ball_position(p, next, fraction)
        draw_circle(ground, 2.0 * width, Color(0.04, 0.06, 0.04, 0.7))
        draw_line(ground, point, Color(0.95, 0.77, 0.45, 0.5), width)
        draw_circle(point, 2.5 * width, Color(1.0, 0.86, 0.46))
    for event in events:
        if not event.has_position:continue
        var age: float = time - event.time
        if age < 0 or age > event.duration:continue
        var fade := 1.0 - age / maxf(0.1, event.duration)
        if event.kind in ["volley", "artillery_fire"]:
            var side := Vector2.from_angle(event.facing + PI / 2.0)
            var forward := Vector2.from_angle(event.facing)
            for i in range(7):
                var point: Vector2 = event.position + side * (float(i) / 6.0 - 0.5) * event.width + forward * age * 5
                draw_circle(point, 3.0 + age * 4.0, Color(0.85, 0.86, 0.79, fade * 0.5))
                if age < 0.16:draw_circle(point, 3.0, Color(1.0, 0.86, 0.35, 0.9))
        elif event.kind in ["impact", "charge_impact", "charge_start", "rout", "rally"]:
            var color := Color(1.0, 0.73, 0.28, fade)
            if event.kind == "rout":color = Color(0.9, 0.4, 0.85, fade)
            if event.kind == "rally":color = Color(0.35, 1.0, 0.65, fade)
            draw_arc(event.position, 7.0 + age * 12.0, 0, TAU, 24, color, 2.0 * width, true)
    var chosen: Variant = current.units.get(selected)
    if chosen != null and current.units.has(chosen.target):
        var target: Variant = current.units[chosen.target]
        var a: Dictionary = unit_pose(chosen);var b: Dictionary = unit_pose(target)
        draw_dashed_line(a.position, b.position, Color(1.0, 0.9, 0.45), width, 8.0 * width)
        draw_arc(b.position, maxf(target.width, target.depth) * 0.6, 0, TAU, 32, Color(1.0, 0.9, 0.45), 2.0 * width)
    last_draw_us = Time.get_ticks_usec() - start

func draw_regiment(u: Frame.UnitState, point: Vector2, facing: float, pixel: float) -> void:
    var color: Color = army_colors.get(u.info.army, Color.WHITE)
    if u.state == "routing":color = color.darkened(0.35)
    if not u.active:color.a = 0.3
    var corners := World.footprint(point, facing, u.width, u.depth)
    draw_colored_polygon(PackedVector2Array([corners[0], corners[1], corners[2], corners[3]]), Color(color, 0.75))
    draw_polyline(corners, Color(0.05, 0.08, 0.07), 3.0 * pixel, true)
    draw_polyline(corners, Color(1.0, 0.93, 0.55) if u.info.id == selected else color.lightened(0.35), (2.5 if u.info.id == selected else 1.0) * pixel, true)
    var forward := Vector2.from_angle(facing)
    var side := Vector2.from_angle(facing + PI / 2.0)
    var tip := point + forward * (u.depth / 2.0 + 10.0)
    draw_line(point, tip, u.info.accent, 2.0 * pixel, true)
    draw_polyline(PackedVector2Array([tip - forward * 5 + side * 4, tip, tip - forward * 5 - side * 4]), u.info.accent, 1.5 * pixel, true)
    if u.formation == "skirmish":
        for row in range(2):
            for col in range(7):
                var dot := point + side * (float(col) / 6.0 - 0.5) * u.width * 0.85 + forward * (float(row) - 0.5) * u.depth * 0.65
                draw_circle(dot, 1.7 * pixel, u.info.accent)
    if u.info.category == "cavalry":
        draw_polyline(PackedVector2Array([point - side * 8 - forward * 4, point + forward * 5, point + side * 8 - forward * 4]), u.info.accent, 2.0 * pixel)
    if u.info.category == "artillery":
        draw_line(point - forward * 5, point + forward * 10, u.info.accent, 4.0 * pixel)
        draw_circle(point + side * 5, 2.5 * pixel, u.info.accent)
        draw_circle(point - side * 5, 2.5 * pixel, u.info.accent)
    var label := str(u.info.id) + ":" + u.info.symbol
    var label_at := point - Vector2(0, u.width / 2.0 + 9.0 * pixel)
    # Constant font raster size; compensate in the draw transform rather than
    # creating a new oversized glyph atlas at every camera zoom.
    draw_set_transform(label_at, 0.0, Vector2.ONE * pixel)
    draw_string_outline(font, Vector2.ZERO, label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, 3, Color(0.06, 0.08, 0.07))
    draw_string(font, Vector2.ZERO, label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(0.97, 0.95, 0.81))
    draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
    var bar := point + Vector2(-14 * pixel, u.width / 2.0 + 5 * pixel)
    draw_rect(Rect2(bar, Vector2(28 * pixel, 3 * pixel)), Color(0.08, 0.10, 0.08))
    draw_rect(Rect2(bar, Vector2(28 * pixel * u.morale / 100.0, 3 * pixel)), Color(0.4, 0.85, 0.4))
    if u.charge_state in ["charging", "pursuit"]:
        draw_line(tip, tip + forward * 14, Color(1.0, 0.7, 0.2), 3 * pixel, true)
