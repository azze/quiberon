extends SceneTree
const Viewer=preload("res://scripts/three_d/viewer_3d.gd")
var checks:=0
var failed:=false
func check(value: bool,message: String) -> void:
    checks+=1
    if not value:failed=true;push_error(message)
func _initialize() -> void:run.call_deferred()
func mouse(v: Object,button: int,pressed: bool,pixel: Vector2) -> void:
    var e:=InputEventMouseButton.new();e.button_index=button;e.pressed=pressed;e.position=pixel+v.viewport.get_parent().global_position;Input.parse_input_event(e)
func motion(v: Object,pixel: Vector2,previous: Vector2) -> void:
    var e:=InputEventMouseMotion.new();e.position=pixel+v.viewport.get_parent().global_position;e.relative=pixel-previous;e.button_mask=MOUSE_BUTTON_MASK_RIGHT;Input.parse_input_event(e)
func capture(path: String) -> void:
    if DisplayServer.get_name()=="headless" or "--test-capture" not in OS.get_cmdline_user_args():return
    await process_frame;await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png(path)
func run() -> void:
    root.size=Vector2i(1280,800);var v:=Viewer.new();root.add_child(v)
    await process_frame;await process_frame;v.set_process(false)
    v.live_scenario="movement";v.live_terrain=true;v.live_seed=991;v.start_live();v.playback.playing=false;v.units.selected=0;v.refresh_frame()
    var playback: Object=v.playback;var backend: Object=playback.backend
    var goal:=Vector2(400,130);playback.issue_move(0,goal,PI/2)
    v.hud.view_button.pressed.emit()
    check(v.view_2d and v.viewport.disable_3d and v.flat_view.visible,"2D button selects the alternate battlefield renderer")
    check(v.playback==playback and v.playback.backend==backend,"Live simulation and clock are the same objects")
    check(v.playback.tick==0 and not v.playback.playing and v.units.selected==0,"Switch preserves tick, pause and selection")
    check(v.flat_view.terrain==playback.source.terrain and v.flat_view.units_view.current==playback.current,"2D displays the current terrain and exact live frames")
    check(playback.source.seed_text=="991" and v.hud.view_button.text=="3D view","Custom seed is retained and return control is visible")
    v.action("live:step")
    check(playback.current.units[0].destination==goal and is_equal_approx(playback.current.units[0].arrival_facing,PI/2),"Queued 3D commands survive switching views")
    var pixel: Vector2=v.flat_view.world_to_screen(playback.current.units[1].position)
    mouse(v,MOUSE_BUTTON_LEFT,true,pixel);mouse(v,MOUSE_BUTTON_LEFT,false,pixel);await process_frame
    check(v.units.selected==1 and v.flat_view.units_view.selected==1,"Actual 2D input selects and inspects current regiments")
    var destination:=Vector2(450,240);var begin: Vector2=v.flat_view.world_to_screen(destination);var end: Vector2=v.flat_view.world_to_screen(destination+Vector2(-25,0))
    mouse(v,MOUSE_BUTTON_RIGHT,true,begin);await process_frame;motion(v,end,begin);await process_frame;v.refresh_frame()
    check(v.order_preview.active and v.order_preview.destination.distance_to(destination)<.01,"2D movement previews use the shared order gesture")
    mouse(v,MOUSE_BUTTON_RIGHT,false,end);await process_frame;v.action("live:step")
    check(playback.current.units[1].destination.distance_to(destination)<.01 and absf(angle_difference(playback.current.units[1].arrival_facing,PI))<.01,"2D release queues an authoritative oriented movement order")
    v.action("speed:4");v.action("pause");var tick: int=playback.tick;v._process(.2)
    check(playback.tick==tick+8,"The live clock advances exactly once in 2D at the selected speed")
    v.action("pause");var paused_tick: int=playback.tick
    var position: Vector2=playback.following.units[1].position;v.flat_view.advance(.2,Vector2(1,0),true)
    check(playback.tick==paused_tick and playback.following.units[1].position==position,"2D camera cannot move or advance authoritative state")
    await capture("/tmp/rtt-current-battle-2d.png")
    var builds: int=v.flat_view.terrain_view.builds
    v.hud.view_button.pressed.emit()
    check(not v.view_2d and not v.viewport.disable_3d and v.playback==playback,"Return to 3D preserves the same live battle")
    check(playback.tick==paused_tick and playback.speed==4 and v.units.selected==1,"Round trip preserves speed, progress and selection")
    v.action("2d");v.action("2d");check(v.flat_view.terrain_view.builds==builds,"Repeated switches reuse the cached 2D terrain")
    v.action("mode:replay");v.seek(180);v.playback.playing=false;v.playback.speed=2;v.units.selected=4;v.refresh_frame()
    var replay: Object=v.playback;var time: float=replay.time;var frame: Object=replay.current
    v.action("2d")
    check(v.playback==replay and replay.time==time and v.flat_view.units_view.current==frame,"Replay switches at the current timeline position, not the demo start")
    check(replay.speed==2 and not replay.playing and v.units.selected==4,"Replay selection, speed and pause survive")
    v.seek(60);check(v.flat_view.units_view.current==replay.current and replay.time==60,"Seeking works in the 2D view")
    v.action("2d");check(v.playback==replay and replay.time==60,"Return to 3D keeps the new replay time")
    v.action("setup");v.action("custom:"+v.hud.setup_dialog.recipe());v.units.selected=0;v.action("2d")
    check(v.playback.backend.IsDeployment() and v.flat_view.deployment,"Current custom deployment also supports 2D")
    var start: Vector2=v.playback.current.units[0].position;var place:=start-Vector2(30,0)
    begin=v.flat_view.world_to_screen(place);end=v.flat_view.world_to_screen(place+Vector2(0,25))
    mouse(v,MOUSE_BUTTON_RIGHT,true,begin);await process_frame;motion(v,end,begin);await process_frame;v.refresh_frame()
    mouse(v,MOUSE_BUTTON_RIGHT,false,end);await process_frame
    check(v.playback.current.units[0].position.distance_to(place)<.01 and absf(angle_difference(v.playback.current.units[0].facing,PI/2))<.01,"2D deployment supports position and facing without advancing")
    check(v.playback.tick==0,"Deployment remains at tick zero across views")
    v.action("2d");check(not v.view_2d,"Custom deployment returns to 3D")
    print("Godot shared-view checks: ",checks,", failed: ",failed);v.queue_free();await process_frame;quit(1 if failed else 0)
