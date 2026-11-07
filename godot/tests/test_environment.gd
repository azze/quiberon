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
    await process_frame;await process_frame;RenderingServer.force_draw();root.get_texture().get_image().save_png(path)
func run() -> void:
    root.size=Vector2i(1280,800)
    if DisplayServer.get_name()!="headless":root.show()
    var v:=Viewer.new();root.add_child(v);await process_frame;await process_frame;v.set_process(false)
    v.live_scenario="environment-vistula";check(v.start_live(),"Vistula development map loads");v.playback.playing=false
    var b=v.playback.backend
    var e: Dictionary=v.playback.source.terrain.environment
    check(e.water.size()>0 and e.crossings.size()==2 and e.roads.size()==2 and e.defences.size()==2,"Same native map exports every environment feature")
    check(v.surface.nx>100 and v.surface.heights.size()>10000,"Native elevation grid used by terrain mesh")
    check(v.surface.model.is_water(Vector2(600,200)),"Water polygon matches actual river")
    check(v.surface.bridge_decks.size()==1 and absf(v.surface.height_at(Vector2(600,412.9))-.15)<.001,"Soldiers and picking use exact bridge deck elevation")
    check(v.hud.crossing_choice.item_count==3,"Manual crossing choice includes bridge, ford, automatic")
    v.action("route:south_ford");check(v.playback.preferred_crossing=="south_ford","Player can pin a crossing")
    check(not b.IssueMove(0,Vector2(600,200)),"Manual destination rejects deep water")
    v.rig.fit(true);v.refresh_frame();v.refresh_ui()
    var builds: int=v.environmental_view.builds
    v.effects.debug_enabled=true;v.refresh_frame()
    check(v.environmental_view.line_count>0,"Debug overlay exposes river banks and crossings")
    check(v.environmental_view.feature_count>=7,"Static environment geometry built")
    await capture("/tmp/rtt-environment-vistula.png")
    v.playback.single_step();v.refresh_frame()
    check(v.environmental_view.builds==builds,"Simulation ticks reuse static environment meshes")
    var tick: int=v.playback.tick;v.action("2d")
    check(v.view_2d and v.playback.tick==tick,"2D retains current river battle")
    await capture("/tmp/rtt-environment-2d.png")
    v.action("2d");check(not v.view_2d,"Return to same 3D battle")
    v.live_scenario="environment-rain";check(v.start_live(),"Rain scenario loads");v.playback.playing=false;v.rig.fit(true);v.refresh_frame()
    check(v.environmental_view.rain!=null and v.environmental_view.rain.multimesh.instance_count==200,"Bounded deterministic visual rain")
    check(v.sunlight.light_energy<1,"Rain dims atmospheric lighting")
    await capture("/tmp/rtt-environment-rain.png")
    v.live_scenario="environment-fog";check(v.start_live(),"Fog scenario loads");v.playback.playing=false;v.rig.fit(true);v.refresh_frame()
    check(v.atmosphere.fog_enabled,"Fog preset controls existing world atmosphere")
    var hidden:=0
    for u in v.playback.current.units.values():
        if not u.observed:hidden+=1;check(not v.units.poses.has(u.info.id),"Unseen enemy has no pickable pose")
    check(hidden>0,"Distant enemies hidden by authoritative army LOS")
    await capture("/tmp/rtt-environment-fog.png")
    v.action("setup");var setup=v.hud.setup_dialog
    check(setup.weather_choice.item_count==3,"Custom setup offers fixed Clear, Rain and Fog")
    setup.hide()
    var recipe: String=b.GetBattlePreset("environment_vistula_lab")
    check(recipe!="","Editable custom laboratory preset bundled")
    var fog_recipe: String=b.ConfigurationWeather(recipe,"fog")
    check(fog_recipe!="" and b.InitializeCustom(fog_recipe),"Weather override preserves custom environmental geometry")
    var saved: String=b.GetConfiguration()
    check(saved.contains("vistula") and saved.contains("fog") and saved.contains("crossings"),"Save includes versioned environmental definition")
    check(b.InitializeCustom(saved),"Saved custom battlefield reloads")
    v.action("mode:replay");v.seek(60)
    check(not v.is_live and v.playback.time==60,"Python replay seeking still works")
    check(not v.atmosphere.fog_enabled and v.environmental_view.rain==null,"Weather clears when returning to old recording")
    v.queue_free();await process_frame
    print("Godot environment checks: ",checks," failed: ",failed);quit(1 if failed else 0)
