extends AcceptDialog
## Custom battle recipes only. No campaign state is created here.
signal configuration_requested(json: String)
const Picker=preload("res://scripts/three_d/unit_picker.gd")
var unit_picker: Picker
var catalogue: Array=[]
var add_buttons: Array=[]
var totals: Array=[]
var backend: Object
var data: Dictionary={}
var counts: Array=[{},{}]
var battle_name: LineEdit
var width_input: SpinBox
var height_input: SpinBox
var per_type_input: SpinBox
var total_input: SpinBox
var seed_strings: Dictionary={}
var seed_input: LineEdit
var terrain_seed: LineEdit
var commander_seed: LineEdit
var weather_choice: OptionButton
var terrain_choice: OptionButton
var symmetric: CheckBox
var strategies: Array=[]
var preset_choice: OptionButton
var message: Label
var files: FileDialog
var loading: bool=false
var syncing: bool=false
const TERRAINS: Array=["Open Field","Central Hill","Rolling Hills","Ridge Defence","Wooded Battlefield","Mixed Terrain"]
const STRATEGIES: Array=["manual","balanced","all_out_attack","hold_the_line","skirmish"]
func _ready() -> void:
    title="Custom Battle — armies and battlefield";size=Vector2i(960,690);get_ok_button().hide()
    var scroll:=ScrollContainer.new();scroll.custom_minimum_size=Vector2(720,550);add_child(scroll)
    var box:=VBoxContainer.new();box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;scroll.add_child(box)
    var header:=HBoxContainer.new();box.add_child(header)
    preset_choice=OptionButton.new();preset_choice.fit_to_longest_item=false;preset_choice.clip_text=true;preset_choice.custom_minimum_size.x=140;preset_choice.size_flags_horizontal=Control.SIZE_EXPAND_FILL;header.add_child(preset_choice)
    make_button(header,"Load preset",func():load_preset())
    make_button(header,"Load file",func():loading=true;files.file_mode=FileDialog.FILE_MODE_OPEN_FILE;files.popup_centered_ratio(.8))
    make_button(header,"Save file",func():loading=false;files.file_mode=FileDialog.FILE_MODE_SAVE_FILE;files.popup_centered_ratio(.8))
    battle_name=line(box,"Battle name")
    var dimensions:=HBoxContainer.new();box.add_child(dimensions)
    width_input=number(dimensions,"Width (m)",300,5000,1000);height_input=number(dimensions,"Height (m)",240,3000,600)
    var sizes:=OptionButton.new();dimensions.add_child(sizes)
    var options: Array=[["Medium",1000,600],["Small",600,400],["Large",1600,1000],["Huge",2400,1500],["Epic",3200,2000],["Vast",4800,3000]]
    for entry in options:sizes.add_item(entry[0])
    sizes.item_selected.connect(func(i):width_input.value=options[i][1];height_input.value=options[i][2])
    var limits:=HBoxContainer.new();box.add_child(limits)
    per_type_input=number(limits,"Maximum per archetype",1,64,12);total_input=number(limits,"Total regiment limit",2,256,48)
    var seeds:=HBoxContainer.new();box.add_child(seeds)
    seed_input=line(seeds,"Battle seed");commander_seed=line(seeds,"Officer seed");terrain_seed=line(seeds,"Terrain seed")
    var terrain_row:=HBoxContainer.new();box.add_child(terrain_row);label(terrain_row,"Terrain")
    terrain_choice=OptionButton.new();terrain_row.add_child(terrain_choice)
    for value in TERRAINS:terrain_choice.add_item(value)
    label(terrain_row,"Weather");weather_choice=OptionButton.new();terrain_row.add_child(weather_choice)
    for value in ["clear","rain","fog"]:weather_choice.add_item(value.capitalize())
    symmetric=CheckBox.new();symmetric.text="Symmetric rosters";terrain_row.add_child(symmetric)
    symmetric.toggled.connect(func(value):if not syncing:sync_red(value))
    var armies:=HBoxContainer.new();box.add_child(armies)
    for army in [0,1]:
        var column:=VBoxContainer.new();column.size_flags_horizontal=Control.SIZE_EXPAND_FILL;armies.add_child(column)
        label(column,"BLUE ARMY" if army==0 else "RED ARMY")
        var strategy:=OptionButton.new();column.add_child(strategy);strategies.append(strategy)
        for value in STRATEGIES:strategy.add_item(value)
        counts[army]["_column"]=column
        var total:=Label.new();column.add_child(total);totals.append(total)
        add_buttons.append(make_button(column,"+ Add units…",func():unit_picker.open_picker(self,army,catalogue)))
    unit_picker=Picker.new();add_child(unit_picker)
    unit_picker.units_added.connect(func(army,id,amount):counts[army][id].value+=amount)
    message=Label.new();message.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;message.custom_minimum_size.x=680;box.add_child(message)
    var help:=Label.new();help.text="Deploy positions both armies without advancing time. Officers and up to three compatible abilities can be edited on the battlefield before starting.";help.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(help)
    make_button(box,"Deploy armies →",func():
        var json:=recipe()
        if json!="":configuration_requested.emit(json))
    files=FileDialog.new();files.access=FileDialog.ACCESS_FILESYSTEM;files.filters=PackedStringArray(["*.json ; Battle configuration"]);files.current_file="custom-battle.json";add_child(files)
    files.file_selected.connect(file_selected)
