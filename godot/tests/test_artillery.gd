extends SceneTree
const Viewer=preload("res://scripts/three_d/viewer_3d.gd")
var checks:=0
var failed:=false
func check(value: bool,message: String) -> void:
    checks+=1
    if not value:failed=true;push_error(message)
func _initialize() -> void:run.call_deferred()
func run() -> void:
    root.size=Vector2i(1280,800);var v:=Viewer.new();root.add_child(v)
    await process_frame;await process_frame;v.set_process(false);v.action("mode:live")
    v.action("scenario:open-shot");v.playback.playing=false;v.units.selected=0;v.playback.warm_start(2);v.refresh_frame();v.refresh_ui()
    check(v.playback.following.shots.size()==6,"Six authoritative cannonballs reach typed frame")
    check(v.effects.ball_count==6,"Existing renderer displays live cannonballs")
    check(v.hud.inspector.text.contains("Guns: 6 / 6") and v.hud.inspector.text.contains("reloading"),"Battery inspector shows actual gun and reload state")
    var initial: Dictionary=v.playback.following.shots.duplicate();v.playback.warm_start(4);v.refresh_frame()
    for id in initial:
        check(v.playback.following.shots.has(id),"Projectile IDs persist")
        check(v.playback.following.shots[id].position!=initial[id].position,"Projectile movement is authoritative")
    check(v.playback.backend.GetMetrics().artillery_shots==6,"A reload cycle does not repeat per tick")
    v.action("live:cease");v.playback.single_step();check(v.playback.current.units[0].hold_fire,"Hold-fire command works")
    v.action("live:fire");v.playback.single_step();check(not v.playback.current.units[0].hold_fire,"Resume-fire command works")
    v.playback.warm_start(350);v.refresh_frame();v.refresh_ui()
    check(v.playback.backend.GetMetrics().projectile_bounces>0,"Terrain ricochets reach live simulation")
    check(v.playback.backend.GetMetrics().projectile_hits>0,"Physical shots cause formation hits")
    v.effects.debug_enabled=true;v.effects.selected_id=0;v.refresh_frame();check(v.effects.debug_mesh.get_surface_count()>0,"Debug visuals are optional and usable")
    for id in ["prussian-drill","woodland-specialists","grenadier-support","uhlan-charge","rifle-engagement","horse-redeployment","combined-arms"]:
        v.action("scenario:"+id);v.playback.playing=false;v.units.selected=0;v.playback.warm_start(1);v.refresh_frame();v.refresh_ui()
        check(v.units.visuals.size()==v.playback.infos.size(),"Specialist visuals reuse existing renderer: "+id)
        check(not v.playback.current.units[0].ability.is_empty(),"Specialist effect description reaches inspector: "+id)
    v.action("scenario:friendly-fire");v.playback.playing=false;v.playback.warm_start(600);v.refresh_frame()
    check(v.playback.backend.GetMetrics().friendly_fire>0,"Friendly fire is active in live mode")
    v.action("scenario:combined-arms");v.playback.playing=false;v.playback.warm_start(195);v.effects.debug_enabled=false;v.units.selected=5;v.refresh_frame();v.refresh_ui()
    v.rig.fit();check(v.rig!=null,"Existing tactical camera is preserved")
    if DisplayServer.get_name()!="headless" and "--test-capture" in OS.get_cmdline_user_args():
        await process_frame;await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("/tmp/rtt-m4-combined.png")
    v.action("restart");check(v.playback.current.shots.is_empty(),"Reset clears live projectile state")
    root.size=Vector2i(800,600);await process_frame;check(v.hud.inspector.visible,"Inspection remains available at small window size")
    check(v.hud.order_buttons.skirmish_order.get_global_rect().end.x<=801,"Order strip fits 800 pixel window")
    print("Godot artillery/specialist checks: ",checks,", failed: ",failed);v.queue_free();await process_frame;quit(1 if failed else 0)
