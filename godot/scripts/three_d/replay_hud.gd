extends CanvasLayer
## Existing replay controls/inspection pattern, separated from 3D world input.
signal action_requested(action: String)
signal recording_selected(path: String)
signal seek_requested(time: float)
const Setup=preload("res://scripts/three_d/battle_setup.gd")
const Results=preload("res://scripts/three_d/battle_results.gd")
var setup_dialog: Setup
var results_dialog: Results
var deploy_button: Button
var deploy_reset: Button
var deploy_facing: Button
var setup_save: Button
var results_button: Button
var upgrades_box: VBoxContainer
var upgrade_options: Dictionary={}
var upgrade_apply: Button
var top_panel: PanelContainer
var status: Label
var inspector: Label
var notices: Label
var clock_label: Label
var camera_status: Label
var play_button: Button
var overhead_button: Button
var follow_button: Button
var view_button: Button
var projection_button: Button
var timeline: HSlider
var speeds: OptionButton
var dialog: FileDialog
var settings_dialog: AcceptDialog
var historical_option: OptionButton
var historical_apply: Button
var historical_details: Label
var army_commander_options: Array=[]
var crossing_choice: OptionButton
var ai_dialog: AcceptDialog
var ai_button: Button
var army_options: Array=[]
var personality_option: OptionButton
var specialty_option: OptionButton
var reroll_button: Button
var assign_button: Button
var autonomy_button: Button
var setup_label: Label
var ai_selected: int=-1
var ai_signature: String=""
var updating: bool = false
var live_mode: bool = false
var mode_selector: OptionButton
var live_orders: HBoxContainer
var open_button: Button
var scenario_selector: OptionButton
var combat_mode: bool=false
var dynamics_mode: bool=false
var cavalry_orders: HBoxContainer
var side_panel: PanelContainer
var bottom_panel: PanelContainer
var scenario_choices: Array=SCENARIOS.duplicate(true)
var order_buttons: Dictionary={}
const SCENARIOS := [["Infantry Duel","infantry-duel"],["Ridge Defence","ridge-defence"],["Forest Engagement","forest-engagement"],["Flank Attack","flank-attack"],["Firing Lanes","friendly-obstruction"],["Combined Arms","combined"],["Movement Sandbox","movement"],["Terrain March","terrain-march"]]
const LIVE_HINT := "LIVE C# SIMULATION\n\nLeft click: select Blue\nRight click enemy: attack\nRight click ground: move\nHold right + drag: set facing\nV: advance and engage\nH: hold and fire\nL/J/K: line/column/loose\n.: single tick while paused\nSpace: pause · R: reset\n1/2/3/4: 1×/2×/4×/10×\n\nUse the scenario selector for terrain, firing lanes and melee tests.\n\nMorale/routing, cavalry combat, artillery fire and tactical AI are not ported.\n\nCamera: WASD, Q/E, middle drag, Alt+middle, wheel, Home/F/C/T/P."
const DYNAMICS_HINT := "LIVE C# BATTLE\n\nLeft click: select Blue\nRight click enemy: attack\nRight click ground: move\nHold right + drag: set facing\nB: charge current enemy\nU: pursue routing target\nX: disengage\nG: reform (hold/recover)\nH: hold · V: advance\nL/J/K: formations\nSpace: pause · .: single tick\nR: reset · 1/2/3/4: speeds\n\nRouting regiments flee danger. Orders unlock after rallying.\n\nThe scenario selector includes morale cascades, prepared/flank charges, pursuit and rallying.\n\nY: hold fire · I: resume fire · O: skirmish stance.\nAI scenarios add named officers and army objectives. Use the AI button for setup and autonomy. Other scenarios retain earlier milestone rules.\n\nRoute: choose a bridge/ford or Auto. F8: environment and combat debug. Narrow bridges require a column.\n\nCamera controls are unchanged."
const HINT := "REGIMENT INSPECTION\n\nClick a formation or its flag.\n\nWASD: pan\nQ/E: rotate\nShift: fast movement\nMiddle drag: grab ground\nAlt + middle: orbit/tilt\nWheel: zoom to cursor\n\nHome: overview\nF: focus selected\nC: follow selected\nT: tactical overhead\nP: projection\n\nSpace: pause replay\nR: restart replay\n1/2/4: replay speed"
func panel(root: Control,rect: Rect2,anchors: Vector4) -> PanelContainer:
    var result := PanelContainer.new();root.add_child(result)
    result.anchor_left=anchors.x;result.anchor_top=anchors.y;result.anchor_right=anchors.z;result.anchor_bottom=anchors.w
    result.offset_left=rect.position.x;result.offset_top=rect.position.y;result.offset_right=rect.end.x;result.offset_bottom=rect.end.y
    var style := StyleBoxFlat.new();style.bg_color=Color(.055,.08,.07,.97)
    style.content_margin_left=10;style.content_margin_right=10;style.content_margin_top=6;style.content_margin_bottom=6
    result.add_theme_stylebox_override("panel",style);return result
