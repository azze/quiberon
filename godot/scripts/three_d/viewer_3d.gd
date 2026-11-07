extends Control
## 3D presentation controller. The original 2D scene remains unchanged.
const Source=preload("res://scripts/recording_source.gd")
const Playback=preload("res://scripts/playback.gd")
const Surface=preload("res://scripts/three_d/terrain_surface.gd")
const TerrainView=preload("res://scripts/three_d/terrain_mesh.gd")
const ForestView=preload("res://scripts/three_d/forest_view.gd")
const Units=preload("res://scripts/three_d/regiment_view_3d.gd")
const Effects=preload("res://scripts/three_d/effects_3d.gd")
const Markers=preload("res://scripts/three_d/unit_markers.gd")
const Rig=preload("res://scripts/three_d/tactical_camera.gd")
const HUD=preload("res://scripts/three_d/replay_hud.gd")
const World=preload("res://scripts/three_d/world_3d.gd")
const Live=preload("res://scripts/simulation_adapter/live_source.gd")
const FlatView=preload("res://scripts/battlefield_2d.gd")
var flat_view: FlatView
var view_2d: bool=false
const Frame=preload("res://scripts/battle_frame.gd")
const OrderPreview=preload("res://scripts/three_d/order_preview.gd")
const RangeIndicator=preload("res://scripts/three_d/range_indicator.gd")
var order_preview: OrderPreview
var range_indicator: RangeIndicator
var gesture: Dictionary={}
var gesture_cursor:=Vector2.ZERO
const DeploymentOverlay=preload("res://scripts/three_d/deployment_overlay.gd")
var deployment_overlay: DeploymentOverlay
var presentation: Resource=preload("res://resources/presentation_3d.tres").duplicate(true)
var playback: RefCounted
var is_live: bool=false
var live_count: int=8
var live_terrain: bool=false
var live_scenario: String="ai-player"
var live_dynamics: bool=true
var live_seed: int=17
var custom_recipe: String=""
var report_shown: bool=false
var order_notice: String=""
var order_notice_left: float=0
var recording_path: String="res://recordings/combined-arms/metadata.json"
var surface: Surface
var viewport: SubViewport
var terrain_view: TerrainView
var forests: ForestView
var units: Units
var effects: Effects
var rig: Rig
var markers: Markers
var hud: HUD
const EnvironmentalView=preload("res://scripts/three_d/environment_view.gd")
var environmental_view: EnvironmentalView
var atmosphere: Environment
var sunlight: DirectionalLight3D
var ui_elapsed: float=0
var load_ms: float=0
var load_error: String=""
var mission_panel: Label
var mission_overlay: MeshInstance3D
var screenshot_path: String=""
var screenshot_written: bool=false
var benchmark_frames: int=0
var benchmark_output: String=""
var warmup: int=60
var timings: Array=[]
var updates: Array=[]
var last_process: int=0
var update_ms: float=0
func _ready() -> void:
    set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);mouse_filter=Control.MOUSE_FILTER_IGNORE
    var container:=SubViewportContainer.new();add_child(container)
    container.anchor_right=1;container.anchor_bottom=1;container.offset_left=10;container.offset_top=162;container.offset_right=-308;container.offset_bottom=-96;container.stretch=true
    viewport=SubViewport.new();viewport.own_world_3d=true;viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;container.add_child(viewport)
    viewport.msaa_3d=Viewport.MSAA_2X
    flat_view=FlatView.new();viewport.add_child(flat_view)
    flat_view.selection_requested.connect(select_at);flat_view.secondary_started.connect(begin_order)
    flat_view.secondary_updated.connect(func(pixel):gesture_cursor=pixel)
    flat_view.secondary_requested.connect(finish_order);flat_view.secondary_cancelled.connect(cancel_order)
    var world:=Node3D.new();viewport.add_child(world)
    var environment:=WorldEnvironment.new();environment.environment=Environment.new();world.add_child(environment)
    atmosphere=environment.environment
    var env:=environment.environment;env.background_mode=Environment.BG_COLOR;env.background_color=Color("#c3cfcc")
    env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.ambient_light_color=Color("#e0e8df");env.ambient_light_energy=.65
    sunlight=DirectionalLight3D.new();sunlight.rotation_degrees=Vector3(-55,-35,0);sunlight.light_energy=1.1;sunlight.shadow_enabled=presentation.shadows;sunlight.directional_shadow_max_distance=1200;world.add_child(sunlight)
    environmental_view=EnvironmentalView.new();world.add_child(environmental_view)
    terrain_view=TerrainView.new();world.add_child(terrain_view);forests=ForestView.new();world.add_child(forests)
    deployment_overlay=DeploymentOverlay.new();deployment_overlay.visible=false;world.add_child(deployment_overlay)
    units=Units.new();world.add_child(units);effects=Effects.new();world.add_child(effects)
    order_preview=OrderPreview.new();world.add_child(order_preview);range_indicator=RangeIndicator.new();world.add_child(range_indicator)
    rig=Rig.new();rig.settings=rig.settings.duplicate(true);world.add_child(rig)
    var overlay:=CanvasLayer.new();viewport.add_child(overlay);markers=Markers.new();overlay.add_child(markers);markers.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);markers.renderer=units;markers.camera=rig.camera
    rig.selection_requested.connect(select_at)
    rig.secondary_started.connect(begin_order)
    rig.secondary_updated.connect(func(pixel):gesture_cursor=pixel)
    rig.secondary_requested.connect(finish_order)
    rig.secondary_cancelled.connect(cancel_order)
    hud=HUD.new();add_child(hud);hud.configure_camera(rig.settings)
    mission_panel=Label.new();mission_panel.position=Vector2(22,170);mission_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE;mission_panel.add_theme_color_override("font_shadow_color",Color.BLACK);mission_panel.add_theme_constant_override("shadow_offset_x",2);mission_panel.add_theme_constant_override("shadow_offset_y",2);add_child(mission_panel)
    mission_overlay=preload("res://scripts/three_d/mission_overlay.gd").new();world.add_child(mission_overlay)
    hud.action_requested.connect(action);hud.recording_selected.connect(load_recording);hud.seek_requested.connect(seek)
    viewport.size_changed.connect(rig.viewport_resized);viewport.size_changed.connect(flat_view.viewport_resized)
    var path: String="res://recordings/combined-arms/metadata.json";var paused:=false;var at: float=-1
    var projection_override: Variant=null
    var campaign_stage:=0
    var start_live_mode: bool=false;var march: bool=false;var combat_argument: String="";var pre_roll: int=0;var live_speed: float=1
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--campaign-stage="):campaign_stage=int(arg.trim_prefix("--campaign-stage="))
        elif arg.begins_with("--recording="):path=arg.trim_prefix("--recording=")
        elif arg=="--paused":paused=true
        elif arg.begins_with("--seek="):at=float(arg.trim_prefix("--seek="))
        elif arg.begins_with("--screenshot="):screenshot_path=arg.trim_prefix("--screenshot=")
        elif arg.begins_with("--benchmark-frames="):benchmark_frames=int(arg.trim_prefix("--benchmark-frames="))
        elif arg.begins_with("--benchmark-output="):benchmark_output=arg.trim_prefix("--benchmark-output=")
        elif arg=="--perspective":projection_override=true
        elif arg=="--orthographic":projection_override=false
        elif arg=="--live":start_live_mode=true
        elif arg=="--legacy-combat":live_dynamics=false
        elif arg.begins_with("--live-warmup-ticks="):pre_roll=clampi(int(arg.trim_prefix("--live-warmup-ticks=")),0,100000)
        elif arg.begins_with("--live-speed="):live_speed=clampf(float(arg.trim_prefix("--live-speed=")),.25,10)
        elif arg.begins_with("--live-seed="):live_seed=int(arg.trim_prefix("--live-seed="))
        elif arg=="--live-terrain":start_live_mode=true;live_terrain=true;live_scenario="movement"
        elif arg=="--march":march=true;live_scenario="movement"
        elif arg.begins_with("--live-count="):live_count=clampi(int(arg.trim_prefix("--live-count=")),2,256);live_scenario="movement"
        elif arg.begins_with("--combat-scenario="):combat_argument=arg.trim_prefix("--combat-scenario=");start_live_mode=true
        elif arg.begins_with("--figures="):presentation.figures_per_regiment=clampi(int(arg.trim_prefix("--figures=")),1,64)
    await get_tree().process_frame # Container has established the 3D viewport aspect.
    if combat_argument!="":live_scenario=combat_argument
    if campaign_stage>0:
        var lab=load("res://scripts/simulation_adapter/CampaignBridge.cs").new();lab.PrepareLaboratory(campaign_stage,"1796","rescue");lab.free()
        live_scenario="campaign";start_live();playback.backend.StartDeployedBattle();playback.synchronize()
    elif start_live_mode:start_live(march)
    else:load_recording(path)
    if "--setup" in OS.get_cmdline_user_args():action("setup")
    if playback!=null:
        if is_live:
            if pre_roll>0:playback.warm_start(pre_roll);last_process=Time.get_ticks_usec()
            playback.speed=live_speed
            var index: int=[.25,.5,1.,2.,4.,10.].find(live_speed)
            if index>=0:hud.speeds.select(index)
        playback.playing=not paused
        if at>=0 and not is_live:playback.seek(at)
        # Select explicitly: --perspective must not toggle the new default off.
        if projection_override!=null:
            rig.perspective=projection_override;rig.fit(true)
        refresh_frame()
        for arg in OS.get_cmdline_user_args():
            if arg.begins_with("--focus-id="):
                units.selected=int(arg.trim_prefix("--focus-id="))
                var point: Variant=units.ground_position(units.selected)
                if point!=null:rig.focus=World.horizontal(point);rig.target_focus=rig.focus;rig.fit_mode=false
            elif arg.begins_with("--camera-span="):rig.span=clampf(float(arg.trim_prefix("--camera-span=")),rig.settings.minimum_zoom,rig.max_span);rig.target_span=rig.span;rig.fit_mode=false
            elif arg.begins_with("--camera-pitch="):rig.pitch=deg_to_rad(clampf(float(arg.trim_prefix("--camera-pitch=")),rig.settings.minimum_pitch,rig.settings.maximum_pitch));rig.target_pitch=rig.pitch
        rig.update_pose();refresh_frame();refresh_ui()
    if get_tree().root.has_meta("menu_mode"):
        var menu_mode: String=get_tree().root.get_meta("menu_mode");get_tree().root.remove_meta("menu_mode")
        if menu_mode=="campaign":live_scenario="campaign";start_live();playback.playing=false
        elif menu_mode=="live":start_live()
        elif menu_mode=="custom":action("setup")
    if benchmark_frames>0:
        Engine.max_fps=0
        if DisplayServer.get_name()!="headless":DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
