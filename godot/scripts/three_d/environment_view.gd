extends Node3D
## Static geometry from the authoritative environment export. No gameplay or RNG.
const Kit=preload("res://scripts/three_d/mesh_kit.gd")
const World=preload("res://scripts/three_d/world_3d.gd")
var surface: Object
var data: Dictionary={}
var atmosphere: Environment
var sunlight: DirectionalLight3D
var rain: MultiMeshInstance3D
var debug_mesh:=ImmediateMesh.new()
var debug_node:=MeshInstance3D.new()
var debug_enabled:=false
var builds:=0
var feature_count:=0
var line_count:=0
var crossing_labels: Dictionary={}
var crossing_owners: Dictionary={}
func _ready() -> void:
    debug_node.mesh=debug_mesh;debug_node.material_override=Kit.material(true);add_child(debug_node)
func configure(ground: Object,definition: Dictionary,sky: Environment,light: DirectionalLight3D) -> void:
    surface=ground;data=definition;atmosphere=sky;sunlight=light
    for child in get_children():
        if child!=debug_node:remove_child(child);child.queue_free()
    crossing_labels.clear()
    rain=null;builds+=1;feature_count=0
    var tool:=SurfaceTool.new();tool.begin(Mesh.PRIMITIVE_TRIANGLES);var vertices:=0
    for water in data.get("water",[]):
        var points:=PackedVector2Array(water.points);var triangles:=Geometry2D.triangulate_polygon(points)
        for index in triangles:
            tool.set_color(Color("#4d8b9d").srgb_to_linear());tool.set_normal(Vector3.UP);tool.add_vertex(World.ground(points[index],water.height));vertices+=1
        feature_count+=1
    if vertices>0:
        tool.index();var node:=MeshInstance3D.new();node.mesh=tool.commit();node.material_override=Kit.material();add_child(node)
    var roads:=SurfaceTool.new();roads.begin(Mesh.PRIMITIVE_TRIANGLES);vertices=0
    for road in data.get("roads",[]):
        for i in range(1,road.points.size()):
            var a: Vector2=road.points[i-1];var b: Vector2=road.points[i]
            var n:=maxi(1,int(ceil(a.distance_to(b)/4)));var side: Vector2=(b-a).normalized().orthogonal()*road.width/2
            for j in n:
                var p:=a.lerp(b,float(j)/n);var q:=a.lerp(b,float(j+1)/n);var mid: Vector2=(p+q)/2
                if surface.model.is_water(mid) and surface.model.crossing_at(mid).is_empty():continue
                var color:=Color("#968469") if road.surface=="mainroad" else Color("#9c936e")
                for v in [p+side,q+side,p-side,p-side,q+side,q-side]:
                    roads.set_color(color.srgb_to_linear());roads.set_normal(Vector3.UP);roads.add_vertex(World.ground(v,surface.height_at(v)+.04));vertices+=1
        feature_count+=1
    if vertices>0:
        roads.index();var node:=MeshInstance3D.new();node.mesh=roads.commit();node.material_override=Kit.material();add_child(node)
    for c in data.get("crossings",[]):
        feature_count+=1
        var label:=Label3D.new();label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;label.font_size=40;label.pixel_size=.1;label.no_depth_test=true;label.visible=false
        label.position=World.ground(c.position,c.height+8);add_child(label);crossing_labels[c.id]=label
        if c.kind=="bridge":
            box(Vector3(c.length,.35,c.width),World.ground(c.position,c.height-.175),c.facing,Color("#8c7656"))
            for side in [-1,1]:
                var local:=Vector2(0,side*(c.width/2-.3)).rotated(c.facing)
                box(Vector3(c.length,.55,.5),World.ground(c.position+local,c.height+.28),c.facing,Color("#b09b78"))
            for j in range(0,int(c.length),8):
                var offset:=Vector2(j-c.length/2,0).rotated(c.facing)
                box(Vector3(.16,.04,c.width-1),World.ground(c.position+offset,c.height+.025),c.facing,Color("#b4a07c"))
        else:
            var axis:=Vector2.RIGHT.rotated(c.facing)
            for sign in [-1,1]:
                var p: Vector2=c.position+axis*c.length/2*sign
                box(Vector3(1,2,1),World.ground(p,surface.height_at(p)+1),0,Color("#b6b5a0"))
    for f in data.get("defences",[]):
        feature_count+=1
        box(Vector3(f.depth,.95 if f.kind=="earthwork" else 1.2,f.width),World.ground(f.position,surface.height_at(f.position)+.45),f.facing,Color("#847554") if f.kind=="earthwork" else Color("#675843"))
    var weather: String=data.get("weather","clear")
    atmosphere.fog_enabled=weather=="fog"
    atmosphere.background_color=Color("#aebbc0") if weather!="clear" else Color("#c3cfcc")
    atmosphere.ambient_light_energy=.55 if weather=="rain" else .65
    atmosphere.fog_light_color=Color("#bcc8c6");sunlight.light_energy=.85 if weather=="rain" else 1.1
    if weather=="rain":create_rain()
