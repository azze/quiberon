extends SceneTree
const Viewer=preload("res://scripts/three_d/viewer_3d.gd")
var checks:=0
var failed:=false
func check(value: bool,message: String) -> void:
    checks+=1
    if not value:failed=true;push_error(message)
func _initialize() -> void:run.call_deferred()
func capture(path: String) -> void:
    if DisplayServer.get_name()=="headless" or "--test-capture" not in OS.get_cmdline_user_args():return
    await process_frame;await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png(path)
func run() -> void:
    root.size=Vector2i(1280,800);var v:=Viewer.new();root.add_child(v)
    await process_frame;await process_frame;v.set_process(false);v.action("setup")
    check(v.hud.setup_dialog.visible and v.hud.blocked(),"Setup blocks navigation and selection")
    var setup=v.hud.setup_dialog
    check(setup.preset_choice.item_count>=12,"Python custom presets are bundled")
    check(setup.counts[0].has("prussian_line") and setup.counts[0].has("french_horse_artillery"),"All archetypes editable")
    var json: String=setup.recipe()
    check(setup.strategies[1].selected==1,"Loading a recipe retains the Red AI setting")
    check(json!="","Godot-produced numeric JSON validates: "+setup.message.text)
    v.action("custom:"+json)
    check(v.is_live and v.playback.backend.IsDeployment() and not v.playback.playing,"Custom armies open in deployment")
    check(v.playback.current.units.size()==12,"Custom roster is authoritative")
    v.playback.advance(2);v.playback.single_step();check(v.playback.tick==0,"Deployment never advances simulation")
    v.units.selected=0;v.refresh_frame();v.refresh_ui()
    check(v.playback.issue_autonomy(0,true),"Individual autonomy can be assigned during deployment")
    check(v.playback.current.units[0].autonomy=="autonomous","Deployment autonomy is visible immediately")
    check(v.playback.current.units[1].autonomy!="autonomous","Releasing one regiment does not release its whole army")
    check(v.playback.issue_autonomy(0,false),"Selected regiment can be pinned to Hold before battle")
    v.action("army:1:hold_the_line")
    var edited=JSON.parse_string(v.playback.backend.GetConfiguration())
    check(edited.ai_strategies[1]=="hold_the_line","Saved recipe retains AI-dialog strategy edits")
    v.action("army:1:balanced")
    check(v.hud.deploy_button.visible and not v.hud.order_buttons.column.disabled,"Deployment formation controls active")
    var p: Vector2=v.playback.current.units[0].position
    check(not v.playback.edit_deployment(0,Vector2(500,300),0,"line"),"Out-of-zone position rejected")
    check(v.playback.current.units[0].position==p,"Invalid edit is transactional")
    check(v.playback.edit_deployment(0,p-Vector2(8,0),0,"line"),"Valid deployment movement")
    var pixel: Vector2=v.rig.camera.unproject_position(Vector3(p.x-12,0,p.y))
    v.move_selected(pixel)
    check(v.playback.current.units[0].position.distance_to(p-Vector2(12,0))<.1,"Right-click deployment uses terrain-aware picking")
    v.action("live:column");check(v.playback.current.units[0].formation=="column" and v.playback.tick==0,"Deployment formation changes are immediate and safe")
    v.action("deploy:reset");check(v.playback.current.units[0].position==p,"Reset positions preserves stable regiment IDs")
    await capture("/tmp/rtt-sandbox-deployment.png")
    var officer: String=v.playback.current.units[0].info.commander
    v.hud.ai_dialog.popup_centered_clamped(Vector2i(620,650),.95);v.refresh_ui()
    check(v.hud.upgrade_options.has("rolling_volley"),"Ability selection lists compatible options")
    check(v.playback.set_upgrades(0,["rolling_volley","swift_reform","rallying_presence"]),"Three sandbox abilities assigned to officer")
    check(not v.playback.set_upgrades(0,["mobile_battery"]),"Incompatible ability rejected")
    check(not v.playback.set_upgrades(0,["rolling_volley","swift_reform","rallying_presence","inspired_attack"]),"Ability limit enforced")
    v.refresh_ui();check(v.hud.inspector.text.contains("Acquired abilities") and v.hud.inspector.text.contains("Rolling Volley"),"Inspector displays owned abilities")
    v.hud.ai_dialog.hide()
    var path: String="user://sandbox-roundtrip.json"
    check(v.playback.backend.SaveConfiguration(ProjectSettings.globalize_path(path)),"Recipe saves from deployment")
    var saved:=FileAccess.get_file_as_string(path)
    v.action("setup");setup.loading=true;setup.file_selected(path)
    check(setup.message.text.begins_with("Loaded"),"Setup file chooser loads saved recipes")
    setup.hide()
    v.action("custom:"+saved)
    check(v.playback.current.units[0].info.commander==officer and v.playback.current.units[0].upgrades.size()==3,"Officers and abilities survive file roundtrip")
    var recipe=JSON.parse_string(saved);recipe.blue={"infantry":1,"cavalry":0,"artillery":0,"specialists":{}};recipe.red=recipe.blue.duplicate(true);recipe.placements=[]
    recipe.ai_armies=[0,1];recipe.terrain=null;recipe.width=600;recipe.height=400;recipe.name="UI integration duel"
    v.action("custom:"+JSON.stringify(recipe));v.action("deploy:start")
    check(not v.playback.backend.IsDeployment() and v.playback.playing,"Start enters live combat")
    v.playback.warm_start(10000);v.refresh_frame();v.refresh_ui()
    check(v.playback.result!="","Full custom AI duel reaches a result")
    if v.playback.result=="":quit(1);return
    v._process(.01)
    check(v.hud.results_dialog.visible,"Existing live battle transitions to results")
    var report=v.hud.results_dialog.report
    check(report.armies.size()==2 and report.regiments.size()==2,"Results contain both armies and individual regiments")
    check(v.hud.results_dialog.size.y<=root.size.y,"Results fit the viewport")
    await capture("/tmp/rtt-sandbox-results.png")
    v.hud.results_dialog.view_filter.select(1);v.hud.results_dialog.refresh()
    check(v.hud.results_dialog.rows().size()==2,"Grouped archetype statistics")
    v.hud.results_dialog.army_filter.select(1);v.hud.results_dialog.refresh()
    check(v.hud.results_dialog.rows().size()==1,"Report army filtering")
    v.hud.results_dialog.hide();v.action("rematch")
    check(v.playback.tick==0 and v.playback.backend.GetSeed()==18,"Rematch uses a new combat seed")
    check(not v.playback.edit_commander(0,"methodical","artillerist"),"Commander compatibility remains authoritative")
    v.action("setup");check(v.hud.setup_dialog.visible,"Return from battle to editable setup")
    setup=v.hud.setup_dialog;setup.loading=true;setup.file_selected("user://missing-battle.json")
    check(setup.message.text.contains("Cannot open"),"Missing configuration errors are readable")
    setup.hide();v.action("mode:replay");check(not v.is_live and not v.playback.current.units.is_empty(),"Python replay still works")
    root.size=Vector2i(800,600);await process_frame;v.action("setup");await process_frame
    check(v.hud.setup_dialog.size.x<=root.size.x and v.hud.setup_dialog.size.y<=root.size.y,"Setup fits small windows")
    if DisplayServer.get_name()!="headless" and "--test-capture" in OS.get_cmdline_user_args():
        await process_frame;await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("/tmp/rtt-sandbox-setup.png")
    v.queue_free();await process_frame
    print("Godot sandbox checks: ",checks,", failed: ",failed);quit(1 if failed else 0)