func button(label: String,key: String,row: Container) -> Button:
    var b:=Button.new();b.text=label;b.focus_mode=Control.FOCUS_NONE;b.pressed.connect(func():action_requested.emit(key));row.add_child(b);return b
func _ready() -> void:
    var root:=Control.new();add_child(root);root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);root.mouse_filter=Control.MOUSE_FILTER_IGNORE
    var top:=panel(root,Rect2(10,8,-20,146),Vector4(0,0,1,0));top_panel=top;var box:=VBoxContainer.new();top.add_child(box)
    var row:=HBoxContainer.new();box.add_child(row)
    mode_selector=OptionButton.new();mode_selector.focus_mode=Control.FOCUS_NONE;mode_selector.add_item("Replay Mode");mode_selector.add_item("Live (C#)");row.add_child(mode_selector)
    mode_selector.item_selected.connect(func(i):action_requested.emit("mode:live" if i==1 else "mode:replay"))
    open_button=button("Open recording","open",row);open_button.pressed.connect(func():dialog.popup_centered_ratio(.8))
    scenario_selector=OptionButton.new();scenario_selector.focus_mode=Control.FOCUS_NONE;scenario_selector.visible=false;scenario_selector.fit_to_longest_item=false;scenario_selector.custom_minimum_size.x=145;row.add_child(scenario_selector)
    scenario_selector.clip_text=true;scenario_selector.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
    for spec in SCENARIOS:scenario_selector.add_item(spec[0])
    scenario_selector.item_selected.connect(func(i):action_requested.emit("scenario:"+scenario_choices[i][1]))
    play_button=button("Pause [Space]","pause",row);button("Restart [R]","restart",row)
    speeds=OptionButton.new();speeds.focus_mode=Control.FOCUS_NONE
    for speed in [.25,.5,1.0,2.0,4.0,10.0]:speeds.add_item(str(speed)+"×")
    speeds.select(2);speeds.item_selected.connect(func(i):action_requested.emit("speed:"+str([.25,.5,1.,2.,4.,10.][i])));row.add_child(speeds)
    button("Camera settings","settings",row).pressed.connect(func():settings_dialog.popup_centered(Vector2i(600,620)))
    ai_button=button("AI","ai_setup",row);ai_button.pressed.connect(func():ai_dialog.popup_centered(Vector2i(580,460)))
    var controls:=HBoxContainer.new();box.add_child(controls)
    button("Overview [Home]","fit",controls);button("Focus [F]","focus",controls)
    follow_button=button("Follow [C]","follow",controls);overhead_button=button("Overhead [T]","overhead",controls)
    projection_button=button("Perspective [P]","projection",controls);view_button=button("2D view","2d",controls)
    crossing_choice=OptionButton.new();crossing_choice.focus_mode=Control.FOCUS_NONE;crossing_choice.fit_to_longest_item=false;crossing_choice.clip_text=true;crossing_choice.custom_minimum_size.x=160;crossing_choice.visible=false;controls.add_child(crossing_choice)
    crossing_choice.tooltip_text="Choose the crossing used by the next right-click movement order. Auto selects a distance-based compatible route."
    crossing_choice.item_selected.connect(func(i):action_requested.emit("route:"+str(crossing_choice.get_item_metadata(i))))
    var flow:=HFlowContainer.new();box.add_child(flow)
    button("Menu","menu",flow);button("Custom battle","setup",flow)
    results_button=button("Battle results [Tab]","results",flow)
    deploy_button=button("Start battle","deploy:start",flow)
    deploy_reset=button("Reset positions","deploy:reset",flow)
    deploy_facing=button("Rotate selected 15°","deploy:rotate",flow)
    setup_save=button("Save setup","deploy:save",flow)
    for b in [deploy_button,deploy_reset,deploy_facing,setup_save]:b.visible=false
    status=Label.new();status.add_theme_font_size_override("font_size",13);status.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS;box.add_child(status)
    camera_status=Label.new();camera_status.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS;camera_status.add_theme_font_size_override("font_size",12);box.add_child(camera_status)
    var side:=panel(root,Rect2(-298,162,288,-258),Vector4(1,0,1,1));side_panel=side;var scroll:=ScrollContainer.new();side.add_child(scroll)
    inspector=Label.new();inspector.custom_minimum_size.x=258;inspector.size_flags_horizontal=Control.SIZE_EXPAND_FILL;inspector.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;inspector.text=HINT;scroll.add_child(inspector)
    var bottom:=panel(root,Rect2(10,-86,-20,76),Vector4(0,1,1,1));bottom_panel=bottom;var column:=VBoxContainer.new();bottom.add_child(column)
    var strip:=HBoxContainer.new();column.add_child(strip)
    clock_label=Label.new();clock_label.custom_minimum_size.x=200;strip.add_child(clock_label)
    timeline=HSlider.new();timeline.focus_mode=Control.FOCUS_NONE;timeline.size_flags_horizontal=Control.SIZE_EXPAND_FILL;timeline.step=.001;strip.add_child(timeline)
    timeline.value_changed.connect(func(t):
        if not updating:seek_requested.emit(t))
    live_orders=HBoxContainer.new();live_orders.visible=false;strip.add_child(live_orders)
    for spec in [["Line [L]","line"],["Column [J]","column"],["Loose [K]","skirmish"],["Hold [H]","hold"],["Advance [V]","advance"],["Tick [.]","step"]]:
        order_buttons[spec[1]]=button(spec[0],"live:"+spec[1],live_orders)
    cavalry_orders=HBoxContainer.new();cavalry_orders.visible=false;column.add_child(cavalry_orders)
    for spec in [["Charge [B]","charge"],["Pursue [U]","pursue"],["Disengage [X]","disengage"],["Reform [G]","reform"],["Cease [Y]","cease"],["Fire [I]","fire"],["Skirmish [O]","skirmish_order"]]:
        order_buttons[spec[1]]=button(spec[0],"live:"+spec[1],cavalry_orders)
        order_buttons[spec[1]].add_theme_font_size_override("font_size",13)
    order_buttons.charge.tooltip_text="Approach the current enemy, align and accelerate when eligible."
    order_buttons.pursue.tooltip_text="Pursue the current routing target; stop when it recovers."
    order_buttons.reform.tooltip_text="Hold position for ordinary recovery. Does not instantly rally or reset charge locks."
    notices=Label.new();notices.add_theme_font_size_override("font_size",13);notices.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS;column.add_child(notices)
    dialog=FileDialog.new();dialog.title="Open battle metadata.json";dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.filters=PackedStringArray(["*.json ; Battle recording metadata"])
    dialog.current_dir=ProjectSettings.globalize_path("res://recordings");dialog.file_selected.connect(func(path):recording_selected.emit(path));root.add_child(dialog)
    settings_dialog=AcceptDialog.new();settings_dialog.title="Tactical camera — live settings";root.add_child(settings_dialog)
    ai_dialog=AcceptDialog.new();ai_dialog.title="Army objectives and selected commander";root.add_child(ai_dialog)
    var setup_scroll:=ScrollContainer.new();setup_scroll.custom_minimum_size=Vector2(570,500);ai_dialog.add_child(setup_scroll)
    var setup:=VBoxContainer.new();setup.size_flags_horizontal=Control.SIZE_EXPAND_FILL;setup_scroll.add_child(setup)
    setup_label=Label.new();setup_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;setup_label.custom_minimum_size.x=530;setup.add_child(setup_label)
    for army in [0,1]:
        var line:=HBoxContainer.new();setup.add_child(line);var label:=Label.new();label.text="Blue army" if army==0 else "Red army";label.custom_minimum_size.x=110;line.add_child(label)
        var option:=OptionButton.new();line.add_child(option);army_options.append(option)
        for value in ["manual","balanced","all_out_attack","hold_the_line","skirmish"]:option.add_item(value)
        option.item_selected.connect(func(i):action_requested.emit("army:%d:%s" % [army,option.get_item_text(i)]))
    for army in [0,1]:
        var leader_line:=HBoxContainer.new();setup.add_child(leader_line)
        var caption:=Label.new();caption.text=("Blue" if army==0 else "Red")+" army commander";leader_line.add_child(caption)
        var leaders:=OptionButton.new();leader_line.add_child(leaders);army_commander_options.append(leaders)
        leaders.item_selected.connect(func(i):action_requested.emit("army_commander:%d:%s" % [army,str(leaders.get_item_metadata(i))]))
    historical_option=OptionButton.new();setup.add_child(historical_option)
    historical_option.item_selected.connect(func(i):historical_details.text=historical_option.get_item_tooltip(i))
    historical_details=Label.new();historical_details.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;historical_details.custom_minimum_size.x=510;setup.add_child(historical_details)
    historical_apply=button("Assign historical officer to selected regiment","historical:apply",setup)
    historical_apply.pressed.connect(func():
        if historical_option.selected>=0:action_requested.emit("historical:"+str(historical_option.get_item_metadata(historical_option.selected))))
    personality_option=OptionButton.new();setup.add_child(personality_option)
    specialty_option=OptionButton.new();setup.add_child(specialty_option)
    reroll_button=button("Reroll selected commander (before first tick)","commander:reroll",setup)
    assign_button=button("Assign selected personality and specialization","commander:apply",setup)
    assign_button.pressed.connect(func():
        if personality_option.item_count>0 and specialty_option.item_count>0:action_requested.emit("commander:set:"+personality_option.get_item_text(personality_option.selected)+":"+specialty_option.get_item_text(specialty_option.selected)))
    var upgrade_label:=Label.new();upgrade_label.text="Acquired commander abilities (up to 3; sandbox setup only)";setup.add_child(upgrade_label)
    upgrades_box=VBoxContainer.new();setup.add_child(upgrades_box)
    upgrade_apply=button("Apply abilities","commander:upgrades",setup)
    upgrade_apply.pressed.connect(func():
        var keys: Array=[]
        for id in upgrade_options:
            if upgrade_options[id].button_pressed:keys.append(id)
        action_requested.emit("upgrades:"+JSON.stringify(keys)))
    setup_dialog=Setup.new();root.add_child(setup_dialog)
    setup_dialog.configuration_requested.connect(func(json):action_requested.emit("custom:"+json))
    results_dialog=Results.new();root.add_child(results_dialog);results_dialog.action_requested.connect(func(key):action_requested.emit(key))
    autonomy_button=button("Selected Blue regiment: Autonomous","live:auto",setup)
    button("Selected Blue regiment: Hold (player priority)","live:ordered",setup)
