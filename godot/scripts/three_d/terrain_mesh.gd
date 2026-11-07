extends Node3D
const Surface = preload("res://scripts/three_d/terrain_surface.gd")
const Kit = preload("res://scripts/three_d/mesh_kit.gd")
var surface: Surface
var mesh_instance: MeshInstance3D
var builds: int = 0
var build_ms: float = 0
func configure(value: Surface) -> void:
    var start := Time.get_ticks_usec();surface = value
    if mesh_instance != null:mesh_instance.queue_free()
    var vertices := PackedVector3Array();var normals := PackedVector3Array();var colors := PackedColorArray();var indices := PackedInt32Array()
    for z in range(surface.nz + 1):
        for x in range(surface.nx + 1):
            var p := Vector2(x,z)*surface.step;var h := surface.vertex_height(x,z);var n := surface.normal_at(p)
            vertices.append(Vector3(p.x,h,p.y));normals.append(n)
            var color := Color("#66864f").lerp(Color("#b5a77b"), clampf(h/55.0,0,0.8))
            color = color.lerp(Color("#797465"),clampf((1-n.y)*2,0,.6))
            color = color.lerp(Color("#466b40"),surface.forest_densities[z*(surface.nx+1)+x]*.45)
            colors.append(color.srgb_to_linear())
    for z in range(surface.nz):
        for x in range(surface.nx):
            var a := z*(surface.nx+1)+x;var b := a+1;var c := a+surface.nx+1;var d := c+1
            indices.append_array(PackedInt32Array([a,b,c,b,d,c]))
    var arrays := [];arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX]=vertices;arrays[Mesh.ARRAY_NORMAL]=normals;arrays[Mesh.ARRAY_COLOR]=colors;arrays[Mesh.ARRAY_INDEX]=indices
    var mesh := ArrayMesh.new();mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
    mesh_instance = MeshInstance3D.new();mesh_instance.mesh = mesh;mesh_instance.material_override = Kit.material()
    # Godot uses clockwise front faces; explicit normals point up.
    mesh_instance.material_override.cull_mode = BaseMaterial3D.CULL_BACK
    add_child(mesh_instance);builds += 1;build_ms = (Time.get_ticks_usec()-start)/1000.0
