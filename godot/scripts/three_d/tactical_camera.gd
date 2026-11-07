class_name TacticalCameraRig
extends Node3D
signal selection_requested(pixel: Vector2)
signal secondary_requested(pixel: Vector2)
signal secondary_started(pixel: Vector2)
signal secondary_updated(pixel: Vector2)
signal secondary_cancelled()
var secondary_down: bool=false
## Independent real-time rig; no replay, regiment, JSON or physics dependencies.
const Settings = preload("res://scripts/three_d/camera_settings.gd")
const Surface = preload("res://scripts/three_d/terrain_surface.gd")
const Bindings = preload("res://scripts/three_d/camera_bindings.gd")
const World = preload("res://scripts/three_d/world_3d.gd")
@export var settings: Settings = preload("res://resources/tactical_camera.tres")
var camera: Camera3D
var surface: Surface
var focus := Vector2.ZERO
var target_focus := Vector2.ZERO
var velocity := Vector2.ZERO
var yaw: float = 0.0
var target_yaw: float = 0.0
var pitch: float = deg_to_rad(55)
var target_pitch: float = deg_to_rad(55)
var span: float = 500.0
var target_span: float = 500.0
var max_span: float = 1000.0
var margin: float = 80.0
var overhead: bool = false
var saved_view: Dictionary = {}
var perspective: bool = true
var follow_offset := Vector2.ZERO
var follow_id: int = -1
var auto_focus: bool = false
var fit_mode: bool = true
var navigation_enabled: bool = true
var dragging: bool = false
var orbiting: bool = false
var drag_anchor: Variant = null
var drag_pixel := Vector2.ZERO
var mouse_position := Vector2.ZERO
var zoom_anchor: Variant = null
var zoom_cursor := Vector2.ZERO

func _ready() -> void:
    Bindings.install()
    if camera == null:
        camera = Camera3D.new();add_child(camera);camera.current = true
    camera.keep_aspect = Camera3D.KEEP_HEIGHT;camera.near = 0.15

func configure(value: Surface) -> void:
    surface = value;max_span = surface.size.length() * settings.maximum_zoom_diagonals
    margin = minf(settings.boundary_margin_maximum, minf(surface.size.x, surface.size.y) * settings.boundary_margin_fraction)
    pitch = deg_to_rad(settings.default_pitch);target_pitch = pitch
    yaw = 0;target_yaw = 0;overhead = false;perspective = settings.default_perspective;follow_id = -1;follow_offset = Vector2.ZERO
    fit(true)

func right_direction() -> Vector2:return Vector2(cos(yaw), -sin(yaw))
func forward_direction() -> Vector2:return Vector2(-sin(yaw), -cos(yaw))
func constrained(point: Vector2) -> Vector2:return point.clamp(Vector2.ONE * -margin, surface.size + Vector2.ONE * margin)

func fit(snap: bool = false) -> void:
    if surface == null or camera == null:return
    fit_mode = true;auto_focus = true
    target_span = fit_span(target_pitch, perspective)
    target_focus = surface.size * 0.5;velocity = Vector2.ZERO;follow_id = -1;zoom_anchor = null
    if snap:focus = target_focus;span = target_span
    update_pose()

func fit_span(angle: float, use_perspective: bool) -> float:
    var aspect := maxf(0.1, camera.get_viewport().get_visible_rect().size.aspect())
    var right := Vector3(cos(target_yaw), 0, -sin(target_yaw))
    var orbit := Vector3(sin(target_yaw)*cos(angle),sin(angle),cos(target_yaw)*cos(angle))
    var up := orbit.cross(right)
    var required: float
    if use_perspective:
        var tangent := tan(deg_to_rad(settings.perspective_fov)*.5)
        var center := World.ground(surface.size*.5,surface.height_at(surface.size*.5))
        var distance := 0.0
        for x in [0.0,surface.size.x]:
            for z in [0.0,surface.size.y]:
                for h in [surface.minimum,surface.maximum]:
                    var relative := Vector3(x,h,z)-center
                    distance=maxf(distance,relative.dot(orbit)+maxf(absf(relative.dot(right))/(tangent*aspect),absf(relative.dot(up))/tangent))
        required=distance*2*tangent*1.10
    else:
        var width := Vector2(absf(right.x),absf(right.z)).dot(surface.size)
        var height := Vector2(absf(up.x),absf(up.z)).dot(surface.size)+(surface.maximum-surface.minimum)*absf(up.y)
        required=maxf(width/aspect,height)*1.12
    return clampf(required,settings.minimum_zoom,max_span)

