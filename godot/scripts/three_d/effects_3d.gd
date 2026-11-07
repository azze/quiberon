extends Node3D
const World = preload("res://scripts/three_d/world_3d.gd")
const Kit = preload("res://scripts/three_d/mesh_kit.gd")
var debug_enabled: bool=false
var selected_id: int=-1
var debug_view:=MeshInstance3D.new()
var debug_mesh:=ImmediateMesh.new()
var surface: Object
var balls: MultiMeshInstance3D
var smoke: MultiMeshInstance3D
var halos := MeshInstance3D.new()
var halo_mesh := ImmediateMesh.new()
var ball_count: int = 0
var smoke_count: int = 0
func _ready() -> void:
    var sphere := SphereMesh.new();sphere.radius=.25;sphere.height=.5;sphere.radial_segments=8;sphere.rings=4
    balls=Kit.batch(sphere,256,Kit.material(true),true);add_child(balls)
    var puff := SphereMesh.new();puff.radius=1;puff.height=2;puff.radial_segments=8;puff.rings=4
    smoke=Kit.batch(puff,512,Kit.material(true,true),true);smoke.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;add_child(smoke)
    debug_view.mesh=debug_mesh;debug_view.material_override=Kit.material(true,true);add_child(debug_view)
    halos.mesh=halo_mesh;halos.material_override=Kit.material(true,true);add_child(halos)
func display(a: Object,b: Object,alpha: float,time: float,events: Array) -> void:
    if surface==null:return
    ball_count=0;smoke_count=0
    if a.shots.size()>balls.multimesh.instance_count:balls.multimesh.instance_count=a.shots.size()
    for p in a.shots.values():
        balls.multimesh.set_instance_transform(ball_count,Transform3D(Basis.IDENTITY,World.projectile(p,b.shots.get(p.id),alpha)))
        balls.multimesh.set_instance_color(ball_count,Color("#e4b85f").srgb_to_linear());ball_count+=1
    balls.multimesh.visible_instance_count=ball_count
    halo_mesh.clear_surfaces();var rings: Array=[]
    for event in events:
        var age: float=time-event.time
        if not event.has_position or age<0 or age>event.duration:continue
        var fade := 1-age/maxf(.01,event.duration)
        if event.kind in ["volley","artillery_fire","impact","charge_impact","projectile_bounce","projectile_hit","friendly_fire"]:
            var count := 7 if event.kind in ["volley","artillery_fire"] else 1
            for i in range(count):
                if smoke_count>=smoke.multimesh.instance_count:break
                var pos: Vector2=event.position+Vector2.from_angle(event.facing+PI/2)*(float(i)/maxi(1,count-1)-.5)*event.width
                pos+=Vector2.from_angle(event.facing)*age*2
                var at := World.ground(pos,surface.height_at(pos)+1.3+age*.8)
                var radius := 1.2+age*1.5
                smoke.multimesh.set_instance_transform(smoke_count,Transform3D(Basis.IDENTITY.scaled(Vector3.ONE*radius),at))
                var color := Color(.85,.85,.77,fade*.35)
                if age<.12:color=Color(1,.79,.32,.8)
                smoke.multimesh.set_instance_color(smoke_count,color.srgb_to_linear());smoke_count+=1
        if event.kind in ["charge_start","charge_impact","rout","rally","impact","melee_enter","destroyed","charge_repulsed","breakthrough","pursuit_start","projectile_bounce","projectile_hit","friendly_fire"]:rings.append({"event":event,"age":age,"fade":fade})
    smoke.multimesh.visible_instance_count=smoke_count
    if not rings.is_empty():
        halo_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
        for item in rings:
            var color := Color(1,.73,.3,item.fade)
            if item.event.kind=="rout":color=Color(.95,.35,.8,item.fade)
            if item.event.kind=="rally":color=Color(.3,1,.6,item.fade)
            for i in range(32):
                for j in [i,i+1]:
                    var p: Vector2=item.event.position+Vector2.from_angle(j*TAU/32)*(6+item.age*8)
                    halo_mesh.surface_set_color(color.srgb_to_linear());halo_mesh.surface_add_vertex(World.ground(p,surface.height_at(p)+.4))
        halo_mesh.surface_end()

    debug_mesh.clear_surfaces()
    if debug_enabled and (not a.shots.is_empty() or a.units.has(selected_id)):
        debug_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
        for shot in a.shots.values():
            var previous:=World.ground(shot.position,shot.height)
            for i in range(1,11):
                var t:=i*.05
                # Local trajectory tangent, not an authoritative future collision.
                var point: Vector2=shot.position+shot.velocity*t
                var next:=World.ground(point,shot.height)
                debug_mesh.surface_set_color(Color(1,.3,.1));debug_mesh.surface_add_vertex(previous);debug_mesh.surface_add_vertex(next);previous=next
        var u: Object=a.units.get(selected_id)
        if u!=null:
            var radius: float=125 if u.info.archetype=="royal_grenadiers" else u.weapon_range
            for i in range(64):
                for j in [i,i+1]:
                    var point: Vector2=u.position+Vector2.from_angle(j*TAU/64)*radius
                    debug_mesh.surface_set_color(Color(.3,1,.6));debug_mesh.surface_add_vertex(World.ground(point,surface.height_at(point)+.5))
            if a.units.has(u.target):
                for point in [u.position,a.units[u.target].position]:
                    debug_mesh.surface_set_color(Color(1,.8,.2));debug_mesh.surface_add_vertex(World.ground(point,surface.height_at(point)+2))
            for angle in [-.65,.65]:
                for point in [u.position,u.position+Vector2.from_angle(u.facing+angle)*u.weapon_range]:
                    debug_mesh.surface_set_color(Color(1,.6,.4));debug_mesh.surface_add_vertex(World.ground(point,surface.height_at(point)+.6))
        debug_mesh.surface_end()