func load_recording(path: String) -> bool:
    var start:=Time.get_ticks_usec();var source:=Source.new()
    if not source.load_recording(path):load_error=source.error;hud.status.text=load_error;return false
    var next:=Playback.new()
    if not next.attach(source):load_error=source.error;hud.status.text=load_error;return false
    playback=next;recording_path=path;is_live=false;install_presentation()
    load_ms=(Time.get_ticks_usec()-start)/1000.0;refresh_frame();refresh_ui();return true
func start_live(march: bool=false) -> bool:
    if is_live and playback!=null and playback.backend.IsCustom():custom_recipe=playback.backend.GetConfiguration()
    var start:=Time.get_ticks_usec();var next:=Live.new()
    if not next.attach(live_count,live_terrain,march,live_scenario,live_dynamics,live_seed,custom_recipe):
        load_error=next.error;hud.status.text=load_error;hud.mode_selector.select(1 if is_live else 0);return false
    playback=next;is_live=true;install_presentation()
    load_ms=(Time.get_ticks_usec()-start)/1000.;refresh_frame();refresh_ui();return true
func install_presentation() -> void:
    rig.cancel_secondary()
    var source=playback.source
    report_shown=false;hud.results_dialog.hide();load_error="";order_notice="";order_notice_left=0;surface=Surface.new();surface.configure(source.terrain,presentation.terrain_spacing,presentation.terrain_vertex_budget)
    terrain_view.configure(surface);forests.configure(surface,presentation);units.configure(surface,presentation,source.armies);units.selected=-1;effects.surface=surface
    environmental_view.configure(surface,source.terrain.environment,atmosphere,sunlight)
    deployment_overlay.configure(surface,playback.backend.GetDeploymentZones() if is_live else [])
    flat_view.deployment_zones=playback.backend.GetDeploymentZones() if is_live else []
    flat_view.configure(source.terrain,source.armies)
    if view_2d:flat_view.activate(true)
    hud.crossing_choice.clear();hud.crossing_choice.add_item("Route: Auto");hud.crossing_choice.set_item_metadata(0,"")
    for crossing in source.terrain.environment.get("crossings",[]):
        hud.crossing_choice.add_item(crossing.id);hud.crossing_choice.set_item_metadata(hud.crossing_choice.item_count-1,crossing.id)
    hud.crossing_choice.visible=is_live and hud.crossing_choice.item_count>1
    rig.configure(surface);hud.set_live(is_live,("terrain-march" if live_terrain else "movement") if is_live and live_scenario=="movement" else live_scenario,is_live and playback.combat_enabled,is_live and playback.morale_enabled,playback.choices if is_live else [])
    viewport.get_parent().offset_bottom=-130 if is_live and playback.morale_enabled else -96
    if is_live and playback.backend.IsCampaign():hud.mode_selector.disabled=true;hud.scenario_selector.disabled=true
    if not is_live:hud.bind_range(source.times[0],source.times[-1])
    hud.speeds.select(2)
    last_process=Time.get_ticks_usec() # Loading/setup time is not live battle time.