func blocked() -> bool:
    var focus:=get_viewport().gui_get_focus_owner()
    return setup_dialog.visible or results_dialog.visible or ai_dialog.visible or dialog.visible or settings_dialog.visible or speeds.get_popup().visible or mode_selector.get_popup().visible or scenario_selector.get_popup().visible or crossing_choice.get_popup().visible or focus is LineEdit or focus is TextEdit
func configure_camera(settings: Resource) -> void:
    var scroll:=ScrollContainer.new();scroll.custom_minimum_size=Vector2(560,520);settings_dialog.add_child(scroll)
    var box:=VBoxContainer.new();box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;scroll.add_child(box)
    var help:=Label.new();help.text="Drag ground with middle mouse; Alt+middle orbits the focus.\nZoom anchors the terrain under the cursor. P switches projection.\nManual pan/orbit cancels follow; zoom keeps following.\nRemap camera_* actions in Project Settings → Input Map.\nDefaults: resources/tactical_camera.tres";help.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(help)
    for spec in [["minimum_pitch","Minimum tilt above horizon (degrees)",0,30,1],["move_speed","Movement speed (m/s)",5,250,.5],["fast_multiplier","Shift multiplier",1,6,.1],["mouse_pan_sensitivity","Ground drag sensitivity",.2,2,.05],["mouse_rotation_sensitivity","Mouse orbit (rad/pixel)",.001,.015,.001],["zoom_sensitivity","Wheel zoom sensitivity",.04,.4,.01],["movement_smoothing","Movement responsiveness",2,25,.5],["rotation_smoothing","Rotation responsiveness",2,25,.5],["zoom_smoothing","Zoom responsiveness",2,25,.5],["focus_smoothing","Focus/follow responsiveness",2,25,.5]]:
        var row:=HBoxContainer.new();box.add_child(row)
        var label:=Label.new();label.text=spec[1];label.size_flags_horizontal=Control.SIZE_EXPAND_FILL;row.add_child(label)
        var input:=SpinBox.new();input.min_value=spec[2];input.max_value=spec[3];input.step=spec[4];input.value=settings.get(spec[0]);row.add_child(input)
        var key: String=spec[0];input.value_changed.connect(func(v):settings.set(key,v))
