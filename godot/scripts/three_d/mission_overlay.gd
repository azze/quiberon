extends MeshInstance3D
const World=preload("res://scripts/three_d/world_3d.gd")
var signature: String=""
func _ready() -> void:
    var mat:=StandardMaterial3D.new();mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;mat.vertex_color_use_as_albedo=true;mat.no_depth_test=true;material_override=mat
func configure(data: Dictionary,surface: Object) -> void:
    if data.is_empty():visible=false;signature="";return
    visible=true
    var key: String="|".join(data.states.map(func(s):return s.id+":"+s.status))
    if signature==key:return
    signature=key;var lines:=ImmediateMesh.new();lines.surface_begin(Mesh.PRIMITIVE_LINES)
    for objective in data.definitions:
        if objective.type=="defeat":continue
        var center:=Vector2(objective.position.x,objective.position.y);var status: String="active"
        for state in data.states:
            if state.id==objective.id:status=state.status
        var color:=Color.GREEN if status=="success" else Color.RED if status=="failure" else Color.GOLD
        for i in 96:
            for angle in [TAU*i/96,TAU*(i+1)/96]:
                var p: Vector2=center+Vector2.from_angle(angle)*objective.radius
                lines.surface_set_color(color);lines.surface_add_vertex(World.ground(p,surface.height_at(p)+1))
    # A defeat-only mission has no geographic circle; a tiny centre marker avoids an empty ImmediateMesh surface.
    lines.surface_set_color(Color.TRANSPARENT);lines.surface_add_vertex(Vector3.ZERO);lines.surface_add_vertex(Vector3.ZERO)
    lines.surface_end();mesh=lines
