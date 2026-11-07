extends SceneTree
const Viewer=preload("res://scripts/three_d/viewer_3d.gd")
const Frame=preload("res://scripts/battle_frame.gd")
const World=preload("res://scripts/three_d/world_3d.gd")
const Surface=preload("res://scripts/three_d/terrain_surface.gd")
const Terrain=preload("res://scripts/three_d/terrain_mesh.gd")
const Forest=preload("res://scripts/three_d/forest_view.gd")
const Kit=preload("res://scripts/three_d/mesh_kit.gd")
var failed:=false
var checks:=0
func check(value: bool,message: String) -> void:
    checks+=1
    if not value:failed=true;push_error(message)
func _initialize() -> void:run.call_deferred()
func key(code: int) -> void:
    var event:=InputEventKey.new();event.keycode=code;event.physical_keycode=code;event.pressed=true;Input.parse_input_event(event)
    var up:=event.duplicate();up.pressed=false;Input.parse_input_event(up)
func run() -> void:
    root.size=Vector2i(1280,800)
    var viewer:=Viewer.new();root.add_child(viewer)
    await process_frame
    await process_frame
    viewer.playback.playing=false;viewer.set_process(false);viewer.seek(0)
    var initial_smoke: int=viewer.effects.smoke_count
    viewer.seek(60)
    check(viewer.playback!=null and viewer.viewport.size.x>100,"3D scene and viewport load")
    check(viewer.rig.perspective and viewer.rig.camera.projection==Camera3D.PROJECTION_PERSPECTIVE,"Viewer starts with physical perspective dolly controls")
    check(viewer.units.visuals.size()==12,"One visual root per regiment")
    var categories: Dictionary={}
    for unit in viewer.playback.current.units.values():categories[unit.info.category]=true
    for category in ["infantry","cavalry","artillery"]:check(categories.has(category),category+" supported")
    check(viewer.units.mesh_cache.size()>=6,"Specialist mesh profiles loaded")
    check(viewer.units.profiles.haudenosaunee_skirmishers.headwear=="none","Neutral woodland visual profile")
    check(viewer.units.profiles.commonwealth_uhlans.lance,"Uhlan lance silhouette")
    check(viewer.units.profiles.french_horse_artillery.horse_battery,"Horse artillery teams")
    var mesh: ArrayMesh=viewer.terrain_view.mesh_instance.mesh
    var arrays:=mesh.surface_get_arrays(0)
    check(arrays[Mesh.ARRAY_VERTEX].size()==viewer.surface.heights.size(),"Terrain grid vertices retained")
    var triangle: PackedInt32Array=arrays[Mesh.ARRAY_INDEX]
    var vertices: PackedVector3Array=arrays[Mesh.ARRAY_VERTEX]
    check((vertices[triangle[1]]-vertices[triangle[0]]).cross(vertices[triangle[2]]-vertices[triangle[0]]).y<0,"Terrain winding is Godot clockwise from above")
    check(viewer.terrain_view.mesh_instance.material_override.cull_mode==BaseMaterial3D.CULL_BACK,"Terrain lights/receives shadows on its front face")
    check(arrays[Mesh.ARRAY_INDEX].size()==viewer.surface.nx*viewer.surface.nz*6,"Indexed terrain triangles")
    var maximum: float=-INF
    for point in arrays[Mesh.ARRAY_VERTEX]:maximum=maxf(maximum,point.y)
    check(absf(maximum-viewer.surface.maximum)<.001 and maximum>20,"True hill geometry")
    check(viewer.forests.count>100,"Batched 3D forest")
    for point in viewer.forests.tree_positions:
        if absf(point.y-viewer.surface.height_at(World.horizontal(point)))>.001 or viewer.surface.model.forest_density(World.horizontal(point))<=.05:
            check(false,"Tree floats or lies outside forest");break
    var forest:=Forest.new();viewer.viewport.add_child(forest);forest.configure(viewer.surface,viewer.presentation)
    check(forest.tree_positions==viewer.forests.tree_positions,"Tree placement deterministic")
    forest.queue_free()
    var u: Object=viewer.playback.current.units[0]
    var visual: Dictionary=viewer.units.visuals[0]
    check(visual.capacity==32,"Configurable representative count")
    var slots:=viewer.units.layout(u,visual.capacity)
    for slot in slots:check(absf(slot.x)<=u.depth/2 and absf(slot.y)<=u.width/2,"Figure slot inside footprint")
    var parity:=true
    for z in range(0,viewer.surface.nz+1,7):
        for x in range(0,viewer.surface.nx+1,7):
            var point:=Vector2(x,z)*viewer.surface.step
            if absf(viewer.surface.vertex_height(x,z)-viewer.surface.model.elevation(point))>.001:parity=false
            if absf(viewer.surface.exact_forest_density(point)-viewer.surface.model.forest_density(point))>.000001:parity=false
    check(parity,"Finite-support/static-cell terrain queries preserve analytic features")
    var grid_grounded:=true
    for i in range(visual.visible_count):
        var at: Vector3=visual.root.transform*visual.figures.multimesh.get_instance_transform(i).origin
        if absf(at.y-viewer.surface.height_at(World.horizontal(at)))>.002:grid_grounded=false
    check(grid_grounded,"Individual bases follow sampled terrain")
    var strength: int=u.strength;u.strength=int(u.info.maximum*.25);viewer.units.invalidate();viewer.refresh_frame()
    check(visual.visible_count==8,"Casualty count without repacking slots")
    u.strength=strength;viewer.units.invalidate();viewer.refresh_frame()
    var old_formation: String=u.formation;var old_width: float=u.width;var old_depth: float=u.depth
    u.formation="column";u.width=22;u.depth=34;viewer.units.invalidate();viewer.refresh_frame()
    var column:=viewer.units.layout(u,visual.capacity)
    check(column!=slots,"Column changes rendered slots")
    u.formation=old_formation;u.width=old_width;u.depth=old_depth;viewer.units.invalidate();viewer.refresh_frame()
    var selected_point: Vector3=viewer.units.poses[0].world
    check(viewer.units.pick(selected_point)>=0,"Ground-footprint selection")
    viewer.units.selected=0;viewer.refresh_ui()
    check(viewer.hud.inspector.text.contains(u.info.commander),"3D inspection keeps commander")
    # World input really passes through the SubViewportContainer.
    var pixel: Vector2=viewer.rig.camera.unproject_position(selected_point)
    viewer.units.selected=-1
    var container: Control=viewer.viewport.get_parent()
    var click:=InputEventMouseButton.new();click.button_index=MOUSE_BUTTON_LEFT;click.pressed=true;click.position=pixel+container.global_position;Input.parse_input_event(click)
    await process_frame
    check(viewer.units.selected>=0,"Actual 3D viewport click selects")
    viewer.units.selected=0;viewer.action("focus")
    var span: float=viewer.rig.target_span;viewer.rig.advance(.5)
    check(viewer.rig.target_focus.distance_to(World.horizontal(selected_point))<.01 and viewer.rig.target_span==span,"Focus preserves scale")
    viewer.action("follow");check(viewer.rig.follow_id==0,"Follow button")
    viewer.rig.advance(.2,Vector2(1,0),0,false);check(viewer.rig.follow_id==-1,"Manual interruption")
    var old: bool=viewer.rig.perspective;key(KEY_P);await process_frame
    check(viewer.rig.perspective!=old,"Projection hotkey routes once")
    key(KEY_T);await process_frame;check(viewer.rig.overhead,"T overhead hotkey")
    key(KEY_T);await process_frame;check(not viewer.rig.overhead,"T returns to saved view")
    viewer.hud.settings_dialog.popup_centered();await process_frame
    var old_pitch: float=viewer.rig.target_pitch;var old_mode: bool=viewer.rig.perspective
    key(KEY_T);key(KEY_P);await process_frame
    check(viewer.rig.target_pitch==old_pitch and viewer.rig.perspective==old_mode,"Camera shortcuts blocked in settings/text entry")
    viewer.hud.settings_dialog.hide()
    var wheel:=InputEventMouseButton.new();wheel.button_index=MOUSE_BUTTON_WHEEL_UP;wheel.pressed=true;wheel.position=Vector2(600,90)
    var scale: float=viewer.rig.target_span;Input.parse_input_event(wheel);await process_frame
    check(viewer.rig.target_span==scale,"Scrolling over UI does not zoom the battlefield")
    # Replay rates do not enter camera integration; pause does not stop it.
    for speed in [1.,2.,4.]:
        viewer.playback.speed=speed;viewer.playback.playing=false;viewer.rig.configure(viewer.surface)
        var from: Vector2=viewer.rig.focus
        Input.action_press("camera_forward");viewer._process(.1);Input.action_release("camera_forward")
        check(viewer.rig.focus.distance_to(from)>0,"Camera moves with paused replay at "+str(speed))
    var active: Dictionary={}
    for unit in viewer.playback.current.units.values():active[unit.info.id]=unit.active;unit.active=false
    viewer.units.invalidate();viewer.refresh_frame()
    check(viewer.units.active_count==0 and viewer.units.visible_figures==0,"Destroyed/withdrawn army renders without empty geometry errors")
    for unit in viewer.playback.current.units.values():unit.active=active[unit.info.id]
    viewer.units.invalidate();viewer.refresh_frame()
    viewer.seek(0)
    check(viewer.effects.ball_count==0 and viewer.effects.smoke_count==initial_smoke,"Seeking backwards clears temporary effects")
    var builds: int=viewer.terrain_view.builds;viewer.rig.toggle_projection();viewer.rig.fit()
    check(viewer.terrain_view.builds==builds,"Camera does not rebuild terrain")
    var camera_pos: Vector2=viewer.rig.focus;viewer.rig.dragging=true
    var release:=InputEventMouseButton.new();release.button_index=MOUSE_BUTTON_MIDDLE;release.pressed=false;viewer._input(release)
    check(not viewer.rig.dragging,"Outside-viewport release ends dragging")
    viewer.seek(viewer.playback.source.times[-1]);check(not viewer.playback.playing,"End of recording pauses")
    check(not viewer.load_recording("user://missing.json") and viewer.playback!=null,"Invalid recording retains previous view")
    viewer.queue_free();await process_frame
    print("3D viewer checks: %d, failed: %s" % [checks,failed]);quit(1 if failed else 0)