func box(size: Vector3,point: Vector3,facing: float,color: Color) -> void:
    var tool:=SurfaceTool.new();tool.begin(Mesh.PRIMITIVE_TRIANGLES);Kit.part(tool,Kit.box(size),Vector3.ZERO,color);tool.index()
    var node:=MeshInstance3D.new();node.mesh=tool.commit();node.material_override=Kit.material();node.position=point;node.rotation.y=World.yaw(facing);add_child(node)
func create_rain() -> void:
    var mesh:=ImmediateMesh.new();mesh.surface_begin(Mesh.PRIMITIVE_LINES);mesh.surface_add_vertex(Vector3(0,0,0));mesh.surface_add_vertex(Vector3(.25,1.6,.1));mesh.surface_end()
    rain=Kit.batch(mesh,200,Kit.material(true,true));add_child(rain)
    var shader:=Shader.new();shader.code="shader_type spatial; render_mode unshaded, shadows_disabled; void vertex(){VERTEX.y=mod(VERTEX.y+INSTANCE_CUSTOM.x*40.0-TIME*28.0,40.0);} void fragment(){ALBEDO=vec3(.63,.74,.81);ALPHA=.5;}"
    var mat:=ShaderMaterial.new();mat.shader=shader;rain.material_override=mat
    rain.multimesh.instance_count=0;rain.multimesh.use_custom_data=true;rain.multimesh.instance_count=200
    for i in 200:
        var x:=fposmod(sin(i*12.13+42)*43758.1,1.0);var z:=fposmod(sin(i*7.19+81)*17341.9,1.0)
        rain.multimesh.set_instance_transform(i,Transform3D(Basis.IDENTITY,Vector3((x-.5)*240,0,(z-.5)*240)))
        rain.multimesh.set_instance_custom_data(i,Color(x,0,0,1))
func display(frame: Object,rig: Object,debug: bool) -> void:
    debug_enabled=debug;debug_node.visible=debug
    if atmosphere.fog_enabled:
        # Terrain fog is atmospheric; enemy visibility comes from unit LOS, not
        # 3D camera distance. High tactical cameras must not obscure nearby troops.
        atmosphere.fog_density=.54/(data.get("visibility_limit",180.)+maxf(0,rig.camera.global_position.y)*3)
    if rain!=null:rain.position=World.ground(rig.focus,surface.height_at(rig.focus))
    for label in crossing_labels.values():label.visible=debug
    if not debug:return
    for id in crossing_labels:
        var travelling: Array=[];var waiting: Array=[]
        for u in frame.units.values():
            if not u.observed or u.crossing!=id:continue
            if u.environment_state.begins_with("Waiting"):waiting.append(str(u.info.id))
            else:travelling.append(str(u.info.id))
        crossing_labels[id].text=id+"\nowner: "+str(crossing_owners.get(id,"none"))+" | approaching: "+", ".join(travelling)+" | wait: "+", ".join(waiting)
    debug_mesh.clear_surfaces();line_count=0
    for piece in data.get("water",[]):
        for i in piece.points.size():line(piece.points[i],piece.points[(i+1)%piece.points.size()],Color.CYAN)
    for c in data.get("crossings",[]):
        line(c.entry,c.exit,Color.YELLOW)
        var side: Vector2=Vector2.UP.rotated(c.facing)*c.width/2
        line(c.entry+side,c.exit+side,Color.ORANGE);line(c.entry-side,c.exit-side,Color.ORANGE)
    for u in frame.units.values():
        if not u.observed:continue
        var p: Vector2=u.position
        for next in u.route_points:line(p,next,Color("#f7e591"));p=next
    if line_count>0:debug_mesh.surface_end()
func line(a: Vector2,b: Vector2,color: Color) -> void:
    if line_count==0:debug_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
    line_count+=1
    for p in [a,b]:debug_mesh.surface_set_color(color);debug_mesh.surface_add_vertex(World.ground(p,maxf(surface.height_at(p),.2)+1))