func ground_under(pixel: Vector2) -> Variant:
    if not view_2d:return rig.ground_under(pixel)
    var point:=flat_view.screen_to_world(pixel)
    return World.ground(point,surface.height_at(point)) if Rect2(Vector2.ZERO,surface.size).has_point(point) else null
func pick_at(pixel: Vector2,hit: Variant) -> int:
    if view_2d:return flat_view.pick(pixel)
    var uid:=markers.pick(pixel)
    return units.pick(hit) if uid<0 and hit!=null else uid
func toggle_2d() -> void:
    rig.cancel_secondary();flat_view.cancel_secondary();rig.end_drag()
    view_2d=not view_2d
    viewport.disable_3d=view_2d;flat_view.activate(view_2d);markers.visible=not view_2d
    rig.navigation_enabled=not view_2d and not hud.blocked();flat_view.navigation_enabled=view_2d and not hud.blocked()
    hud.view_button.text="3D view" if view_2d else "2D view"
    last_process=Time.get_ticks_usec() # Building a cached map is not battle time.
    refresh_frame();refresh_ui()
func select_at(pixel: Vector2) -> void:
    if playback==null or hud.blocked():return
    var hit: Variant=ground_under(pixel)
    var uid:=pick_at(pixel,hit)
    units.selected=uid
    if is_live and not playback.backend.IsDeployment() and not playback.ai_enabled and uid>=0 and playback.current.units[uid].info.army!=0:units.selected=-1
    if rig.follow_id>=0:rig.follow_id=units.selected;rig.follow_offset=Vector2.ZERO;rig.velocity=Vector2.ZERO
    if flat_view.follow_id>=0:flat_view.follow_id=units.selected
    refresh_frame();refresh_ui()