func viewport_resized() -> void:
    end_drag();cancel_secondary();zoom_anchor=null
    if fit_mode:fit(false)
    else:update_pose()

func focus_on(point: Vector2) -> void:
    auto_focus = true;fit_mode = false
    target_focus = constrained(point);velocity = Vector2.ZERO;zoom_anchor = null;follow_id = -1;follow_offset = Vector2.ZERO

func manual_motion() -> void:
    if follow_id >= 0 or auto_focus:target_focus = focus;velocity = Vector2.ZERO
    follow_id = -1;follow_offset = Vector2.ZERO;zoom_anchor = null;auto_focus = false;fit_mode = false

func toggle_overhead() -> void:
    zoom_anchor = null
    if not overhead:
        saved_view = {"pitch": target_pitch, "span": target_span, "perspective": perspective, "yaw": target_yaw}
        target_pitch = deg_to_rad(settings.overhead_pitch);perspective = false;overhead = true
        if fit_mode:target_span=fit_span(target_pitch,false)
    else:
        target_pitch = saved_view.pitch;target_yaw = saved_view.yaw;target_span = saved_view.span;perspective = saved_view.perspective;overhead = false
    update_pose()

func toggle_projection() -> void:
    perspective = not perspective;overhead = false;zoom_anchor = null;update_pose()

func view_distance() -> float:
    # Span is a scale-compatible control value, not a changing lens/FOV.
    # With a fixed perspective lens this directly controls physical distance.
    return span / (2.0 * tan(deg_to_rad(settings.perspective_fov) * 0.5))

func update_pose() -> void:
    if surface == null or camera == null:return
    var ground := World.ground(focus, surface.height_at(focus))
    var low_angle: float=clampf(1.0-pitch/deg_to_rad(10),0,1)
    ground.y+=settings.terrain_clearance*low_angle
    var distance := view_distance()
    var offset := Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)) * distance
    camera.near = clampf(distance*settings.near_clip_distance_ratio,settings.minimum_near_clip,settings.maximum_near_clip)
    camera.position = ground + offset
    var lift: float=maxf(0,surface.height_at(World.horizontal(camera.position))+settings.terrain_clearance-camera.position.y)
    camera.position.y+=lift
    ground.y+=lift*low_angle
    camera.look_at(ground, Vector3.UP)
    camera.projection = Camera3D.PROJECTION_PERSPECTIVE if perspective else Camera3D.PROJECTION_ORTHOGONAL
    camera.fov = settings.perspective_fov;camera.size = span
    camera.far = maxf(2000.0, surface.size.length() * 4.0 + distance * 2)
    camera.force_update_transform()

func ground_under(pixel: Vector2) -> Variant:
    if surface == null:return null
    return surface.raycast(camera.project_ray_origin(pixel), camera.project_ray_normal(pixel))

func request_zoom(steps: float, pixel: Vector2) -> void:
    if is_zero_approx(steps):return
    fit_mode = false
    zoom_anchor = ground_under(pixel);zoom_cursor = pixel
    # Orthographic scaling has no sense of approaching the ground. Wheel input
    # always dollies with perspective, including from a tactical overhead view.
    if not perspective:
        perspective = true;update_pose()
        if zoom_anchor != null:pin_ground(zoom_anchor, zoom_cursor)
    target_span = clampf(target_span * exp(-steps * settings.zoom_sensitivity), settings.minimum_zoom, max_span)

func begin_drag(pixel: Vector2, orbit: bool) -> void:
    cancel_secondary()
    manual_motion();dragging = true;orbiting = orbit;mouse_position = pixel;drag_pixel = pixel
    drag_anchor = ground_under(pixel);velocity = Vector2.ZERO