func bind_range(start: float,end: float) -> void:
    updating=true;timeline.min_value=start;timeline.max_value=end;timeline.value=start;updating=false
func set_live(value: bool,scenario: String="",combat: bool=false,dynamics: bool=false,choices: Array=[]) -> void:
    live_mode=value;mode_selector.select(1 if value else 0);timeline.visible=not value;live_orders.visible=value;open_button.visible=not value
    results_button.disabled=not value
    scenario_selector.visible=value;combat_mode=combat
    dynamics_mode=value and dynamics;cavalry_orders.visible=dynamics_mode
    bottom_panel.offset_top=-120 if dynamics_mode else -86
    side_panel.offset_bottom=-130 if dynamics_mode else -96
    if not choices.is_empty():
        scenario_choices.clear()
        for entry in choices:scenario_choices.append([entry.name,entry.id])
        scenario_choices.append(["Movement Sandbox","movement"]);scenario_choices.append(["Terrain March","terrain-march"])
        scenario_selector.clear()
        for spec in scenario_choices:scenario_selector.add_item(spec[0])
    if scenario=="custom" and not scenario_choices.any(func(entry):return entry[1]=="custom"):
        scenario_choices.append(["Custom Battle","custom"]);scenario_selector.add_item("Custom Battle")
    for i in scenario_choices.size():
        if scenario_choices[i][1]==scenario:scenario_selector.select(i)
