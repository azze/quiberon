extends MeshInstance3D
## Nominal weapon envelope; terrain/LOS and friendly screens still govern firing.
const World=preload("res://scripts/three_d/world_3d.gd")
var radius: float=0
var last_key: Array=[]
var builds: int=0
func _ready() -> void:
    var m:=StandardMaterial3D.new();m.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;m.vertex_color_use_as_albedo=true;m.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;m.no_depth_test=true
    material_override=m;cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;visible=false
func display(u: Object,pose: Dictionary,surface: Object) -> void:
    radius=maxf(u.weapon_range,u.info.weapon_range) if u!=null and u.active else 0
    visible=radius>0
    if not visible:last_key=[];return
    var center: Vector2=pose.position;var angle: float=pose.facing
    var key: Array=[center,angle,radius,surface]
    if key==last_key:return
    last_key=key;builds+=1
    var lines:=ImmediateMesh.new();lines.surface_begin(Mesh.PRIMITIVE_LINES)
    for i in 128:
        var middle:=wrapf((i+.5)*TAU/128-angle,-PI,PI)
        var color:=Color(.4,1,.65,.9) if absf(middle)<=.65 else Color(.4,.8,1,.4)
        segment(lines,center+Vector2.from_angle(i*TAU/128)*radius,center+Vector2.from_angle((i+1)*TAU/128)*radius,surface,color)
    for turn in [-.65,.65]:segment(lines,center,center+Vector2.from_angle(angle+turn)*radius,surface,Color(.4,1,.65,.65))
    lines.surface_end();mesh=lines
func segment(lines: ImmediateMesh,a: Vector2,b: Vector2,surface: Object,color: Color) -> void:
    var count:=maxi(1,ceili(a.distance_to(b)/8))
    for i in count:
        var start:=a.lerp(b,float(i)/count);var end:=a.lerp(b,float(i+1)/count)
        if not Rect2(Vector2.ZERO,surface.size).has_point(start) or not Rect2(Vector2.ZERO,surface.size).has_point(end):continue
        for point in [start,end]:
            lines.surface_set_color(color);lines.surface_add_vertex(World.ground(point,surface.height_at(point)+.7))
