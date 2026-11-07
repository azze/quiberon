extends Node3D
const Frame = preload("res://scripts/battle_frame.gd")
const World = preload("res://scripts/three_d/world_3d.gd")
const Kit = preload("res://scripts/three_d/mesh_kit.gd")
const FlatWorld = preload("res://scripts/world_coordinates.gd")
var surface: Object
var settings: Resource
var current: Frame
var following: Frame
var alpha: float = 0.0
var selected: int = -1
var army_colors: Dictionary = {}
var visuals: Dictionary = {}
var mesh_cache: Dictionary = {}
var layout_cache: Dictionary = {}
var poses: Dictionary = {}
var profiles: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://resources/unit_visuals.json"))
var material: StandardMaterial3D = Kit.material()
var outlines := MeshInstance3D.new()
var lines := ImmediateMesh.new()
var line_material: StandardMaterial3D = Kit.material(true,true)
var visible_figures: int = 0
var active_count: int = 0
var update_ms: float = 0
var last_time: float = -INF
var last_lod: bool = false
var last_selected: int = -2

func _ready() -> void:
    outlines.mesh=lines;outlines.material_override=line_material;outlines.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;add_child(outlines)

func configure(value: Object, config: Resource, colors: Dictionary) -> void:
    surface=value;settings=config;army_colors=colors
    for visual in visuals.values():remove_child(visual.root);visual.root.queue_free()
    visuals.clear();poses.clear();layout_cache.clear();invalidate()

func create_visual(u: Frame.UnitState) -> Dictionary:
    var key: String="transport" if u.transport else u.info.archetype
    if not mesh_cache.has(key):mesh_cache[key]=Kit.wagon() if u.transport else Kit.figure(profiles.get(key,{}),u.info.category)
    var maximum: int = maxi(1,settings.figures_per_regiment)
    if u.info.category=="artillery":maximum=maxi(1,u.info.guns if u.info.guns>0 else 4)
    var node := Node3D.new();add_child(node)
    var figures := Kit.batch(mesh_cache[key],maximum,material)
    figures.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON if settings.shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    node.add_child(figures)
    var result := {"root":node,"figures":figures,"capacity":maximum,"visible_count":maximum}
    visuals[u.info.id]=result;return result

func layout(u: Frame.UnitState, capacity: int) -> Array:
    var key := "%s/%s/%s/%s" % [u.formation,u.width,u.depth,capacity]
    if layout_cache.has(key):return layout_cache[key]
    var columns := clampi(int(round(sqrt(capacity*u.width/maxf(1,u.depth)))),1,capacity)
    var rows := int(ceil(float(capacity)/columns))
    var points: Array=[]
    for row in range(rows):
        for col in range(columns):
            var x := (float(row)+.5)/rows-.5;var z := (float(col)+.5)/columns-.5
            var point:=Vector2(x*u.depth*.85,z*u.width*.88)
            if u.formation=="skirmish":point+=Vector2(sin(col*2.17+row)*.9,cos(row*2.41+col)*1.3)
            points.append(point)
    # Stable centre-out order: casualties hide outer slots without repacking.
    points.sort_custom(func(a,b):return a.length_squared()<b.length_squared())
    points.resize(capacity);layout_cache[key]=points;return points

func invalidate() -> void:last_time = -INF