func move_selected(pixel: Vector2) -> void:
    # Direct-click interface retained for tools. Real input commits on release.
    begin_order(pixel);finish_order(pixel)
func cancel_order() -> void:
    gesture.clear()
    if order_preview!=null:order_preview.hide_preview()
func begin_order(pixel: Vector2) -> void:
    cancel_order()
    if not is_live or playback==null or hud.blocked() or units.selected<0 or playback.result!="":return
    var u: Object=playback.current.units.get(units.selected)
    if u==null or not u.effective:return
    var deployment: bool=playback.backend.IsDeployment()
    if not deployment and u.info.army!=0:return
    var hit: Variant=ground_under(pixel)
    if not deployment:
        var enemy:=pick_at(pixel,hit)
        if enemy>=0 and playback.current.units[enemy].info.army!=u.info.army:
            gesture={"unit":units.selected,"attack":enemy};return
    if hit==null:return
    var point: Vector2=World.horizontal(hit)
    if not deployment:point=playback.backend.GetMoveDestination(units.selected,point)
    var default_facing: float=u.facing if deployment or point.distance_to(u.position)<1 else (point-u.position).angle()
    gesture={"unit":units.selected,"destination":point,"start_pixel":pixel,"default_facing":default_facing,"facing":null,"deployment":deployment}
    gesture_cursor=pixel;update_order_preview()
func update_order_preview() -> void:
    if gesture.is_empty() or gesture.has("attack"):return
    var u: Object=playback.current.units.get(gesture.unit)
    if hud.blocked() or units.selected!=gesture.unit or u==null or not u.effective or playback.result!="" or gesture.deployment!=playback.backend.IsDeployment():cancel_order();return
    if gesture_cursor.distance_to(gesture.start_pixel)>=8:
        var ray_key: Array=[gesture_cursor,flat_view.camera.get_screen_center_position(),flat_view.camera.zoom] if view_2d else [gesture_cursor,rig.camera.global_transform]
        if gesture.get("ray_key",[])!=ray_key:
            gesture.ray_key=ray_key
            var hit: Variant=ground_under(gesture_cursor)
            if hit!=null:
                var delta: Vector2=World.horizontal(hit)-gesture.destination
                if delta.length()>.0001:gesture.facing=delta.angle()
    var facing: float=gesture.default_facing if gesture.facing==null else gesture.facing
    var validation_key: Array=[playback.current,facing,u.formation]
    if gesture.get("validation_key",[])!=validation_key:
        gesture.validation_key=validation_key
        gesture.validation_reason=playback.backend.CheckDeployment(gesture.unit,gesture.destination,facing,u.formation) if gesture.deployment else playback.backend.CheckMoveDestination(gesture.unit,gesture.destination)
    var reason: String=gesture.validation_reason
    order_preview.display(u,gesture.destination,facing,reason=="",reason,units)
func finish_order(pixel: Vector2) -> void:
    if gesture.is_empty():return
    gesture_cursor=pixel;update_order_preview()
    if gesture.is_empty():return
    var pending: Dictionary=gesture.duplicate();cancel_order()
    if hud.blocked() or units.selected!=pending.unit or playback.result!="":return
    var u: Object=playback.current.units.get(pending.unit)
    if u==null or not u.effective:return
    var accepted:=false
    if pending.has("attack"):
        accepted=playback.issue_attack(pending.unit,pending.attack);order_notice="Attack queued" if accepted else "Attack unavailable"
    elif pending.deployment:
        accepted=playback.edit_deployment(pending.unit,pending.destination,pending.default_facing if pending.facing==null else pending.facing,u.formation)
        order_notice="Deployment updated" if accepted else playback.backend.SetupError
    else:
        accepted=playback.issue_move(pending.unit,pending.destination,pending.facing)
        order_notice="Move queued"+(" with arrival facing" if pending.facing!=null else "") if accepted else "Movement unavailable"
    order_notice_left=5;refresh_frame();refresh_ui()
func seek(time: float) -> void:
    if playback==null or is_live:return
    if not playback.seek(time):load_error=playback.source.error
    refresh_frame();refresh_ui()