func update_live_commands(allowed: Array, transition: bool, selected: bool, playing: bool,capable: bool=false,cavalry: bool=false,routing_target: bool=false) -> void:
    if not live_mode:return
    for formation in ["line","column","skirmish"]:order_buttons[formation].disabled=not selected or transition or formation not in allowed
    order_buttons.hold.disabled=not selected;order_buttons.step.disabled=playing
    order_buttons.advance.disabled=not selected or not capable or not combat_mode
    order_buttons.charge.disabled=not selected or not (cavalry or capable and "line" in allowed)
    order_buttons.pursue.disabled=not selected or not cavalry or not routing_target
    order_buttons.disengage.disabled=not selected;order_buttons.reform.disabled=not selected
    order_buttons.cease.disabled=not selected;order_buttons.fire.disabled=not selected;order_buttons.skirmish_order.disabled=not selected or transition or "skirmish" not in allowed
func inspect_unit(u: Object,units: Dictionary,rules: Dictionary={}) -> void:
    if u==null:inspector.text=DYNAMICS_HINT if dynamics_mode else LIVE_HINT if live_mode else HINT;return
    var officer: String=u.info.commander
    if live_mode and u.personality!="":officer+="\nPersonality: "+u.personality.capitalize()+"\nSpecialization: "+(u.specialization_name if u.specialization_name!="" else u.specialization.replace("_"," ").capitalize())+"\nAutonomy: "+u.autonomy+"\n"+u.intention
    var target:=str(u.target) if u.target>=0 else "None"
    if units.has(u.target):target+=" — "+units[u.target].info.name
    inspector.text="%s\n\n%s\nArmy %d · #%d\n\nCommander\n%s\n\nStrength: %d / %d\nMorale: %.1f\nCohesion: %.1f\n\nFormation: %s\nState: %s\nCombat: %s\nOrder: %s\nTarget: %s\n\nCharge: %s\nMomentum: %.0f%%\nSpeed: %.1f m/s\n\n%s" % [u.info.name,u.info.category+" / "+u.info.archetype,u.info.army,u.info.id,officer,u.strength,u.info.maximum,u.morale,u.cohesion,u.formation,u.state,u.combat_state,u.order,target,u.charge_state,u.momentum*100,u.speed,"Withdrawn/destroyed" if not u.active else ""]
    if live_mode:
        inspector.text="%s\n%s · Army %d · #%d\n\nCommander\n%s\n\nStrength: %d / %d\nCohesion: %.1f\nMorale: not simulated\n\nFormation: %s\nMovement: %s\nCombat: %s\nOrder: %s\nTarget: %s" % [u.info.name,u.info.faction if u.info.faction!="" else u.info.archetype,u.info.army,u.info.id,officer,u.strength,u.info.maximum,u.cohesion,u.formation,u.state,u.combat_state,u.order,target]
        if u.morale_simulated:
            inspector.text=inspector.text.replace("Morale: not simulated","Morale: %.1f · %s" % [u.morale,u.state]).replace("Movement: "+u.state,"Movement: "+u.movement_state)
            if u.state=="routing":inspector.text+="\nSafe to rally: %.1f / %.1f s" % [u.safe_time,rules.get("rally_safe_seconds",22.)]
            if u.state=="rallying":inspector.text+="\nRallying: needs morale 48 / cohesion 45"
            if not u.effective:inspector.text+="\nOrders unavailable until returned to duty."
            if u.withdrawn:inspector.text+="\nEscaped; survivors retained."
            if u.state_reason!="":inspector.text+="\n"+u.state_reason
        if u.combat_enabled and u.ranged_capable and u.info.category=="artillery":inspector.text+="\nWeapon: physical round shot (battery abilities below)\nRange: %.0f m (nominal)\nReload: %.1f s" % [u.weapon_range,u.reload_left]
        elif u.combat_enabled and u.ranged_capable:
            inspector.text+="\nRange: %.0f m (nominal)\nReload: %.1f s\nVisibility: %s (%.0f%%)\nLast volley lane: %.0f%%\nLast volley: %d shots · %.1f%% hit chance" % [u.weapon_range,u.reload_left,u.sight_state,u.sight_transmission*100,u.fire_lane*100,u.last_volley_shots,u.last_volley_probability*100]
        elif u.combat_enabled and u.cavalry_simulated and u.info.category=="cavalry":
            inspector.text+="\n\nCavalry: %s\nSpeed: %.2f / %.1f m/s charge cap\nMomentum: %.0f%% · last %.0f%%\nCharge run: %.1f m\nCharge target: %s\nPursuit target: %s\nCharge ready: %s · cooldown %.1f s\nLast impact: %s" % [u.charge_state,u.speed,u.info.charge_max_speed,u.momentum*100,u.last_momentum*100,u.charge_distance,str(u.cavalry_target) if u.cavalry_target>=0 else "None",str(u.pursuit) if u.pursuit>=0 else "None",str(u.charge_ready),u.charge_cooldown,u.charge_result]
        if u.personality!="":inspector.text+="\n\nPersonality: %s\nSpecialization: %s\nAutonomy: %s\nOrder owner: %s\nLast decision: %s\nNext decision: %.1f s\nLast threat ratio: %s · target score %s\n%s" % [u.personality,u.specialization_name if u.specialization_name!="" else u.specialization,u.autonomy,u.order_owner,u.intention,maxf(0,u.next_decision-rules.get("simulation_time",0)),("%.2f" % u.threat_ratio) if u.threat_ratio>0 else "n/a",("%.1f" % u.target_score) if u.info.category=="cavalry" or u.personality=="opportunistic" else "distance priority",u.commander_effects]
        if u.ai_enabled:inspector.text+="\nAssignment: %s\nNearby support: friendly %.0f / enemy %.0f\n%s" % [u.tactical_assignment if u.tactical_assignment!="" else "Army doctrine",u.friendly_support,u.enemy_support,u.position_reason]
        if u.army_plan!="":inspector.text+="\nArmy plan: %s\nRole: %s %s" % [u.army_plan,u.army_role,u.mounted_intent]
        if not u.upgrades.is_empty():inspector.text+="\n\nAcquired abilities\n"+u.upgrade_effects
        if u.infantry_charging or u.charge_result=="bayonet impact":inspector.text+="\nBayonet charge: %s\nMomentum %.0f%% · last %.0f%%\nRun %.1f m · ready %s · cooldown %.1f s" % ["charging" if u.infantry_charging else u.charge_result,u.momentum*100,u.last_momentum*100,u.charge_distance,str(u.charge_ready),u.charge_cooldown]
        if u.ability!="":inspector.text+="\n\n"+u.ability+"\nDrill: %.0f%% · Aimed fire: ×%.2f" % [u.drill*100,u.aimed]
        if u.info.category=="artillery" and u.battery_state!="not ported":inspector.text+="\nGuns: %d / %d\nBattery: %s\nLimber/setup: %.1f / %.1f s\nReload cycle: %.1f s\nHold fire: %s" % [u.guns,u.info.guns,u.battery_state,u.limber_left,u.setup_left,u.reload_seconds,str(u.hold_fire)]
        elif u.combat_enabled and not u.ranged_capable and not (u.cavalry_simulated and u.info.category=="cavalry"):inspector.text+=("\nCrew melee only; artillery fire not ported." if u.info.category=="artillery" else "\nMelee-only shock infantry: no ranged weapon.") if u.melee_capable else "\nOutgoing combat: disabled (not ported)"
        inspector.text+="\n\nSpeed: %.2f m/s\nFatigue: %.1f\nCongestion: %.0f%% (speed ×%.2f)\nTerrain speed: ×%.2f\nForest cover: %.0f%%\nSlope: %.3f" % [u.speed,u.fatigue,u.congestion*100,u.congestion_speed,u.terrain_speed,u.forest_cover*100,u.slope]
        if u.environment_state!="":inspector.text+="\n\nCrossing: "+u.environment_state
        if u.road!="":inspector.text+="\nRoad: "+u.road
        if u.destination!=null:inspector.text+="\nDestination: (%.1f, %.1f) m" % [u.destination.x,u.destination.y]
        if u.settling_goal!=null:inspector.text+="\nAdjusted stop: (%.1f, %.1f) m" % [u.settling_goal.x,u.settling_goal.y]
        if u.transition_left>0:inspector.text+="\nChanging to %s: %.1f s" % [u.next_formation,u.transition_left]
        inspector.text+="\n\nF8: range/target debug. AI button: army objectives and officer setup." if u.ai_enabled else "\n\nAI/commander effects disabled in this legacy scenario." if u.morale_simulated else "\n\nMorale/routing, cavalry combat, artillery fire and commander effects are not simulated." if u.combat_enabled else "\n\nMovement sandbox: combat and commander effects are inactive."

