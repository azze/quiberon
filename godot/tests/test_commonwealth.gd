extends SceneTree
const Viewer=preload("res://scripts/three_d/viewer_3d.gd")
const Kit=preload("res://scripts/three_d/mesh_kit.gd")
var checks:=0
var failed:=false
func check(value: bool,message: String) -> void:
    checks+=1
    if not value:failed=true;push_error(message)
func _initialize() -> void:run.call_deferred()
func capture(path: String) -> void:
    if DisplayServer.get_name()=="headless" or "--test-capture" not in OS.get_cmdline_user_args():return
    await process_frame;await process_frame;RenderingServer.force_draw();root.get_texture().get_image().save_png(path)
func run() -> void:
    root.size=Vector2i(1280,800)
    if DisplayServer.get_name()!="headless":root.show()
    var v:=Viewer.new();root.add_child(v);await process_frame;await process_frame;v.set_process(false)
    v.action("setup")
    var setup=v.hud.setup_dialog
    check(setup.catalogue.size()==20,"All fifteen core and five legacy sandbox types")
    var core: Array=setup.catalogue.filter(func(a):return a.campaign_core)
    check(core.size()==15,"Exactly fifteen initial campaign units")
    setup.unit_picker.open_picker(setup,0,setup.catalogue)
    var picker=setup.unit_picker
    var prussia: int=-1
    for i in picker.faction_filter.item_count:
        if picker.faction_filter.get_item_text(i)=="Prussia":prussia=i
    check(prussia>=0,"Faction filter includes Prussia")
    picker.faction_filter.select(prussia);picker.set_filter("cavalry")
    check(picker.filtered.size()==1 and picker.filtered[0].id=="prussian_cuirassiers","Faction and category filters combine")
    await capture("/tmp/rtt-commonwealth-roster.png")
    picker.hide();setup.hide()
    v.live_scenario="commonwealth-battle-coalition";v.start_live();v.playback.playing=false
    check(v.is_live and v.playback.current.units.size()==16,"Combined coalition scenario loads through the existing live renderer")
    v.rig.fit(true);v.refresh_frame()
    await capture("/tmp/rtt-commonwealth-coalition.png")
    check(v.units.visuals.size()==16,"Existing batched renderer displays every coalition regiment")
    var b=v.playback.backend
    check(b.GetArmyCommanders().size()==2,"Two separate army commander roles")
    check(b.GetArmyCommander(0)=="tadeusz_kosciuszko" and b.GetArmyCommander(1)=="alexander_suvorov","Army leaders remain separate from regiment officers")
    check(not b.AssignArmyCommander(0,"alexander_suvorov"),"An army commander cannot appear twice")
    check(not b.AssignHistoricalCommander(1,"franciszek_ksawery_niesiolowski"),"Historical regiment commander is unique across battle")
    v.units.selected=0;v.hud.ai_dialog.popup_centered_clamped(Vector2i(620,650),.95);v.refresh_frame();v.refresh_ui()
    check(v.hud.historical_option.item_count>=8,"Compatible historical officers shown before battle")
    check(v.hud.specialty_option.disabled,"Historical signature is fixed; generic reroll stays available")
    check(not v.hud.reroll_button.disabled,"Can replace historical commander with a generic officer")
    await capture("/tmp/rtt-commonwealth-commanders.png")
    check(v.hud.inspector.text.contains("Niesiołowski"),"Diacritics survive adapter and inspector")
    v.action("historical:jan_henryk_dabrowski")
    check(b.GetHistoricalDefinition(0)=="jan_henryk_dabrowski","Historical assignment action reaches authoritative C#")
    v.refresh_ui();check(v.hud.inspector.text.contains("Dąbrowski"),"Inspector updates after assignment")
    v.units.selected=2;v.refresh_frame();v.refresh_ui()
    check(v.playback.current.units[2].combat_capable and not v.playback.current.units[2].ranged_capable,"Scythemen can receive combat orders without a fake firearm")
    check(not v.hud.order_buttons.charge.disabled,"Melee-only infantry charge control enabled")
    check(v.hud.inspector.text.contains("no ranged weapon"),"Inspector describes actual melee-only capability")
    v.hud.ai_dialog.hide()
    var scythe_mesh:=Kit.figure(v.units.profiles.commonwealth_scythemen,"infantry")
    check(scythe_mesh.get_surface_count()==1,"Scythe silhouette uses the shared mesh kit")
    var stamp: float=b.GetTime();v.action("2d")
    check(v.view_2d and b.GetTime()==stamp,"Current live coalition battle switches to 2D without advancing")
    v.action("2d");check(not v.view_2d and v.playback.current.units.size()==16,"Return to same 3D battle")
    v.playback.single_step();v.refresh_frame();v.refresh_ui()
    check(not b.AssignHistoricalCommander(0,"jan_henryk_dabrowski"),"Historical editing locks after first tick")
    check(v.playback.current.units[0].commander_effects.contains("Flexible Manoeuvres"),"Actual signature conditions exposed in state")
    # Deployment/save path uses the same custom setup, never a campaign state.
    var recipe: String=b.GetBattlePreset("commonwealth_lab_coalition")
    check(recipe!="","Custom-battle laboratory preset is bundled")
    v.action("custom:"+recipe);v.playback.playing=false
    check(v.playback.backend.IsDeployment(),"Laboratory preset supports ordinary deployment")
    var saved: String=v.playback.backend.GetConfiguration()
    check(saved.contains("definition_id") and saved.contains("army_commanders"),"Recipe retains authored identities and separate army roles")
    check(v.playback.backend.InitializeCustom(saved),"Custom historical coalition reloads")
    v.playback.synchronize()
    check(v.playback.backend.GetHistoricalDefinition(5)=="joseph_louis_cook","Cook identity preserved through custom save/load")
    v.live_scenario="commonwealth-canister";v.start_live();v.playback.playing=false;v.playback.single_step();v.refresh_frame()
    check(v.playback.backend.GetMetrics().active_projectiles>0,"Authoritative physical canister reaches live projectile rendering")
    v.action("mode:replay")
    check(not v.is_live and v.playback.current.units.size()==12,"Python replay remains available")
    v.queue_free();await process_frame
    print("Godot Commonwealth checks: ",checks," failed: ",failed);quit(1 if failed else 0)