func action(key: String) -> void:
    if key.begins_with("route:") and is_live:playback.preferred_crossing=key.trim_prefix("route:");return
    if key in ["restart","rematch","deploy:start","deploy:reset","setup","menu","2d"]:rig.cancel_secondary();flat_view.cancel_secondary()
    if key=="menu":get_tree().change_scene_to_file("res://scenes/main_menu.tscn");return
    if key=="setup" or key=="deploy:save":
        if playback!=null:playback.playing=false
        var native: Object=playback.backend if is_live else null
        if native==null:
            if not ClassDB.class_exists("CSharpScript"):load_error="Custom battles require the Godot .NET edition.";refresh_ui();return
            var script: Script=load("res://scripts/simulation_adapter/LiveSimulationBridge.cs")
            if script==null or not script.can_instantiate():load_error="Build godot/Quiberon.csproj to enable custom battles.";refresh_ui();return
            native=script.new()
        hud.setup_dialog.open_setup(native,native.GetConfiguration() if is_live else custom_recipe)
        return
    if key.begins_with("custom:"):
        var next:=Live.new()
        if not next.attach(8,false,false,"custom",true,live_seed,key.trim_prefix("custom:")):hud.setup_dialog.message.text=next.error;return
        custom_recipe=next.backend.GetConfiguration();hud.setup_dialog.hide();playback=next;is_live=true;live_scenario="custom";playback.playing=false;install_presentation();refresh_frame();refresh_ui();return
    if is_live and playback.backend.IsCampaign():
        if key=="campaign:continue":
            if playback.result!="" and playback.backend.CompleteCampaign():get_tree().change_scene_to_file("res://scenes/campaign.tscn")
            return
        if key in ["restart","rematch","setup"] or key.begins_with("historical:") or key.begins_with("army_commander:"):return
    if key=="results" and is_live:
        playback.playing=false;hud.results_dialog.open_report(playback.backend.GetBattleReportJson());hud.results_dialog.set_campaign(playback.backend.IsCampaign(),playback.result!="");return
    if key=="rematch" and is_live:
        live_seed=playback.backend.GetSeed()+1;playback.backend.Rematch(live_seed);playback.seed=live_seed;playback.source.seed_text=str(live_seed);playback.cached_tick=-1;playback.refresh();playback.playing=false;report_shown=false;refresh_frame();refresh_ui();return
    if key.begins_with("upgrades:") and is_live:
        var keys=JSON.parse_string(key.trim_prefix("upgrades:"))
        if keys is Array:
            var ok: bool=playback.set_upgrades(units.selected,keys)
            order_notice="Commander abilities assigned" if ok else playback.backend.SetupError;order_notice_left=5
        refresh_frame();refresh_ui();return
    if key.begins_with("deploy:") and is_live:
        if key=="deploy:start":
            if playback.backend.StartDeployedBattle():playback.playing=true;last_process=Time.get_ticks_usec()
        elif key=="deploy:reset":playback.backend.ResetDeployment();playback.synchronize();playback.playing=false
        elif key=="deploy:rotate" and units.selected>=0:
            var u: Object=playback.current.units[units.selected]
            if not playback.edit_deployment(units.selected,u.position,u.facing+deg_to_rad(15),u.formation):order_notice=playback.backend.SetupError;order_notice_left=6
        refresh_frame();refresh_ui();return
    if key.begins_with("army:") and is_live:
        var bits:=key.split(":");playback.configure_army(int(bits[1]),bits[2]);refresh_frame();refresh_ui();return
    if key.begins_with("historical:") and key!="historical:apply" and is_live:
        if not playback.backend.AssignHistoricalCommander(units.selected,key.trim_prefix("historical:")):
            order_notice=playback.backend.SetupError;order_notice_left=6
        playback.synchronize();refresh_frame();refresh_ui();return
    if key.begins_with("army_commander:") and is_live:
        var bits:=key.split(":")
        if not playback.backend.AssignArmyCommander(int(bits[1]),bits[2]):order_notice=playback.backend.SetupError;order_notice_left=6
        playback.synchronize();refresh_frame();refresh_ui();return
    if key=="commander:reroll" and is_live:playback.edit_commander(units.selected);refresh_frame();refresh_ui();return
    if key.begins_with("commander:set:") and is_live:
        var bits:=key.split(":");playback.edit_commander(units.selected,bits[2],bits[3]);refresh_frame();refresh_ui();return
    if key=="2d":toggle_2d();return
    if view_2d and key in ["fit","focus","follow","overhead","projection"]:
        if key=="fit":flat_view.fit()
        elif units.selected>=0 and playback.current.units.has(units.selected):
            if key=="focus":flat_view.focus_on(playback.current.units[units.selected].position)
            elif key=="follow":flat_view.follow_id=-1 if flat_view.follow_id==units.selected else units.selected
        refresh_ui();return
    if key=="mode:live":start_live();return
    if key=="mode:replay":
        if is_live and playback.backend.IsCustom():custom_recipe=playback.backend.GetConfiguration()
        load_recording(recording_path);return
    if key.begins_with("scenario:"):
        live_scenario=key.trim_prefix("scenario:");live_terrain=live_scenario=="terrain-march"
        if live_terrain:live_scenario="movement"
        start_live();return
    if playback==null:return
    match key:
        "pause":
            if is_live and playback.backend.IsDeployment():action("deploy:start");return
            if not is_live and playback.time>=playback.source.times[-1]:playback.restart()
            elif is_live and playback.result!="":pass
            else:playback.playing=not playback.playing
        "restart":playback.restart();report_shown=false
        "fit":rig.fit()
        "focus":
            var point: Variant=units.ground_position(units.selected)
            if point!=null:rig.focus_on(World.horizontal(point))
        "follow":
            if units.ground_position(units.selected)!=null:
                rig.follow_id=-1 if rig.follow_id==units.selected else units.selected;rig.follow_offset=Vector2.ZERO;rig.velocity=Vector2.ZERO;rig.auto_focus=false;rig.fit_mode=false
        "overhead":rig.toggle_overhead()
        "projection":rig.toggle_projection()
        _:
            if key.begins_with("speed:"):playback.speed=float(key.trim_prefix("speed:"))
            elif is_live and key.begins_with("live:"):
                var order:=key.trim_prefix("live:")
                if order=="step":
                    if not playback.playing:playback.single_step()
                elif units.selected>=0:
                    if playback.backend.IsDeployment() and order in ["line","column","skirmish"]:
                        var u: Object=playback.current.units[units.selected]
                        var ok: bool=playback.edit_deployment(units.selected,u.position,u.facing,order)
                        order_notice="Formation placed" if ok else playback.backend.SetupError;order_notice_left=5;refresh_frame();refresh_ui();return
                    var accepted: bool=false
                    if order=="hold":accepted=playback.issue_hold(units.selected)
                    elif order=="advance":accepted=playback.issue_advance(units.selected)
                    elif order=="charge":accepted=playback.issue_charge(units.selected)
                    elif order=="pursue":accepted=playback.issue_pursue(units.selected)
                    elif order=="disengage":accepted=playback.issue_disengage(units.selected)
                    elif order=="reform":accepted=playback.issue_reform(units.selected)
                    elif order=="cease":accepted=playback.issue_fire_control(units.selected,true)
                    elif order=="fire":accepted=playback.issue_fire_control(units.selected,false)
                    elif order=="auto":accepted=playback.issue_autonomy(units.selected,true)
                    elif order=="ordered":accepted=playback.issue_autonomy(units.selected,false)
                    elif order=="skirmish_order":accepted=playback.issue_skirmish(units.selected)
                    else:accepted=playback.issue_formation(units.selected,order)
                    order_notice=("Order queued: "+order) if accepted else "Order unavailable for this unit or while changing formation."
                    order_notice_left=4
    refresh_frame();refresh_ui()
