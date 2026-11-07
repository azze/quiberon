extends Node2D
## Alternate presentation of the owner's existing frame source, never a new clock.
signal selection_requested(pixel: Vector2)
signal secondary_started(pixel: Vector2)
signal secondary_updated(pixel: Vector2)
signal secondary_requested(pixel: Vector2)
signal secondary_cancelled()
const Terrain=preload("res://scripts/terrain_view.gd")
const Units=preload("res://scripts/regiment_view.gd")
var terrain_view: Terrain
var units_view: Units
var camera: Camera2D
var overlay: Node2D
var terrain: Object
var configured_terrain: Object
var armies: Dictionary={}
var mission_data: Dictionary={}
var deployment_zones: Array=[]
var enabled: bool=false
var navigation_enabled: bool=true
var secondary_down: bool=false
var dragging: bool=false
var follow_id: int=-1
var fitted: bool=true
var ghost: Object
var deployment: bool=false
func _ready() -> void:
    terrain_view=Terrain.new();add_child(terrain_view)
    units_view=Units.new();units_view.z_index=1;add_child(units_view)
    overlay=Node2D.new();overlay.z_index=2;add_child(overlay);overlay.draw.connect(draw_overlays)
    camera=Camera2D.new();camera.enabled=false;add_child(camera);visible=false
func configure(value: Object,colors: Dictionary) -> void:
    terrain=value;armies=colors;configured_terrain=null;fitted=true;follow_id=-1
func activate(value: bool) -> void:
    enabled=value;visible=value;camera.enabled=value;dragging=false;cancel_secondary()
    if value:
        if configured_terrain!=terrain:
            terrain_view.configure(terrain);configured_terrain=terrain;units_view.army_colors=armies;fit()
        camera.force_update_scroll()
func fit() -> void:
    if terrain==null:return
    var size:=get_viewport_rect().size
    camera.zoom=Vector2.ONE*clampf(minf(size.x/terrain.size.x,size.y/terrain.size.y)*.92,.01,6)
    camera.position=terrain.size*.5;camera.force_update_scroll();fitted=true;follow_id=-1
func viewport_resized() -> void:
    dragging=false;cancel_secondary()
    if enabled and fitted:fit()
func screen_to_world(pixel: Vector2) -> Vector2:return get_viewport().get_canvas_transform().affine_inverse()*pixel
func world_to_screen(point: Vector2) -> Vector2:return get_viewport().get_canvas_transform()*point
func pick(pixel: Vector2) -> int:return units_view.pick(screen_to_world(pixel))
func focus_on(point: Vector2) -> void:camera.position=point;fitted=false;camera.force_update_scroll()
func display(a: Object,b: Object,alpha: float,time: float,events: Array,selected: int) -> void:
    units_view.selected=selected;units_view.zoom=camera.zoom.x;units_view.display(a,b,alpha,time,events);overlay.queue_redraw()
func advance(delta: float,move: Vector2,fast: bool) -> void:
    if not enabled:return
    if move.length_squared()>0:
        fitted=false;follow_id=-1;camera.position+=move.normalized()*delta*450/camera.zoom.x*(3 if fast else 1)
    elif follow_id>=0:
        var u: Object=units_view.current.units.get(follow_id) if units_view.current!=null else null
        if u==null or not u.active:follow_id=-1
        else:camera.position=camera.position.lerp(units_view.unit_pose(u).position,1-exp(-10*delta))
    camera.force_update_scroll()
func cancel_secondary() -> void:secondary_down=false;secondary_cancelled.emit()
func _unhandled_input(event: InputEvent) -> void:
    if not enabled or not navigation_enabled:return
    if event is InputEventMouseButton:
        if event.button_index==MOUSE_BUTTON_LEFT and event.pressed:selection_requested.emit(event.position)
        elif event.button_index==MOUSE_BUTTON_RIGHT:
            if event.pressed:secondary_down=true;secondary_started.emit(event.position)
            elif secondary_down:secondary_down=false;secondary_requested.emit(event.position)
        elif event.button_index==MOUSE_BUTTON_MIDDLE:
            dragging=event.pressed
            if dragging:cancel_secondary();follow_id=-1;fitted=false
        elif event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
            var before:=screen_to_world(event.position);var factor:=1.15 if event.button_index==MOUSE_BUTTON_WHEEL_UP else 1/1.15
            camera.zoom=Vector2.ONE*clampf(camera.zoom.x*factor,.01,6);camera.force_update_scroll();camera.position+=before-screen_to_world(event.position);camera.force_update_scroll();fitted=false
    elif event is InputEventMouseMotion:
        if dragging:camera.position-=event.relative/camera.zoom.x;camera.force_update_scroll()
        elif secondary_down:secondary_updated.emit(event.position)
func draw_overlays() -> void:
    if not enabled or units_view.current==null:return
    var width: float=1/maxf(.01,camera.zoom.x)
    for objective in mission_data.get("definitions",[]):
        if objective.type=="defeat":continue
        var center:=Vector2(objective.position.x,objective.position.y)
        overlay.draw_arc(center,objective.radius,0,TAU,96,Color.GOLD,2*width,true)
    if deployment and not deployment_zones.is_empty():
        for zone in deployment_zones:overlay.draw_rect(zone,Color(.3,.7,1),false,width)
    elif deployment:
        overlay.draw_rect(Rect2(20,20,terrain.size.x*.32-20,terrain.size.y-40),Color(.3,.7,1),false,width)
        overlay.draw_rect(Rect2(terrain.size.x*.68,20,terrain.size.x*.32-20,terrain.size.y-40),Color(1,.4,.3),false,width)
    var u: Object=units_view.current.units.get(units_view.selected)
    if u!=null and u.active:
        var pose: Dictionary=units_view.unit_pose(u);var radius: float=maxf(u.weapon_range,u.info.weapon_range)
        if radius>0:
            overlay.draw_arc(pose.position,radius,0,TAU,128,Color(.4,.8,1,.5),width,true)
            overlay.draw_arc(pose.position,radius,pose.facing-.65,pose.facing+.65,32,Color(.4,1,.65),2*width,true)
    if ghost==null or not ghost.active or u==null:return
    var front:=Vector2.from_angle(ghost.facing);var side:=front.rotated(PI/2);var points:=PackedVector2Array()
    for signs in [Vector2(-1,-1),Vector2(1,-1),Vector2(1,1),Vector2(-1,1)]:points.append(ghost.destination+front*signs.x*u.depth/2+side*signs.y*u.width/2)
    var color:=Color(.2,.9,1) if ghost.valid else Color(1,.2,.2)
    overlay.draw_colored_polygon(points,Color(color,.2));points.append(points[0]);overlay.draw_polyline(points,color,2*width,true)
    var tip: Vector2=ghost.destination+front*(u.depth/2+12)
    overlay.draw_line(ghost.destination,tip,color,2*width,true)
    overlay.draw_line(tip,tip-front*5+side*4,color,2*width,true);overlay.draw_line(tip,tip-front*5-side*4,color,2*width,true)
