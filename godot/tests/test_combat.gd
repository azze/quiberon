extends SceneTree
## Exercises the real C# bridge and shared 3D renderer, not a mock replay.
const Viewer=preload("res://scripts/three_d/viewer_3d.gd")
const World=preload("res://scripts/three_d/world_3d.gd")
var checks:=0
var failed:=false
func check(value: bool,message: String) -> void:
    checks+=1
    if not value:failed=true;push_error(message)
func _initialize() -> void:run.call_deferred()
func run() -> void:
    root.size=Vector2i(1280,800)
    var v:=Viewer.new();root.add_child(v)
    await process_frame;await process_frame;v.set_process(false)
    v.live_scenario="infantry-duel";v.live_dynamics=false # Preserve the M2 frozen-morale integration contract.
    v.action("mode:live")
    check(v.is_live and v.playback.combat_enabled,"Live defaults to combat")
    check(v.playback.current.units.size()==4,"Infantry duel loads two regiments per side")
    v.playback.playing=false;v.units.selected=0;v.action("live:step")
    var a: Object=v.playback.current.units[0]
    check(a.strength<240 and a.reload_left>11,"C# volleys inflict casualties and begin reloading")
    check(a.weapon_range==155 and a.target==2 and not a.morale_simulated,"Weapon/target state is authoritative; morale is inactive")
    check(v.hud.inspector.text.contains("Morale: not simulated") and v.hud.inspector.text.contains("Reload:"),"Existing inspector shows combat fields")
    check(v.effects.smoke_count>0,"Authoritative volley events create smoke")
    var seq: int=-1
    for e in v.playback.events:
        check(e.sequence>seq and e.tick==0 and e.time==0,"Stable event IDs and simulation timestamps");seq=e.sequence
    var root_before: Node3D=v.units.visuals[0].root
    for _i in range(250):v.playback.single_step()
    v.refresh_frame();v.refresh_ui()
    check(v.units.visuals[0].root==root_before,"Casualties reuse the existing regiment node")
    check(v.units.visuals[0].visible_count<32,"Casualties reduce decorative soldiers without repacking")
    if DisplayServer.get_name()!="headless" and "--test-capture" in OS.get_cmdline_user_args():
        v.rig.span=400;v.rig.target_span=400;v.rig.focus=Vector2(500,310);v.rig.target_focus=v.rig.focus;v.rig.update_pose();v.refresh_frame()
        await process_frame;await RenderingServer.frame_post_draw
        root.get_texture().get_image().save_png("/tmp/rtt-m2-combat.png")
    v.rig.span=550;v.rig.target_span=550;v.rig.update_pose();v.refresh_frame()
    # Same handler used by right-click picking, including a rotated 3D camera.
    var enemy_pixel: Vector2=v.rig.camera.unproject_position(v.units.poses[3].world)
    v.move_selected(enemy_pixel);v.playback.single_step()
    check(v.playback.current.units[0].order=="attack" and v.playback.current.units[0].target==3,"Right-click enemy binds an attack order")
    check(not v.playback.issue_attack(2,0),"Player cannot command enemies")
    var original: Vector2=v.playback.current.units[0].position
    var before: Vector2=v.rig.focus
    Input.action_press("camera_forward");v._process(.2);Input.action_release("camera_forward")
    check(v.rig.focus!=before and v.playback.current.units[0].position==original,"Camera remains independent while combat is paused")
    v.action("scenario:ridge-defence")
    check(v.surface.maximum>10 and v.playback.combat_enabled,"Ridge uses the actual analytic terrain")
    var enemy_before: Vector2=v.playback.following.units[2].position
    v.playback.single_step();check(v.playback.following.units[2].position.x>enemy_before.x,"Scenario commands run on exact ticks through the bridge")
    v.action("scenario:forest-engagement")
    check(v.forests.count>0 and v.surface.model.forests.size()==2,"Forest scenario shares authoritative and rendered regions")
    v.playback.single_step();check(v.playback.following.units[0].forest_cover>0,"Live inspector receives actual forest coverage")
    v.action("scenario:flank-attack");v.playback.single_step();v.refresh_frame()
    check(v.playback.current.units[0].combat_state=="melee","Oriented enemy contact enters melee")
    check(v.playback.backend.GetMetrics().melee_pulses==1,"Contact resolves one controlled melee pulse")
    check(v.effects.halo_mesh.get_surface_count()>0,"Melee event has visual feedback")
    v.action("scenario:friendly-obstruction");v.playback.single_step()
    check(v.playback.current.units[0].reload_left==0 and v.playback.current.units[1].reload_left>0,"Rear line is blocked while the front line can fire")
    v.action("scenario:combined");v.playback.single_step()
    check(v.playback.current.units.size()==12,"Combined scenario includes twelve regiments")
    check(not v.playback.current.units[4].combat_capable and not v.playback.current.units[5].combat_capable,"Cavalry and artillery outgoing combat are explicitly disabled")
    v.units.selected=5;v.refresh_ui()
    check(v.hud.inspector.text.contains("Outgoing combat: disabled"),"Unsupported units are labelled honestly")
    v.action("restart")
    check(v.playback.tick==0 and v.playback.events.is_empty(),"Reset clears transient combat events")
    v.action("scenario:infantry-duel");v.playback.speed=10
    for _i in range(600):
        v.playback.advance(.16)
        if v.playback.result!="":break
    v.rig.follow_id=2;v._process(0);v.refresh_ui()
    check(v.playback.result=="army_0" and not v.playback.playing,"A complete native live duel reaches the temporary result and pauses")
    check(not v.playback.current.units[2].active and not v.units.visuals[2].root.visible,"Final casualties and destruction are displayed without a stale interpolation frame")
    check(v.rig.follow_id==-1 and v.hud.notices.text.contains("Battle complete"),"Destroyed follow target ends safely and existing HUD reports completion")
    check(not v.playback.issue_move(0,Vector2(300,300)),"Completed battle rejects further orders")
    v.action("restart")
    check(v.playback.playing and v.playback.tick==0 and v.playback.current.units[2].active,"Restart after completion restores the army and resumes")
    v.action("mode:replay");v.seek(60)
    check(not v.is_live and v.playback.time==60 and v.hud.timeline.visible,"Replay still supports timeline seeking")
    v.seek(0)
    var expected_smoke: int=0
    for e in v.playback.events:
        if e.time<=0 and e.time+e.duration>=0 and e.kind in ["volley","artillery_fire","impact","charge_impact"]:expected_smoke+=7 if e.kind in ["volley","artillery_fire"] else 1
    check(v.effects.smoke_count==expected_smoke,"Backward seek displays only effects belonging to the new time (including initial volleys)")
    root.size=Vector2i(800,600);await process_frame;await process_frame
    v.action("mode:live")
    check(v.hud.live_orders.get_global_rect().end.x<=800,"Live order buttons fit at 800×600")
    if DisplayServer.get_name()!="headless" and "--test-capture" in OS.get_cmdline_user_args():
        await process_frame;await RenderingServer.frame_post_draw
        root.get_texture().get_image().save_png("/tmp/rtt-m2-combat-small.png")
    v.queue_free();await process_frame
    print("Godot combat checks: %d, failed: %s" % [checks,failed]);quit(1 if failed else 0)