func refresh_frame() -> void:
    if playback==null:return
    deployment_overlay.visible=is_live and playback.backend.IsDeployment()
    if view_2d:
        flat_view.ghost=order_preview;flat_view.deployment=is_live and playback.backend.IsDeployment()
        flat_view.display(playback.current,playback.following,playback.alpha,playback.time,playback.events,units.selected)
        if is_live:update_order_preview()
        return
    if units.selected>=0 and playback.current.units.has(units.selected) and not playback.current.units[units.selected].observed:units.selected=-1
    units.display(playback.current,playback.following,playback.alpha,playback.time,rig.span)
    if is_live and effects.debug_enabled:environmental_view.crossing_owners=playback.backend.GetEnvironmentMetrics().owners
    environmental_view.display(playback.current,rig,effects.debug_enabled)
    effects.selected_id=units.selected
    effects.display(playback.current,playback.following,playback.alpha,playback.time,playback.events)
    forests.update_visibility(units.ground_position(units.selected),rig.span)
    range_indicator.display(playback.current.units.get(units.selected),units.poses.get(units.selected,{}),surface)
    if is_live:update_order_preview()
    markers.queue_redraw()
func refresh_ui() -> void:
    if playback!=null and is_live:
        var raw: String=playback.backend.GetMissionJson()
        mission_panel.visible=raw!=""
        if raw!="":
            var mission: Dictionary=JSON.parse_string(raw);var lines: Array=[]
            for objective in mission.definitions:
                var state: Dictionary=mission.states.filter(func(s):return s.id==objective.id)[0]
                lines.append(objective.description+" · "+state.status+" · %.0f / %.0f s" % [mission.time if objective.type=="delay" else state.progress,objective.duration])
            if not mission.pending.is_empty():lines.append("Reinforcements awaiting entry: "+str(mission.pending))
            mission_panel.text="\n".join(lines);mission_overlay.configure(mission,surface);flat_view.mission_data=mission
        else:mission_overlay.visible=false;flat_view.mission_data={}
    elif mission_panel!=null:mission_panel.visible=false;mission_overlay.visible=false
    if playback==null:return
    var frame: Frame=playback.current
    hud.status.text="%s · %s | seed %s | %d regiments | %d balls | FPS %d" % ["LIVE" if is_live else "REPLAY",playback.source.title,playback.source.seed_text,frame.units.size(),frame.shots.size(),Engine.get_frames_per_second()]
    if is_live:hud.status.text+=" | tick %d · %.2f ms · debt %.2f s" % [playback.tick,playback.tick_ms,maxf(0,playback.backlog-.1)]
    if playback.source.terrain.environment.get("weather","clear")!="clear":hud.status.text+=" | Weather: "+str(playback.source.terrain.environment.weather).capitalize()
    if load_error!="":hud.status.text=load_error
    hud.play_button.text="Pause [Space]" if playback.playing else "Play [Space]"
    hud.follow_button.text="Following [C]" if (flat_view.follow_id if view_2d else rig.follow_id)>=0 else "Follow [C]"
    hud.overhead_button.disabled=view_2d;hud.projection_button.disabled=view_2d
    hud.projection_button.text="Orthographic [P]" if rig.perspective else "Perspective [P]"
    hud.camera_status.text="WASD pan · Q/E yaw · Alt+middle orbit · Wheel moves closer/further | %.0f° · distance %.0f m · %s %s" % [rad_to_deg(rig.pitch),rig.view_distance(),"PERSP" if rig.perspective else "ORTHO","FOLLOW" if rig.follow_id>=0 else "OVERHEAD" if rig.overhead else "FREE"]
    if view_2d:hud.camera_status.text="2D · WASD pan · Middle drag · Wheel zoom · Home: fit · F: focus · C: follow · 3D view: return to the same battle"
    if is_live:
        hud.deployment_controls(playback.backend.IsDeployment())
        hud.clock_label.text="Live %.1f s · %.0f×" % [playback.time,playback.speed]
        var selected=frame.units.get(units.selected)
        var target: Variant=frame.units.get(selected.target) if selected!=null else null
        hud.update_live_commands(playback.formations.get(units.selected,[]),selected!=null and selected.transition_left>0,selected!=null and selected.info.army==0 and selected.effective and playback.result=="",playback.playing,selected!=null and selected.combat_capable,selected!=null and selected.info.category=="cavalry" and playback.cavalry_enabled,target!=null and target.active and target.state=="routing")
        if playback.backend.IsDeployment():
            for key in hud.order_buttons:
                hud.order_buttons[key].disabled=key not in ["line","column","skirmish"] or selected==null or key not in playback.formations.get(units.selected,[])
        if playback.backend.IsDeployment():hud.play_button.text="Start battle [Space]"
        elif playback.result!="":hud.play_button.text="Finished · Campaign results" if playback.backend.IsCampaign() else "Finished · Reset [R]"
    else:
        hud.deployment_controls(false)
        hud.clock_label.text="%.1f / %.1f s %s" % [playback.time,playback.source.times[-1],frame.result]
        hud.updating=true;hud.timeline.value=playback.time;hud.updating=false
    var text: String="Recorded outcomes · camera uses real time"
    for event in playback.events:
        if event.message!="":text=event.message
    if is_live:
        if playback.backend.IsDeployment():text="DEPLOYMENT · Click either army · Right click: place · Rotate selected / L J K: formation · AI: commander abilities · Start battle when ready"
        elif playback.result!="":text="Battle complete: "+playback.result+" · "+playback.completion_rule+" · R to reset"
        elif order_notice_left>0:text=order_notice
        elif effects.debug_enabled:
            var summary: Array=[]
            for p in playback.following.shots.values():
                if summary.size()>=6:break
                summary.append("#%d E %.2f b%d" % [p.id,p.energy,p.bounces])
            text="Ballistics debug · %d active · " % playback.following.shots.size()+", ".join(summary)
        elif playback.events.is_empty():text="Right click: attack/move · B: charge · U: pursue · X: disengage · G: reform · Morale/routing active" if playback.morale_enabled else "Right click enemy: attack · ground: move · H: hold/fire · V: advance · No morale, cavalry combat or artillery fire" if playback.combat_enabled else "Movement sandbox · Right click: move · L/J/K: formation · H: hold · .: step paused"
    hud.configure_ai(is_live and playback.ai_enabled if is_live else false,playback.tick==0 and not playback.backend.IsCampaign() if is_live else false,frame.units.get(units.selected),playback.backend if is_live else null)
    if is_live:playback.rules["simulation_time"]=playback.time
    if order_preview.active:
        text="Release right mouse: %s · (%.1f, %.1f) m · facing %.0f°" % ["place formation" if playback.backend.IsDeployment() else "move",order_preview.destination.x,order_preview.destination.y,fposmod(rad_to_deg(order_preview.facing),360)] if order_preview.valid else "Invalid placement: "+order_preview.reason
    hud.notices.text=text;hud.inspect_unit(frame.units.get(units.selected),frame.units,playback.rules if is_live else {})
