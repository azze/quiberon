extends Node3D
## Read-only destination footprint, figures and heading. No simulation authority.
const World=preload("res://scripts/three_d/world_3d.gd")
var active: bool=false
var destination:=Vector2.ZERO
var facing: float=0
var valid: bool=true
var reason: String=""
var fill:=MeshInstance3D.new()
var outline:=MeshInstance3D.new()
var figure:=MultiMeshInstance3D.new()
var last_key: Array=[]
func _ready() -> void:
    for node in [fill,outline,figure]:add_child(node);node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    var m:=StandardMaterial3D.new();m.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;m.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;m.cull_mode=BaseMaterial3D.CULL_DISABLED
    m.albedo_color=Color(.2,.85,1,.15);fill.material_override=m
    var line:=m.duplicate();line.albedo_color=Color(.3,.95,1,.95);line.no_depth_test=true;outline.material_override=line
    var ghost:=m.duplicate();ghost.albedo_color=Color(.3,.85,1,.45);figure.material_override=ghost
    hide_preview()
func hide_preview() -> void:active=false;visible=false;last_key=[]
func display(u: Object,point: Vector2,angle: float,allowed: bool,why: String,renderer: Object) -> void:
    active=true;visible=true;destination=point;facing=angle;valid=allowed;reason=why
    var key: Array=[u.info.id,point,angle,allowed,u.formation,u.width,u.depth]
    if key==last_key:return
    last_key=key
    var color:=Color(.25,.9,1) if valid else Color(1,.25,.2)
    fill.material_override.albedo_color=Color(color,.15);outline.material_override.albedo_color=Color(color,.95);figure.material_override.albedo_color=Color(color,.45)
    var surface: Object=renderer.surface;var front:=Vector2.from_angle(angle);var side:=front.rotated(PI/2)
    var corners: Array=[]
    for offsets in [Vector2(-1,-1),Vector2(1,-1),Vector2(1,1),Vector2(-1,1)]:corners.append(point+front*offsets.x*u.depth*.5+side*offsets.y*u.width*.5)
    var mesh:=ImmediateMesh.new();mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
    for index in [0,1,2,0,2,3]:mesh.surface_add_vertex(World.ground(corners[index],surface.height_at(corners[index])+.3))
    mesh.surface_end();fill.mesh=mesh
    var lines:=ImmediateMesh.new();lines.surface_begin(Mesh.PRIMITIVE_LINES)
    for i in 4:segment(lines,corners[i],corners[(i+1)%4],surface)
    var tip: Vector2=point+front*(u.depth*.5+12)
    segment(lines,point,tip,surface);segment(lines,tip,tip-front*5+side*4,surface);segment(lines,tip,tip-front*5-side*4,surface)
    lines.surface_end();outline.mesh=lines
    if renderer.mesh_cache.has(u.info.archetype):
        var capacity: int=mini(16,u.info.guns) if u.info.category=="artillery" and u.info.guns>0 else 16
        if figure.multimesh==null or figure.multimesh.mesh!=renderer.mesh_cache[u.info.archetype]:
            figure.multimesh=MultiMesh.new();figure.multimesh.transform_format=MultiMesh.TRANSFORM_3D;figure.multimesh.mesh=renderer.mesh_cache[u.info.archetype];figure.multimesh.instance_count=capacity
        var slots: Array=renderer.layout(u,capacity);var basis:=World.facing_basis(angle)
        for i in slots.size():
            var p: Vector2=point+slots[i].rotated(angle)
            figure.multimesh.set_instance_transform(i,Transform3D(basis,World.ground(p,surface.height_at(p)+.2)))
func segment(lines: ImmediateMesh,a: Vector2,b: Vector2,surface: Object) -> void:
    var count:=maxi(1,ceili(a.distance_to(b)/5))
    for i in count:
        for t in [float(i)/count,float(i+1)/count]:
            var p:=a.lerp(b,t);lines.surface_add_vertex(World.ground(p,surface.height_at(p)+.4))
