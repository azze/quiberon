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
    check(v.playback.ai_enabled and not v.playback.playing,"AI battle opens paused for commander/army setup")
    check(v.playback.backend.GetArmyStrategy(0)=="manual" and v.playback.backend.GetArmyStrategy(1)=="balanced","Default is player versus AI")
    v.units.selected=0;v.refresh_frame();v.refresh_ui()
    var before: String=v.playback.current.units[0].info.commander
    check(not before.begins_with("Commander "),"Regiments have generated named officers")
    check(v.hud.inspector.text.contains("Personality:") and v.hud.inspector.text.contains("Autonomy:"),"Inspector exposes personality and authority")
    v.hud.ai_dialog.popup_centered(Vector2i(580,460));v.refresh_ui()
    check(not v.hud.reroll_button.disabled and v.hud.personality_option.item_count==5,"Officer setup is available before first tick")
    v.action("commander:reroll");check(v.playback.current.units[0].info.commander!=before,"Reroll changes identity without running combat")
    check(v.playback.backend.GetMetrics().random_draws==0,"Officer generation does not consume combat RNG")
    check(v.playback.current.units[0].tactical_assignment=="" and v.playback.current.units[0].friendly_support==0,"Tactical inspection defaults are valid before first decision")
    check(v.playback.edit_commander(0,"cautious","drillmaster"),"Compatible cross-faction traits can be assigned")
    check(not v.playback.edit_commander(0,"cautious","artillerist"),"Incompatible assignment is rejected")
    var retained: String=v.playback.current.units[0].info.commander
    v.hud.ai_dialog.hide();v.action("restart");check(v.playback.current.units[0].info.commander==retained,"Reset preserves commander assignment")
    v.units.selected=0;v.action("army:0:balanced");v.action("live:step");check(v.playback.backend.GetMetrics().ai_decisions>0,"Both armies make authoritative decisions")
    check(v.playback.current.units[0].personality=="cautious","Assigned personality survives battle initialization")
    check(v.playback.current.units[0].army_plan!="" and v.playback.current.units[0].army_role!="","Inspector receives authoritative army plan and regiment role")
    check(not v.playback.edit_commander(0),"Commander edits are locked after first tick")
    v.action("live:hold");v.playback.single_step();v.playback.warm_start(75);v.refresh_frame();v.refresh_ui()
    check(v.playback.current.units[0].order_owner=="player" and v.playback.current.units[0].order=="hold","AI cannot overwrite player Hold")
    v.action("live:auto");v.playback.single_step();check(v.playback.current.units[0].autonomy=="autonomous","Individual regiment can return to autonomy")
    v.action("scenario:ai-combined");v.playback.warm_start(300);v.refresh_frame();v.refresh_ui()
    check(v.playback.backend.GetArmyStrategy(0)=="balanced" and v.playback.backend.GetArmyStrategy(1)=="balanced","AI versus AI is available")
    var m: Dictionary=v.playback.backend.GetMetrics();check(m.ai_decisions>0 and m.ai_target_evaluations>0,"Decision telemetry is authoritative")
    check(m.artillery_shots>0,"Autonomous batteries fire physical cannonballs")
    v.units.selected=3;v.refresh_ui();check(v.hud.inspector.text.contains("Last decision:"),"Selected cavalry intention is inspectable")
    check(v.rig!=null and v.effects!=null,"Existing camera and renderer are reused")
    if DisplayServer.get_name()!="headless" and "--test-capture" in OS.get_cmdline_user_args():
        await process_frame;await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("/tmp/rtt-m5-autonomous.png")
    v.action("mode:replay");check(not v.is_live and not v.playback.current.units.is_empty(),"Python replay remains available")
    print("Godot AI/commander checks: ",checks,", failed: ",failed);v.queue_free();await process_frame;quit(1 if failed else 0)