func _process(delta: float) -> void:
    var now:=Time.get_ticks_usec();var wall: float=(now-last_process)/1000.0 if last_process else 0;last_process=now
    if playback==null:return
    if is_live and playback.result!="" and not report_shown:
        if playback.backend.IsCampaign():playback.backend.CompleteCampaign()
        report_shown=true;action("results")
    # Godot can cap, smooth or scale _process delta under load. Authority must
    # retain actual elapsed time instead. Explicit calls with processing disabled
    # remain a deterministic stepping interface for tools/tests.
    var real_delta: float=wall/1000.0 if is_processing() and wall>0 else delta
    order_notice_left=maxf(0,order_notice_left-delta)
    var start:=Time.get_ticks_usec()
    if not playback.advance(real_delta if is_live else delta):load_error=playback.source.error
    rig.navigation_enabled=not view_2d and not hud.blocked()
    flat_view.navigation_enabled=view_2d and not hud.blocked()
    var move:=Vector2.ZERO;var turn:=0.0;var fast:=false
    if not hud.blocked():
        move=Input.get_vector("camera_left","camera_right","camera_forward","camera_backward")
        turn=Input.get_action_strength("camera_yaw_left")-Input.get_action_strength("camera_yaw_right");fast=Input.is_action_pressed("camera_fast")
    # Compute the follow point from the current interpolated recording pose.
    var follow: Variant=null
    if playback.current.units.has(rig.follow_id) and playback.current.units[rig.follow_id].active:
        var u: Object=playback.current.units[rig.follow_id]
        follow=World.point_between(u,playback.following.units.get(rig.follow_id),playback.alpha)
    if view_2d:flat_view.advance(real_delta,move,fast)
    else:rig.advance(real_delta,move,turn,fast,follow)
    refresh_frame()
    update_ms=(Time.get_ticks_usec()-start)/1000.0
    ui_elapsed+=delta
    if ui_elapsed>=.1:refresh_ui();ui_elapsed=0
    if screenshot_path!="" and not screenshot_written:screenshot_written=true;save_screenshot.call_deferred()
    if benchmark_frames>0:
        if warmup>0:warmup-=1
        else:
            timings.append(wall);updates.append(update_ms)
            if timings.size()>=benchmark_frames:finish_benchmark()