func configure_ai(enabled: bool,before: bool,u: Object,backend: Object) -> void:
    ai_button.visible=live_mode and enabled
    if not enabled:
        ai_dialog.hide();return
    if not ai_dialog.visible:return
    setup_label.text="Select a regiment to inspect its officer. Army objectives preserve explicit unit orders. Reroll/assignment unlock only before the first tick."
    var strategies: Array=["manual","balanced","all_out_attack","hold_the_line","skirmish"]
    for army in [0,1]:army_options[army].select(strategies.find(backend.GetArmyStrategy(army)))
    reroll_button.disabled=not before or u==null;assign_button.disabled=not before or u==null;personality_option.disabled=not before or u==null;specialty_option.disabled=not before or u==null
    autonomy_button.disabled=u==null or u.info.army!=0 or not u.effective
    for option in upgrade_options.values():option.disabled=not before
    upgrade_apply.disabled=not before or u==null
    for army in [0,1]:
        var choices: OptionButton=army_commander_options[army]
        if choices.item_count==0:
            choices.add_item("No army commander");choices.set_item_metadata(0,"")
            for leader in backend.GetArmyCommanders():
                choices.add_item(leader.name);choices.set_item_metadata(choices.item_count-1,leader.id);choices.set_item_tooltip(choices.item_count-1,leader.description)
        choices.disabled=not before
        var assigned: String=backend.GetArmyCommander(army)
        for i in choices.item_count:
            var id: String=choices.get_item_metadata(i)
            choices.set_item_disabled(i,id!="" and backend.GetArmyCommander(1-army)==id)
            if id==assigned:choices.select(i)
    historical_option.disabled=not before or u==null
    historical_apply.disabled=not before or u==null
    var authored: bool=u!=null and backend.GetHistoricalDefinition(u.info.id)!=""
    personality_option.visible=not authored;specialty_option.visible=not authored;assign_button.visible=not authored
    if u!=null and backend.GetHistoricalDefinition(u.info.id)!="":
        assign_button.disabled=true;personality_option.disabled=true;specialty_option.disabled=true
    var signature: String=(str(u.info.id)+u.personality+u.specialization+str(u.upgrades) if u!=null else "none")+backend.GetCommanderRosterKey()
    if signature==ai_signature:
        if personality_option.item_count>0 and specialty_option.item_count>0:setup_label.text=backend.GetCommanderDescription(personality_option.get_item_text(personality_option.selected),specialty_option.get_item_text(specialty_option.selected))+"\nArmy objectives retain pinned player orders. Officer edits lock after tick 0."
        return
    ai_signature=signature;personality_option.clear();specialty_option.clear()
    historical_option.clear();historical_details.text="Historical identities are unique across both armies. Compatible cross-faction assignments are allowed."
    if u!=null:
        for officer in backend.GetHistoricalCommanders(u.info.id):
            historical_option.add_item(officer.name);var i:=historical_option.item_count-1
            historical_option.set_item_metadata(i,officer.id);historical_option.set_item_disabled(i,officer.assigned)
            historical_option.set_item_tooltip(i,"%s · %s\n%s · %s\n%s" % [officer.faction,officer.role,officer.personality.capitalize(),officer.specialization,officer.description])
            if officer.id==backend.GetHistoricalDefinition(u.info.id):historical_option.select(i)
        if historical_option.selected>=0:historical_details.text=historical_option.get_item_tooltip(historical_option.selected)
    for child in upgrades_box.get_children():child.queue_free()
    upgrade_options.clear()
    if u!=null:
        for upgrade in backend.GetUpgrades(u.info.id):
            var check:=CheckBox.new();check.text=upgrade.name;check.tooltip_text=upgrade.description;check.button_pressed=upgrade.selected;check.disabled=not before;upgrades_box.add_child(check);upgrade_options[upgrade.id]=check
            var description:=Label.new();description.text=upgrade.description;description.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;description.custom_minimum_size.x=500;description.add_theme_font_size_override("font_size",12);upgrades_box.add_child(description)
        for value in backend.GetPersonalities():personality_option.add_item(value)
        for value in backend.GetSpecializations(u.info.id):specialty_option.add_item(value)
        for i in personality_option.item_count:
            if personality_option.get_item_text(i)==u.personality:personality_option.select(i)
        for i in specialty_option.item_count:
            if specialty_option.get_item_text(i)==u.specialization:specialty_option.select(i)

func deployment_controls(active: bool) -> void:
    for b in [deploy_button,deploy_reset,deploy_facing,setup_save]:b.visible=active
