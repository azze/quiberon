extends Node3D
const Kit = preload("res://scripts/three_d/mesh_kit.gd")
const World = preload("res://scripts/three_d/world_3d.gd")
var groups: Array = []
var tree_positions: Array = []
var count: int = 0
var last_focus: Vector2 = Vector2(INF,INF)
var last_distant: bool = false
var fade_radius: float = 45.0
var distant_span: float = 950
func configure(surface: Object, settings: Resource) -> void:
    for child in get_children():child.queue_free()
    groups.clear();tree_positions.clear();count = 0;last_focus = Vector2(INF,INF)
    fade_radius = settings.selected_foliage_radius;distant_span = settings.distant_forest_span
    var positions: Dictionary = {};var visited: Dictionary = {};var spacing: float = maxf(5,settings.forest_spacing)
    for f in surface.model.forests:
        for x in range(int(floor((f.center.x-f.radius.x)/spacing)),int(ceil((f.center.x+f.radius.x)/spacing))+1):
            for z in range(int(floor((f.center.y-f.radius.y)/spacing)),int(ceil((f.center.y+f.radius.y)/spacing))+1):
                var key := Vector2i(x,z)
                if visited.has(key):continue
                visited[key]=true
                var noise := fposmod(sin(x*127.1+z*311.7)*43758.5453,1.0)
                var point := Vector2(x*spacing+sin(z*4.1)*spacing*.2,z*spacing+cos(x*3.7)*spacing*.2)
                var density: float=surface.exact_forest_density(point)
                if surface.model.is_water(point) or not Rect2(Vector2.ZERO,surface.size).has_point(point) or density<=.05 or noise>=density:continue
                var chunk := Vector2i(floor(point.x/settings.forest_chunk_metres),floor(point.y/settings.forest_chunk_metres))
                if not positions.has(chunk):positions[chunk]=[]
                positions[chunk].append({"point":World.ground(point,surface.height_at(point)),"scale":.8+noise*.45,"yaw":noise*TAU})
    var trunk_mesh := Kit.tree(false);var canopy_mesh := Kit.tree(true)
    var trunks_material := Kit.material();var canopy_material := Kit.material(false,true)
    for chunk in positions:
        var items: Array = positions[chunk]
        var trunks := Kit.batch(trunk_mesh,items.size(),trunks_material)
        var canopy := Kit.batch(canopy_mesh,items.size(),canopy_material,true)
        add_child(trunks);add_child(canopy)
        for i in range(items.size()):
            var item: Dictionary=items[i]
            var t := Transform3D(Basis(Vector3.UP,item.yaw).scaled(Vector3.ONE*item.scale),item.point)
            trunks.multimesh.set_instance_transform(i,t);canopy.multimesh.set_instance_transform(i,t)
            canopy.multimesh.set_instance_color(i,Color(1,1,1,1))
            tree_positions.append(item.point)
        groups.append({"canopy":canopy,"items":items});count += items.size()

func update_visibility(selected: Variant, span: float) -> void:
    var point: Vector2 = World.horizontal(selected) if selected != null else Vector2(INF,INF)
    var distant := span > distant_span
    if point == last_focus and distant == last_distant:return
    if is_finite(point.x) and is_finite(last_focus.x) and point.distance_to(last_focus)<3 and distant==last_distant:return
    last_focus=point;last_distant=distant
    for group in groups:
        var mm: MultiMesh = group.canopy.multimesh
        for i in range(group.items.size()):
            var distance := World.horizontal(group.items[i].point).distance_to(point)
            var alpha := lerpf(.16,1.0,smoothstep(fade_radius*.55,fade_radius,distance))
            if distant:alpha=minf(alpha,.45)
            mm.set_instance_color(i,Color(1,1,1,alpha))