func _input(event: InputEvent) -> void:
    if event is InputEventKey:_handle_key(event)
    if event is InputEventMouseButton and not event.pressed and view_2d:
        if event.button_index==MOUSE_BUTTON_MIDDLE:flat_view.dragging=false
        if event.button_index==MOUSE_BUTTON_RIGHT and flat_view.secondary_down and (hud.blocked() or not viewport.get_parent().get_global_rect().has_point(event.position)):flat_view.cancel_secondary()
    if event is InputEventMouseButton and event.button_index==MOUSE_BUTTON_RIGHT and not event.pressed and rig!=null and rig.secondary_down:
        if hud.blocked() or not viewport.get_parent().get_global_rect().has_point(event.position):rig.cancel_secondary()
    if event is InputEventMouseButton and not event.pressed and event.is_action("camera_drag") and rig!=null:rig.end_drag()
func _notification(what: int) -> void:
    if what==NOTIFICATION_WM_WINDOW_FOCUS_OUT and rig!=null:rig.end_drag();rig.cancel_secondary();flat_view.dragging=false;flat_view.cancel_secondary()
func _handle_key(event: InputEvent) -> void:
    if hud==null or hud.blocked() or not event.is_pressed() or event.is_echo():return
    for pair in [["camera_fit","fit"],["camera_focus","focus"],["camera_follow","follow"],["camera_overhead","overhead"],["camera_projection","projection"]]:
        if event.is_action_pressed(pair[0]):action(pair[1]);return
    if event is InputEventKey:
        if is_live:
            if event.keycode==KEY_F8:effects.debug_enabled=not effects.debug_enabled;refresh_frame();get_viewport().set_input_as_handled();return
            var live_keys: Dictionary={KEY_L:"line",KEY_J:"column",KEY_K:"skirmish",KEY_H:"hold",KEY_V:"advance",KEY_PERIOD:"step",KEY_B:"charge",KEY_U:"pursue",KEY_X:"disengage",KEY_G:"reform",KEY_Y:"cease",KEY_I:"fire",KEY_O:"skirmish_order"}
            if live_keys.has(event.keycode):action("live:"+live_keys[event.keycode]);return
        if event.keycode==KEY_SPACE:action("pause")
        elif event.keycode==KEY_R:action("restart")
        elif event.keycode==KEY_TAB and is_live:action("results")
        elif event.keycode==KEY_F5:action("restart")
        elif event.keycode==KEY_F6 and is_live:action("rematch")
        elif event.keycode==KEY_F7:action("setup")
        elif event.keycode==KEY_ESCAPE:rig.cancel_secondary();flat_view.cancel_secondary();units.selected=-1;rig.follow_id=-1;flat_view.follow_id=-1;refresh_frame();refresh_ui()
        elif event.keycode in [KEY_1,KEY_2,KEY_3,KEY_4]:
            var choices: Dictionary={KEY_1:1.,KEY_2:2.,KEY_3:4.,KEY_4:10. if is_live else 4.}
            var speed: float=choices[event.keycode];action("speed:"+str(speed));hud.speeds.select({1.:2,2.:3,4.:4,10.:5}[speed])
func save_screenshot() -> void:
    await RenderingServer.frame_post_draw
    if DisplayServer.get_name()!="headless":get_viewport().get_texture().get_image().save_png(screenshot_path)
func stats(values: Array) -> Dictionary:
    values.sort();var total:=0.0
    for v in values:total+=v
    return {"mean_ms":total/values.size(),"median_ms":values[values.size()/2],"p95_ms":values[mini(values.size()-1,int(values.size()*.95))]}
func finish_benchmark() -> void:
    benchmark_frames=0
    var result: Dictionary={"viewer":"3d","source":"live-csharp" if is_live else "recording","mode":DisplayServer.get_name(),"godot":Engine.get_version_info().string,"units":playback.current.units.size(),"frames":timings.size(),"frame":stats(timings),"presentation_cpu":stats(updates),"load_ms":load_ms,"terrain_build_ms":terrain_view.build_ms,"terrain_vertices":surface.heights.size(),"terrain_builds":terrain_view.builds,"trees":forests.count,"visible_figures":units.visible_figures,"figures_per_regiment":presentation.figures_per_regiment,"projection":"perspective" if rig.perspective else "orthographic","shadows":presentation.shadows,"snapshot_cache":playback.source.frame_cache.size()}
    if is_live:
        result["simulation_tick"]=playback.tick;result["last_tick_ms"]=playback.tick_ms;result["retained_debt_seconds"]=playback.backlog
        result["combat_metrics"]=playback.backend.GetMetrics();result["combat_scenario"]=live_scenario
    print(JSON.stringify(result))
    if benchmark_output!="":
        var file:=FileAccess.open(benchmark_output,FileAccess.WRITE)
        if file!=null:file.store_string(JSON.stringify(result,"  ")+"\n")
    get_tree().quit()
