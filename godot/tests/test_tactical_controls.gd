extends SceneTree
const Viewer=preload("res://scripts/three_d/viewer_3d.gd")
const World=preload("res://scripts/three_d/world_3d.gd")
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
func screen(v: Object,point: Vector2) -> Vector2:return v.rig.camera.unproject_position(World.ground(point,v.surface.height_at(point)))
func capture(path: String) -> void:
    if DisplayServer.get_name()=="headless" or "--test-capture" not in OS.get_cmdline_user_args():return
    await process_frame;await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png(path)
func run() -> void:
    root.size=Vector2i(1280,800);var v:=Viewer.new();root.add_child(v)
    await process_frame;await process_frame;v.set_process(false);v.action("setup")
    var setup=v.hud.setup_dialog
    check(not setup.counts[0].haudenosaunee_skirmishers.get_parent().visible,"Unused archetypes are absent from the main roster")
    check(setup.counts[0].infantry.get_parent().visible,"Chosen archetypes remain editable")
    setup.add_buttons[0].pressed.emit();var picker=setup.unit_picker
    check(picker.visible and v.hud.blocked(),"Add units opens a separate selection screen and blocks battlefield input")
    picker.set_filter("cavalry");check(picker.filtered.size()==5 and picker.filtered.all(func(a):return a.category=="cavalry"),"Cavalry filter")
    picker.set_filter("artillery");check(picker.filtered.size()==3 and picker.filtered.all(func(a):return a.category=="artillery"),"Artillery filter")
    picker.set_filter("infantry");check(picker.filtered.size()==12,"Infantry filter includes light infantry and rifles")
    picker.search.text="Haudenosaunee";picker.search.text_changed.emit(picker.search.text);check(picker.filtered.size()==1,"Search filters the selected category")
    check(picker.details.text.contains("Forest cover boosts aim"),"Picker describes actual archetype abilities")
    picker.amount.value=2;picker.confirm_add()
    check(setup.counts[0].haudenosaunee_skirmishers.value==2 and setup.counts[1].haudenosaunee_skirmishers.value==2,"Adding respects symmetric armies")
    check(setup.counts[0].haudenosaunee_skirmishers.get_parent().visible,"New selection appears in roster")
    setup.counts[0].haudenosaunee_skirmishers.value=0;check(not setup.counts[0].haudenosaunee_skirmishers.get_parent().visible,"Removing the last regiment hides that row")
    setup.unit_picker.open_picker(setup,0,setup.catalogue);picker.amount.value=64;check(picker.add_selected.disabled,"Picker enforces regiment limits")
    picker.hide();setup.hide();v.action("custom:"+v.playback.backend.GetDefaultConfiguration() if v.is_live else "custom:"+setup.backend.GetDefaultConfiguration())
    v.units.selected=0;v.refresh_frame();v.rig.span=800;v.rig.target_span=800;v.rig.update_pose()
    var start: Vector2=v.playback.current.units[0].position
    var destination:=start-Vector2(30,0);var begin:=screen(v,destination);var end:=screen(v,destination+Vector2(0,22))
    mouse(v,MOUSE_BUTTON_RIGHT,true,begin);await process_frame
    check(v.order_preview.active and v.playback.tick==0,"Holding right mouse starts a read-only deployment ghost")
    motion(v,end,begin);await process_frame;v.refresh_frame()
    check(absf(angle_difference(v.order_preview.facing,PI/2))<.01,"Ghost faces the terrain point under the dragged cursor")
    check(v.order_preview.destination.distance_to(destination)<.01,"Dragging preserves the initial destination")
    v.gesture_cursor=begin+Vector2(1,1);v.refresh_frame()
    check(absf(angle_difference(v.order_preview.facing,PI/2))<.01,"Returning inside the click deadzone retains the chosen heading")
    check(v.playback.current.units[0].position==start,"Deployment does not commit on press or motion")
    await capture("/tmp/rtt-drag-facing.png")
    mouse(v,MOUSE_BUTTON_RIGHT,false,end);await process_frame
    check(v.playback.current.units[0].position.distance_to(destination)<.01 and absf(angle_difference(v.playback.current.units[0].facing,PI/2))<.01,"Release commits deployment position and facing")
    check(not v.order_preview.active,"Release clears the ghost")
    begin=screen(v,Vector2(500,300));mouse(v,MOUSE_BUTTON_RIGHT,true,begin);await process_frame;v.refresh_frame()
    check(not v.order_preview.valid,"Out-of-zone placement has an invalid ghost")
    mouse(v,MOUSE_BUTTON_RIGHT,false,begin);await process_frame
    check(v.playback.current.units[0].position.distance_to(destination)<.01,"Invalid deployment does not change authority")
    v.action("deploy:start");v.playback.playing=false
    destination=Vector2(460,300);begin=screen(v,destination);end=screen(v,destination+Vector2(0,35))
    mouse(v,MOUSE_BUTTON_RIGHT,true,begin);await process_frame;motion(v,end,begin);await process_frame;v.refresh_frame()
    check(v.order_preview.valid and v.playback.tick==0,"Move ghost works while simulation is paused")
    v.playback.single_step();check(v.playback.current.units[0].order=="hold","No movement command is issued until release")
    mouse(v,MOUSE_BUTTON_RIGHT,false,end);await process_frame;v.playback.single_step();v.refresh_frame()
    check(v.playback.current.units[0].destination.distance_to(destination)<.01 and absf(angle_difference(v.playback.current.units[0].arrival_facing,PI/2))<.01,"Movement order contains explicit arrival facing")
    check(v.range_indicator.visible and v.range_indicator.radius==155,"Selected musket regiment has a range indicator")
    var builds: int=v.range_indicator.builds;v.refresh_frame();check(v.range_indicator.builds==builds,"Unchanged range geometry is cached")
    v.units.selected=4;v.refresh_frame();check(not v.range_indicator.visible,"Melee-only cavalry has no misleading musket range")
    v.units.selected=0;v.refresh_frame()
    var old_goal: Vector2=v.playback.current.units[0].destination
    begin=screen(v,Vector2(470,320));mouse(v,MOUSE_BUTTON_RIGHT,true,begin);await process_frame
    mouse(v,MOUSE_BUTTON_RIGHT,false,Vector2(-100,-100));await process_frame
    check(not v.order_preview.active and v.gesture.is_empty(),"Releasing over UI or outside battlefield cancels the preview")
    v.playback.single_step();check(v.playback.current.units[0].destination==old_goal,"Cancelled gesture does not queue an order")
    begin=screen(v,Vector2(490,310));mouse(v,MOUSE_BUTTON_RIGHT,true,begin);mouse(v,MOUSE_BUTTON_RIGHT,false,begin);await process_frame;v.playback.single_step()
    check(v.playback.current.units[0].arrival_facing==null,"A plain right click keeps automatic movement facing")
    v.rig.yaw=.9;v.rig.target_yaw=.9;v.rig.update_pose();destination=Vector2(480,330);begin=screen(v,destination);end=screen(v,destination+Vector2(-25,0))
    mouse(v,MOUSE_BUTTON_RIGHT,true,begin);await process_frame;motion(v,end,begin);await process_frame;v.refresh_frame()
    check(absf(angle_difference(v.order_preview.facing,PI))<.01,"Dragged heading stays in world coordinates under camera rotation")
    v.rig.cancel_secondary();check(not v.order_preview.active,"Explicit cancellation clears drag and ghost")
    begin=screen(v,Vector2(470,320));mouse(v,MOUSE_BUTTON_RIGHT,true,begin);await process_frame
    root.size=Vector2i(1000,700);await process_frame;await process_frame
    check(not v.order_preview.active and not v.rig.secondary_down,"Window resizing cancels stale screen-space gestures")
    root.size=Vector2i(1280,800);await process_frame
    v.rig.target_pitch=0
    for i in 300:v.rig.advance(1./120)
    check(absf(v.rig.pitch)<.0001 and absf(v.rig.camera.global_basis.z.y)<.0001,"Camera can look parallel to flat ground")
    check(v.rig.camera.position.y>=v.surface.height_at(World.horizontal(v.rig.camera.position))+v.rig.settings.terrain_clearance-.001,"Ground-level view retains terrain clearance")
    v.rig.request_zoom(1,Vector2(200,20));v.rig.advance(.1)
    check(v.rig.camera.position.is_finite(),"Horizon zoom fallback remains finite")
    v.action("scenario:ridge-defence");v.playback.playing=false;v.units.selected=0;v.refresh_frame()
    var hill: Vector2=v.surface.model.hills[0].center;begin=screen(v,hill);end=screen(v,hill+Vector2(-25,15))
    mouse(v,MOUSE_BUTTON_RIGHT,true,begin);await process_frame;motion(v,end,begin);await process_frame;v.refresh_frame()
    check(v.order_preview.active and v.order_preview.destination.distance_to(hill)<.1,"Movement preview anchors to the actual hill surface")
    check(absf(angle_difference(v.order_preview.facing,Vector2(-25,15).angle()))<.01,"Facing drag accounts for terrain elevation")
    var vertices: PackedVector3Array=v.order_preview.outline.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
    check(Array(vertices).all(func(p):return absf(p.y-v.surface.height_at(Vector2(p.x,p.z))-.4)<.001),"Ghost outline follows terrain height")
    v.rig.cancel_secondary();v.rig.pitch=0;v.rig.target_pitch=0;v.rig.update_pose()
    check(absf(v.rig.camera.global_basis.z.y)<.0001 and v.rig.camera.position.y>=v.surface.height_at(World.horizontal(v.rig.camera.position))+v.rig.settings.terrain_clearance-.001,"Level view remains safe over hills")
    v.action("mode:replay");v.units.selected=0;v.refresh_frame()
    check(v.range_indicator.visible and v.range_indicator.radius>0,"Recorded archetype metadata supplies range in replay")
    root.size=Vector2i(800,600);await process_frame;v.action("setup");setup=v.hud.setup_dialog
    setup.unit_picker.open_picker(setup,0,setup.catalogue);await process_frame
    check(setup.unit_picker.size.x<=root.size.x and setup.unit_picker.size.y<=root.size.y,"Unit picker fits smaller windows")
    await capture("/tmp/rtt-unit-picker.png")
    print("Godot tactical control checks: ",checks,", failed: ",failed);v.queue_free();await process_frame;quit(1 if failed else 0)