func display(a: Frame,b: Frame,t: float,time: float,span: float) -> void:
    var lod: bool=span>settings.figure_lod_span
    if a==current and b==following and t==alpha and time==last_time and lod==last_lod and selected==last_selected:
        update_ms=0;return
    last_time=time;last_lod=lod;last_selected=selected
    var start := Time.get_ticks_usec();current=a;following=b;alpha=t;poses.clear();visible_figures=0;active_count=0
    for visual in visuals.values():visual.root.visible=false
    for u in a.units.values():
        if not u.observed:continue
        var next: Variant=b.units.get(u.info.id)
        var pos := World.point_between(u,next,t);var facing := World.angle_between(u,next,t)
        var height: float=surface.height_at(pos)
        poses[u.info.id]={"position":pos,"facing":facing,"world":World.ground(pos,height)}
        var visual: Dictionary=visuals.get(u.info.id,{})
        if visual.is_empty():visual=create_visual(u)
        visual.root.visible=u.active
        if not u.active or not u.observed:visual.visible_count=0;continue
        active_count+=1
        visual.root.position=World.ground(pos,height);visual.root.rotation.y=World.yaw(facing)
        var count := clampi(int(ceil(float(visual.capacity)*u.strength/maxi(1,u.info.maximum))),0,visual.capacity)
        visual.visible_count=count
        var detailed: bool=span<=settings.figure_lod_span or u.info.id==selected
        visual.figures.multimesh.visible_instance_count=count if detailed else 0
        if not detailed:continue
        visible_figures+=count
        var slots := layout(u,visual.capacity);var basis := World.facing_basis(facing)
        var disorder: float=(1-u.cohesion/100.0)*settings.figure_disorder_metres+(1.2 if u.state=="routing" else 0.0)
        if u.info.category=="cavalry":disorder*=.35
        for i in range(count):
            var local: Vector2=slots[i]
            local+=Vector2(sin(i*13.7+u.info.id*2.1+time*.4),cos(i*8.3+u.info.id+time*.3))*disorder
            local=local.clamp(Vector2(-u.depth*.47,-u.width*.47),Vector2(u.depth*.47,u.width*.47))
            var offset := basis*Vector3(local.x,0,local.y)
            var ground: float=surface.height_at(pos+Vector2(offset.x,offset.z))-height
            visual.figures.multimesh.set_instance_transform(i,Transform3D(Basis.IDENTITY,Vector3(local.x,ground,local.y)))
    draw_outlines(span)
    update_ms=(Time.get_ticks_usec()-start)/1000.0

func ground_position(uid: int) -> Variant:
    if current==null or not current.units.has(uid) or not current.units[uid].active or not poses.has(uid):return null
    return poses[uid].world

func pick(point: Vector3) -> int:
    if current==null:return -1
    var keys := current.units.keys();keys.reverse()
    for uid in keys:
        var u: Frame.UnitState=current.units[uid]
        if u.active and u.observed and poses.has(uid) and FlatWorld.contains(World.horizontal(point),poses[uid].position,poses[uid].facing,u.width,u.depth):return uid
    return -1

func line(a: Vector2,b: Vector2,color: Color) -> void:
    # Subdivide long formation edges so their line follows the same mesh surface.
    var pieces := maxi(1,int(ceil(a.distance_to(b)/8)))
    for i in range(pieces):
        for p in [a.lerp(b,float(i)/pieces),a.lerp(b,float(i+1)/pieces)]:
            lines.surface_set_color(color.srgb_to_linear());lines.surface_add_vertex(World.ground(p,surface.height_at(p)+.12))

func draw_outlines(span: float) -> void:
    lines.clear_surfaces()
    if current==null or poses.is_empty() or active_count==0:return
    lines.surface_begin(Mesh.PRIMITIVE_LINES)
    for u in current.units.values():
        if not u.active or not u.observed:continue
        var pose: Dictionary=poses[u.info.id]
        var color: Color=Color("#ffe286") if selected==u.info.id else army_colors.get(u.info.army,Color.WHITE)
        color.a=1 if selected==u.info.id else .65
        var corners := FlatWorld.footprint(pose.position,pose.facing,u.width,u.depth)
        for i in range(4):line(corners[i],corners[i+1],color)
        var forward := Vector2.from_angle(pose.facing)
        var tip: Vector2=pose.position+forward*(u.depth/2+8)
        line(pose.position,tip,color);line(tip,tip-forward.rotated(.65)*5,color);line(tip,tip-forward.rotated(-.65)*5,color)
    lines.surface_end()
