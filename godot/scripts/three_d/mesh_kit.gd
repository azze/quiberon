extends RefCounted
## Procedural shared meshes, not per-soldier scene/physics objects. Local +X front.
static func material(unshaded: bool = false, transparent: bool = false) -> StandardMaterial3D:
    var m := StandardMaterial3D.new();m.vertex_color_use_as_albedo = true;m.vertex_color_is_srgb = false;m.roughness = 0.9
    if unshaded:m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    if transparent:m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    return m

static func box(size: Vector3) -> BoxMesh:
    var mesh := BoxMesh.new();mesh.size = size;return mesh

static func cylinder(radius: float, height: float, top: float = -1) -> CylinderMesh:
    var mesh := CylinderMesh.new();mesh.bottom_radius = radius;mesh.top_radius = top if top >= 0 else radius
    mesh.height = height;mesh.radial_segments = 8;mesh.rings = 1;return mesh

static func part(tool: SurfaceTool, mesh: Mesh, pos: Vector3, color: Color, rotation: Vector3 = Vector3.ZERO, scale: float = 1.0) -> void:
    var transform := Transform3D(Basis.from_euler(rotation).scaled(Vector3.ONE * scale), pos)
    var arrays := mesh.surface_get_arrays(0)
    var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
    var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
    var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
    for i in range(indices.size() if not indices.is_empty() else vertices.size()):
        var k := indices[i] if not indices.is_empty() else i
        tool.set_color(color.srgb_to_linear());tool.set_normal((transform.basis * normals[k]).normalized());tool.add_vertex(transform * vertices[k])

static func human(tool: SurfaceTool, profile: Dictionary, origin := Vector3.ZERO, scale: float = 1.0) -> void:
    var coat := Color(profile.get("coat", "#9b9b8d"));var dark := Color("#343733");var skin := Color("#c0a181")
    part(tool, box(Vector3(.3,.65,.45)), origin + Vector3(0,1.12,0)*scale, coat, Vector3.ZERO, scale)
    for side in [-1,1]:
        part(tool, box(Vector3(.19,.72,.17)), origin + Vector3(0,.43,side*.12)*scale, Color("#55594f"), Vector3.ZERO, scale)
        part(tool, box(Vector3(.16,.51,.14)), origin + Vector3(.04,1.12,side*.30)*scale, coat.darkened(.08), Vector3(0,0,-.15), scale)
    part(tool, box(Vector3(.29,.29,.28)), origin + Vector3(.02,1.64,0)*scale, skin, Vector3.ZERO, scale)
    var hat: String = profile.get("headwear", "cap")
    if hat != "none":
        var mesh: Mesh = box(Vector3(.34,.18,.34)) if hat == "square_cap" else cylinder(.20,.43 if hat == "tall_cap" else .20)
        part(tool, mesh, origin + Vector3(0,1.89 if hat == "tall_cap" else 1.84,0)*scale, dark, Vector3.ZERO, scale)
    else:
        part(tool, box(Vector3(.29,.09,.28)), origin + Vector3(0,1.81,0)*scale, dark, Vector3.ZERO, scale)
    if profile.get("armour",false):part(tool,box(Vector3(.33,.48,.47)),origin+Vector3(0,1.17,0)*scale,Color("#a9aba3"),Vector3.ZERO,scale)
    if profile.get("scythe",false):
        part(tool,box(Vector3(.055,2.1,.055)),origin+Vector3(.28,1.25,-.38)*scale,Color("#735334"),Vector3.ZERO,scale)
        part(tool,box(Vector3(.65,.08,.06)),origin+Vector3(.55,2.27,-.38)*scale,Color("#b9c1be"),Vector3(0,0,.22),scale)
    else:
        part(tool, box(Vector3(.055,1.35,.055)), origin + Vector3(.25,1.17,-.38)*scale, Color("#654a32"), Vector3(0,0,-.17), scale)

static func horse(tool: SurfaceTool, profile: Dictionary, origin := Vector3.ZERO) -> void:
    var brown := Color(profile.get("horse", "#815536"))
    part(tool, box(Vector3(1.85,.75,.65)), origin+Vector3(0,1.24,0), brown)
    for x in [-.62,.62]:
        for z in [-.23,.23]:part(tool, box(Vector3(.18,1.0,.18)), origin+Vector3(x,.52,z), brown.darkened(.12))
    part(tool, box(Vector3(.40,.85,.40)), origin+Vector3(.77,1.70,0), brown, Vector3(0,0,-.30))
    part(tool, box(Vector3(.66,.36,.34)), origin+Vector3(1.0,2.02,0), brown)
    part(tool, box(Vector3(.15,.73,.15)), origin+Vector3(-1.0,.95,0), Color("#302d29"), Vector3(0,0,-.25))

static func figure(profile: Dictionary, category: String) -> ArrayMesh:
    var tool := SurfaceTool.new();tool.begin(Mesh.PRIMITIVE_TRIANGLES)
    if category == "cavalry":
        horse(tool, profile);human(tool, profile, Vector3(0,1.35,0), .85)
        if profile.get("lance",false):part(tool, box(Vector3(3.8,.045,.045)), Vector3(1.4,2.7,-.43), Color("#b9a780"), Vector3(0,0,.18))
    elif category == "artillery":
        part(tool, box(Vector3(1.8,.32,.65)), Vector3(-.1,.64,0), Color("#5e4e37"))
        part(tool, cylinder(.24,2.7), Vector3(.45,1.08,0), Color(profile.get("gun","#555f59")), Vector3(0,0,-PI/2+.08))
        for side in [-1,1]:part(tool, cylinder(.67,.18), Vector3(-.3,.68,side*.83), Color("#4d4131"), Vector3(PI/2,0,0))
        human(tool, profile, Vector3(-1.7,0,-1.5));human(tool, profile, Vector3(-1.9,0,1.6))
        if profile.get("horse_battery",false):horse(tool, profile, Vector3(-3.4,0,3))
    else:human(tool, profile)
    tool.index();return tool.commit()

static func tree(foliage: bool) -> ArrayMesh:
    var tool := SurfaceTool.new();tool.begin(Mesh.PRIMITIVE_TRIANGLES)
    if foliage:
        part(tool, cylinder(2.3,4.8,0), Vector3(0,4.9,0), Color("#426d42"))
        part(tool, cylinder(1.7,3.8,0), Vector3(0,7.0,0), Color("#507d46"))
    else:part(tool, cylinder(.26,3.8), Vector3(0,1.9,0), Color("#6e5540"))
    tool.index();return tool.commit()

static func batch(mesh: Mesh, count: int, mat: Material, colors: bool = false) -> MultiMeshInstance3D:
    var mm := MultiMesh.new();mm.transform_format = MultiMesh.TRANSFORM_3D;mm.use_colors = colors;mm.mesh = mesh;mm.instance_count = count
    var node := MultiMeshInstance3D.new();node.multimesh = mm;node.material_override = mat
    return node

static func wagon() -> ArrayMesh:
    var t:=SurfaceTool.new();t.begin(Mesh.PRIMITIVE_TRIANGLES)
    part(t,box(Vector3(3,1.1,1.6)),Vector3(0,1.1,0),Color("#967f5d"))
    part(t,box(Vector3(2.8,.3,1.5)),Vector3(0,1.8,0),Color("#c4b799"))
    for x in [-1,1]:
        for z in [-1,1]:part(t,cylinder(.55,.18),Vector3(x,.55,z*.9),Color("#45413a"),Vector3(PI/2,0,0))
    t.index();return t.commit()
