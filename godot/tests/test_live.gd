extends SceneTree
const Viewer=preload("res://scripts/three_d/viewer_3d.gd")
const World=preload("res://scripts/three_d/world_3d.gd")
var checks:=0
var failed:=false
func check(value: bool,message: String) -> void:
    checks+=1
    if not value:failed=true;push_error(message)
func _initialize() -> void:run.call_deferred()
func mouse(viewer: Control,button: int,pixel: Vector2) -> void:
    var event:=InputEventMouseButton.new();event.button_index=button;event.pressed=true;event.position=pixel+viewer.viewport.get_parent().global_position
    Input.parse_input_event(event)
    var release:=event.duplicate();release.pressed=false;Input.parse_input_event(release)
func run() -> void:
    if not ClassDB.class_exists("CSharpScript"):
        push_error("Live tests require Godot .NET, not the standard editor");quit(1);return
    root.size=Vector2i(1280,800)
    var viewer:=Viewer.new();root.add_child(viewer)
    await process_frame;await process_frame
    viewer.set_process(false)
    check(not viewer.is_live and viewer.playback.current.units.size()==12,"Replay remains the default")
    viewer.live_scenario="movement" # Retain the original Milestone 1 regression workload.
    viewer.hud.mode_selector.select(1);viewer.hud.mode_selector.item_selected.emit(1)
    check(viewer.is_live and viewer.playback!=null,"Mode selector creates the C# live source")
    if not viewer.is_live:quit(1);return
    check(viewer.playback.current.units.size()==8,"Default live scenario has eight regiments")
    var counts: Dictionary={}
    for u in viewer.playback.current.units.values():
        var category_key: String=str(u.info.army)+":"+u.info.category
        counts[category_key]=counts.get(category_key,0)+1
        check(u.order=="hold","Live units start without march/attack orders")
    check(counts.get("0:infantry")==4 and counts.get("0:cavalry")==1 and counts.get("0:artillery")==1 and counts.get("1:infantry")==2,"Required default composition")
    check(viewer.surface.model.hills.is_empty() and viewer.surface.model.forests.is_empty(),"Default movement is authoritative open field")
    check(not viewer.hud.timeline.visible and viewer.hud.live_orders.visible,"Live controls reuse the HUD and hide seeking")
    viewer.playback.playing=false
    var original: Vector2=viewer.playback.current.units[0].position
    viewer.rig.span=800;viewer.rig.target_span=800;viewer.rig.update_pose();viewer.refresh_frame()
    var selected: Vector3=viewer.units.poses[0].world
    mouse(viewer,MOUSE_BUTTON_LEFT,viewer.rig.camera.unproject_position(selected));await process_frame
    check(viewer.units.selected==0,"Actual live viewport click selects a friendly regiment")
    var dest:=original+Vector2(140,15)
    mouse(viewer,MOUSE_BUTTON_RIGHT,viewer.rig.camera.unproject_position(World.ground(dest,0)));await process_frame
    viewer._process(.5)
    check(viewer.playback.tick==0 and viewer.playback.following.units[0].position==original,"Queued movement cannot advance paused authority")
    viewer.action("live:step")
    check(viewer.playback.tick==1 and viewer.playback.current.units[0].position.x>original.x,"Single step applies a real C# move command")
    check(viewer.playback.current.units[0].destination.distance_to(dest)<.01,"Terrain picking converts to simulation world coordinates")
    viewer.action("live:column");viewer.action("live:step")
    check(viewer.playback.current.units[0].formation=="line" and viewer.playback.current.units[0].transition_left>6,"Formation button queues a timed transition")
    check(viewer.hud.inspector.text.contains("Changing to column"),"Inspector displays live formation state")
    var waiting: Vector2=viewer.playback.current.units[0].position
    for _i in range(75):viewer.action("live:step")
    check(viewer.playback.current.units[0].formation=="column" and viewer.playback.current.units[0].width==22,"Completed column uses original footprint")
    check(viewer.playback.current.units[0].position.x>waiting.x,"Movement resumes after reforming")
    var unit_root: Node3D=viewer.units.visuals[0].root
    viewer.playback.playing=true;viewer.playback.speed=1
    viewer._process(.1);viewer._process(.025)
    var a: Vector2=viewer.playback.current.units[0].position
    var b: Vector2=viewer.playback.following.units[0].position
    var displayed: Vector2=World.horizontal(viewer.units.poses[0].world)
    check(displayed.distance_to(a.lerp(b,viewer.playback.alpha))<.001,"Live visual motion interpolates adjacent C# snapshots")
    check(viewer.units.visuals[0].root==unit_root,"Ticks reuse regiment visual objects")
    var tick: int=viewer.playback.tick;viewer.playback.speed=10;viewer._process(.16)
    check(viewer.playback.tick==tick+16,"10x speed executes fixed ticks")
    viewer.playback.playing=false
    var authoritative: Vector2=viewer.playback.following.units[0].position
    var focus: Vector2=viewer.rig.focus
    Input.action_press("camera_forward");viewer._process(.2);Input.action_release("camera_forward")
    check(viewer.rig.focus.distance_to(focus)>0,"Paused live simulation leaves camera navigation active")
    check(viewer.playback.following.units[0].position==authoritative,"Camera cannot move authoritative regiments")
    viewer.action("focus");viewer.action("follow");viewer._process(.1)
    check(viewer.rig.follow_id==0,"Follow still works in live mode")
    viewer.action("overhead");viewer.rig.request_zoom(1,Vector2(400,250));viewer._process(.1)
    check(viewer.rig.perspective,"Physical dolly zoom remains available live")
    check(not viewer.playback.issue_move(6,Vector2(500,200)),"Enemy regiments reject player commands")
    viewer.rig.fit(true);viewer.refresh_frame();viewer.rig.follow_id=0
    viewer.select_at(viewer.rig.camera.unproject_position(viewer.units.poses[6].world))
    check(viewer.units.selected==-1 and viewer.rig.follow_id==-1,"Enemy click cannot leave follow attached to an unselected regiment")
    var before_ui: int=viewer.playback.tick
    viewer.hud.settings_dialog.popup_centered();await process_frame
    var key:=InputEventKey.new();key.keycode=KEY_PERIOD;key.pressed=true;Input.parse_input_event(key);await process_frame
    check(viewer.playback.tick==before_ui,"Text/settings UI blocks simulation shortcuts")
    viewer.hud.settings_dialog.hide()
    viewer.playback.playing=true;viewer.playback.speed=1
    var before_stall: int=viewer.playback.tick
    viewer.last_process=Time.get_ticks_usec()-1000000
    viewer.set_process(true);viewer._process(.001);viewer.set_process(false)
    check(viewer.playback.tick==before_stall+10,"Live authority uses monotonic elapsed time even when Godot delta is capped")
    viewer.action("restart")
    check(viewer.playback.tick==0 and viewer.playback.following.units[0].position==original,"Reset creates fresh authoritative state")
    viewer.live_count=12;viewer.live_terrain=true;check(viewer.start_live(),"Terrain live scenario loads")
    check(viewer.surface.maximum>20 and viewer.forests.count>0,"Live terrain matches C# analytic hills and forests")
    viewer.units.selected=4;viewer.playback.playing=false;viewer.action("live:column");viewer.action("live:step")
    check(viewer.playback.following.units[4].next_formation=="column","Skirmisher archetype supports formation commands")
    viewer.action("mode:replay");viewer.seek(60)
    check(not viewer.is_live and viewer.playback.time==60 and viewer.playback.current.units.size()==12,"Return to replay restores seeking and Python recordings")
    check(viewer.hud.timeline.visible and not viewer.hud.live_orders.visible,"Replay controls restored")
    viewer.queue_free();await process_frame
    print("Godot live checks: %d, failed: %s" % [checks,failed]);quit(1 if failed else 0)