func label(parent: Node,text: String) -> Label:
    var value:=Label.new();value.text=text;parent.add_child(value);return value
func line(parent: Node,text: String) -> LineEdit:
    var row:=HBoxContainer.new();parent.add_child(row);label(row,text)
    var input:=LineEdit.new();input.custom_minimum_size.x=105;input.size_flags_horizontal=Control.SIZE_EXPAND_FILL;row.add_child(input);return input
func number(parent: Node,text: String,minimum: float,maximum: float,value: float) -> SpinBox:
    var row:=HBoxContainer.new();parent.add_child(row);label(row,text)
    var input:=SpinBox.new();input.min_value=minimum;input.max_value=maximum;input.step=1;input.value=value;row.add_child(input);return input
func make_button(parent: Node,text: String,callback: Callable) -> Button:
    var b:=Button.new();b.text=text;parent.add_child(b);b.pressed.connect(callback);return b
func open_setup(native: Object,json: String="") -> void:
    backend=native
    if counts[0].size()==1:
        catalogue=backend.GetArchetypes()
        for army in [0,1]:
            for archetype in catalogue:
                var input:=number(counts[army]._column,archetype.name,0,64,0);counts[army][archetype.id]=input
                var caption: Label=input.get_parent().get_child(0);caption.custom_minimum_size.x=190;caption.size_flags_horizontal=Control.SIZE_EXPAND_FILL;caption.clip_text=true;caption.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS;caption.tooltip_text=archetype.name
                input.custom_minimum_size.x=85
                make_button(input.get_parent(),"−",func():input.value=maxf(0,input.value-1))
                input.value_changed.connect(func(_value):
                    if syncing:return
                    if army==0 and symmetric.button_pressed:sync_red(true)
                    refresh_rosters())
        for id in backend.GetBattlePresets():preset_choice.add_item(id.replace("_"," ").capitalize());preset_choice.set_item_metadata(preset_choice.item_count-1,id)
    populate(backend.GetDefaultConfiguration() if json=="" else json)
    popup_centered_clamped(Vector2i(960,690),.95)
func count_value(army: Dictionary,key: String) -> int:
    return int(army.get(key,0)) if key in ["infantry","cavalry","artillery"] else int(army.get("specialists",{}).get(key,0))
func populate(json: String) -> void:
    var parsed=JSON.parse_string(json)
    if not parsed is Dictionary:message.text="Invalid configuration JSON.";return
    data=parsed;syncing=true
    battle_name.text=str(data.get("name","Custom battle"));width_input.value=data.get("width",1000);height_input.value=data.get("height",600)
    seed_input.text=str(int(data.get("seed",17))) if data.get("seed")!=null else "17"
    commander_seed.text=str(int(data.get("commander_seed",1729))) if data.get("commander_seed")!=null else "1729"
    terrain_seed.text=str(int(data.get("terrain_seed",17))) if data.get("terrain_seed")!=null else "17"
    seed_strings=backend.GetConfigurationSeeds(json);seed_input.text=seed_strings.battle;commander_seed.text=seed_strings.commander;terrain_seed.text=seed_strings.terrain
    per_type_input.value=data.get("max_per_type",12);total_input.value=data.get("max_total",48)
    terrain_choice.select(maxi(0,TERRAINS.find(data.get("terrain_preset","Open Field"))))
    var env_data: Dictionary=data.terrain.get("environment",{}) if data.get("terrain")!=null and data.terrain.get("environment")!=null else {}
    var weather_data: Dictionary=env_data.get("weather",{}) if env_data.get("weather")!=null else {}
    var weather: String=weather_data.get("type","clear")
    weather_choice.select(maxi(0,["clear","rain","fog"].find(weather)))
    symmetric.button_pressed=data.get("symmetric",true)
    for army in [0,1]:
        var composition: Dictionary=data.get("blue" if army==0 else "red",{})
        for key in counts[army]:
            if key!="_column":counts[army][key].value=count_value(composition,key)
        var ai: Array=[]
        for value in data.get("ai_armies",[1]):ai.append(int(value))
        var doctrine: Array=data.get("ai_strategies",["balanced","balanced"])
        strategies[army].select(STRATEGIES.find(doctrine[army]) if army in ai else 0)
    syncing=false;sync_red(symmetric.button_pressed);message.text="Add units or adjust your roster, then deploy. Saved placements are retained while the roster and terrain are unchanged."
