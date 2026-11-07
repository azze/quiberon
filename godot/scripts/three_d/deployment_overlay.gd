extends MeshInstance3D
## Static zone boundaries sampled from the same terrain as picking and figures.
func configure(surface: Object,zones: Array=[]) -> void:
    var lines:=ImmediateMesh.new();mesh=lines
    var material:=StandardMaterial3D.new();material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;material.vertex_color_use_as_albedo=true;material.no_depth_test=true
    lines.surface_begin(Mesh.PRIMITIVE_LINES,material)
    for army in range(zones.size() if not zones.is_empty() else 2):
        var left: float=20 if army==0 else surface.size.x*.68
        var right: float=surface.size.x*.32 if army==0 else surface.size.x-20
        var zone: Rect2=zones[army] if not zones.is_empty() else Rect2(left,20,right-left,surface.size.y-40)
        left=zone.position.x;right=zone.end.x
        var corners: Array=[zone.position,Vector2(zone.end.x,zone.position.y),zone.end,Vector2(zone.position.x,zone.end.y)]
        for i in 4:
            var a: Vector2=corners[i];var b: Vector2=corners[(i+1)%4];var steps:=maxi(1,ceili(a.distance_to(b)/5))
            for j in steps:
                for fraction in [float(j)/steps,float(j+1)/steps]:
                    var point:=a.lerp(b,fraction);lines.surface_set_color(Color("#69b8ff") if army==0 else Color("#ff8575"));lines.surface_add_vertex(Vector3(point.x,surface.height_at(point)+.8,point.y))
    lines.surface_end()