func drag_to(pixel: Vector2, relative: Vector2) -> void:
    mouse_position = pixel
    if orbiting:
        target_yaw -= relative.x * settings.mouse_rotation_sensitivity
        target_pitch = clampf(target_pitch - relative.y * settings.mouse_rotation_sensitivity, deg_to_rad(settings.minimum_pitch), deg_to_rad(settings.maximum_pitch))
        overhead = false
    elif drag_anchor != null:
        drag_pixel += relative * settings.mouse_pan_sensitivity
        pin_ground(drag_anchor, drag_pixel)

func cancel_secondary() -> void:
    secondary_down=false;secondary_cancelled.emit()

func end_drag() -> void:dragging = false;orbiting = false;drag_anchor = null

func pin_ground(anchor: Vector3, pixel: Vector2) -> void:
    # Iteration handles focus-height changes when translating the camera uphill.
    for _i in range(4):
        var hit: Variant = ground_under(pixel)
        if hit == null:return
        var shift := World.horizontal(anchor - hit)
        var next := constrained(focus + shift)
        if follow_id >= 0:follow_offset += next - focus
        target_focus += next - focus;focus = next;update_pose()
        if shift.length() < 0.0005:break
    target_focus = constrained(target_focus)

func advance(delta: float, move: Vector2 = Vector2.ZERO, turn: float = 0.0, fast: bool = false, following: Variant = null) -> void:
    if surface == null:return
    if move.length_squared() > 0 or turn != 0:manual_motion()
    if follow_id >= 0:
        if following == null:follow_id = -1
        else:target_focus = constrained(following + follow_offset)
    # Bounded 120 Hz camera integration makes damping consistent at low/high
    # render rates. Pose/raycast work happens once after these cheap scalar steps.
    var left := maxf(0.0, delta)
    while left > 0.000001:
        var dt := minf(left, 1.0 / 120.0);left -= dt
        var direction := right_direction() * move.x + forward_direction() * -move.y
        var speed := settings.move_speed * clampf(span / 200.0, 0.12, 12.0) * (settings.fast_multiplier if fast else 1.0)
        var wanted := direction.limit_length(1.0) * speed
        velocity = velocity.lerp(wanted, 1 - exp(-settings.movement_acceleration * dt))
        target_focus = constrained(target_focus + velocity * dt)
        target_yaw += turn * settings.rotation_speed * dt
        target_pitch = clampf(target_pitch, deg_to_rad(settings.minimum_pitch), deg_to_rad(settings.maximum_pitch))
        target_span = clampf(target_span, settings.minimum_zoom, max_span)
        focus = focus.lerp(target_focus, 1 - exp(-(settings.focus_smoothing if auto_focus or follow_id >= 0 else settings.movement_smoothing) * dt))
        yaw = lerp_angle(yaw, target_yaw, 1 - exp(-settings.rotation_smoothing * dt))
        pitch = lerpf(pitch, target_pitch, 1 - exp(-settings.rotation_smoothing * dt))
        span = lerpf(span, target_span, 1 - exp(-settings.zoom_smoothing * dt))
    update_pose()
    if zoom_anchor != null:
        pin_ground(zoom_anchor, zoom_cursor)
        if absf(span - target_span) < 0.002:zoom_anchor = null

func _unhandled_input(event: InputEvent) -> void:
    if not navigation_enabled:return
    if event is InputEventMouseButton:
        if event.button_index==MOUSE_BUTTON_LEFT and event.pressed and not dragging:selection_requested.emit(event.position)
        if event.button_index==MOUSE_BUTTON_RIGHT and not dragging:
            if event.pressed:secondary_down=true;secondary_started.emit(event.position)
            elif secondary_down:secondary_down=false;secondary_requested.emit(event.position)
        if event.is_action_pressed("camera_drag"):begin_drag(event.position, Input.is_action_pressed("camera_orbit_modifier"))
        elif event.is_action_released("camera_drag"):end_drag()
        elif event.is_action_pressed("camera_zoom_in"):request_zoom(1, event.position)
        elif event.is_action_pressed("camera_zoom_out"):request_zoom(-1, event.position)
    elif event is InputEventMouseMotion:
        if dragging:drag_to(event.position, event.relative)
        elif secondary_down:secondary_updated.emit(event.position)