func sync_red(value: bool) -> void:
    for key in counts[1]:
        if key=="_column":continue
        counts[1][key].editable=not value
        if value:counts[1][key].value=counts[0][key].value
        for child in counts[1][key].get_parent().get_children():
            if child is Button:child.disabled=value
    if not catalogue.is_empty():refresh_rosters()
func roster_total(army: int) -> int:
    var total:=0
    for a in catalogue:total+=int(counts[army][a.id].value)
    return total
func refresh_rosters() -> void:
    for army in [0,1]:
        for a in catalogue:counts[army][a.id].get_parent().visible=counts[army][a.id].value>0
        totals[army].text="%d regiments" % roster_total(army)
        add_buttons[army].disabled=army==1 and symmetric.button_pressed
func recipe() -> String:
    if not seed_input.text.is_valid_int() or not commander_seed.text.is_valid_int() or not terrain_seed.text.is_valid_int():message.text="Seeds must be signed integers.";return ""
    var next: Dictionary=data.duplicate(true);var changed: bool=width_input.value!=data.get("width",1000) or height_input.value!=data.get("height",600)
    for army in [0,1]:
        var composition: Dictionary={"infantry":0,"cavalry":0,"artillery":0,"specialists":{}}
        for key in counts[army]:
            if key=="_column":continue
            var amount:=int(counts[army][key].value)
            if amount!=count_value(data.get("blue" if army==0 else "red",{}),key):changed=true
            if key in ["infantry","cavalry","artillery"]:composition[key]=amount
            elif amount>0:composition.specialists[key]=amount
        next["blue" if army==0 else "red"]=composition
    var terrain_changed: bool=width_input.value!=data.get("width",1000) or height_input.value!=data.get("height",600) or terrain_choice.get_item_text(terrain_choice.selected)!=data.get("terrain_preset","Open Field") or terrain_seed.text!=seed_strings.get("terrain","17")
    next.name=battle_name.text;next.width=width_input.value;next.height=height_input.value;next.seed=seed_input.text;next.commander_seed=commander_seed.text;next.terrain_seed=terrain_seed.text
    next.terrain_preset=terrain_choice.get_item_text(terrain_choice.selected);next.symmetric=symmetric.button_pressed
    next.max_per_type=int(per_type_input.value);next.max_total=int(total_input.value)
    next.ai_armies=[];next.ai_strategies=[]
    for army in [0,1]:
        var strategy: String=STRATEGIES[strategies[army].selected]
        if strategy!="manual":next.ai_armies.append(army)
        next.ai_strategies.append("balanced" if strategy=="manual" else strategy)
    if terrain_changed:next.terrain=null
    if terrain_changed or changed:next.placements=[]
    elif commander_seed.text!=seed_strings.get("commander","1729"):
        for placement in next.get("placements",[]):placement.commander=null
    var normalized: String=backend.NormalizeConfiguration(JSON.stringify(next))
    if normalized=="":message.text=backend.SetupError
    if normalized!="":normalized=backend.ConfigurationWeather(normalized,["clear","rain","fog"][weather_choice.selected])
    return normalized
func load_preset() -> void:
    if preset_choice.item_count>0:populate(backend.GetBattlePreset(preset_choice.get_item_metadata(preset_choice.selected)))
func file_selected(path: String) -> void:
    if loading:
        var f:=FileAccess.open(path,FileAccess.READ)
        if f==null:message.text="Cannot open file: "+error_string(FileAccess.get_open_error());return
        if f.get_length()>1000000:message.text="Configuration exceeds 1 MB.";return
        var normalized: String=backend.NormalizeConfiguration(f.get_as_text())
        if normalized=="":message.text=backend.SetupError;return
        populate(normalized);message.text="Loaded "+path
    else:
        var json:=recipe()
        if json=="":return
        var f:=FileAccess.open(path+".tmp",FileAccess.WRITE)
        if f==null:message.text="Cannot write file: "+error_string(FileAccess.get_open_error());return
        f.store_string(json+"\n");f.close()
        var err:=DirAccess.rename_absolute(path+".tmp",path)
        message.text="Saved "+path if err==OK else "Save failed: "+error_string(err)
