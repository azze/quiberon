extends Control
var bridge: Node
var box: VBoxContainer
var message: Label
var auto_player:=false
func _ready() -> void:
    bridge=load("res://scripts/simulation_adapter/CampaignBridge.cs").new();add_child(bridge)
    set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    var bg:=ColorRect.new();bg.color=Color("#172b27");bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
    var scroll:=ScrollContainer.new();scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);scroll.offset_left=36;scroll.offset_top=20;scroll.offset_right=-36;scroll.offset_bottom=-20;add_child(scroll)
    box=VBoxContainer.new();box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;box.add_theme_constant_override("separation",12);scroll.add_child(box)
    if get_tree().root.get_meta("campaign_load",false):
        get_tree().root.remove_meta("campaign_load");bridge.LoadCampaign()
    if not bridge.HasCampaign():bridge.NewCampaign("1796")
    refresh()
func label(text: String,size: int=18) -> Label:
    var l:=Label.new();l.text=text;l.add_theme_font_size_override("font_size",size);l.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(l);return l
func button(text: String,callback: Callable,parent: Node=null) -> Button:
    if parent==null:parent=box
    var b:=Button.new();b.text=text;b.custom_minimum_size.y=38;parent.add_child(b);b.pressed.connect(callback);return b
func perform(callback: Callable) -> void:
    if not callback.call():message.text=bridge.Error;return
    refresh()
func refresh() -> void:
    for child in box.get_children():box.remove_child(child);child.queue_free()
    var v=JSON.parse_string(bridge.GetView());var s: Dictionary=v.state
    label("THE DEFENCE OF THE COMMONWEALTH",30);label("Spring–Summer 1796 · Kościuszko’s army · Stage %d / 6" % s.stage)
    var progress: Array=[]
    for i in range(6):progress.append("●" if i<s.history.size() else "◉" if i==int(s.stage)-1 else "○")
    label("  ".join(progress),24)
    message=label("")
    var row:=HBoxContainer.new();box.add_child(row)
    label("Campaign seed: "+v.seedText)
    var seed_input:=LineEdit.new();seed_input.text=v.seedText;seed_input.placeholder_text="New run seed";seed_input.custom_minimum_size.x=160;row.add_child(seed_input)
    button("New run with seed",func():perform(func():return bridge.NewCampaign(seed_input.text)),row)
    button("Save campaign",func():perform(func():return bridge.SaveCampaign()),row)
    button("Main menu",func():get_tree().change_scene_to_file("res://scenes/main_menu.tscn"),row)
    if s.phase=="ended":
        label({"decisive":"Decisive Victory — The invasion collapses. The Commonwealth preserves its independence and territory.","negotiated":"Negotiated Victory — The Commonwealth survives. Heavy losses lead to a negotiated peace.","defeat":"Defeat — The invasion prevails. Surviving officers may escape into exile."}.get(s.ending,"Campaign ended"),26)
        label("Victories: %d · Recorded casualties: %d · Decisive victory requires final victory and at least %.0f%% entering roster strength." % [s.history.filter(func(h):return h.winner==0).size(),s.history.reduce(func(n,h):return n+h.lost,0),s.rules.decisiveSurvival*100])
        button("New campaign",func():perform(func():return bridge.NewCampaign("1796")));return
    if s.phase=="rewards":
        label("Victory — choose one reward",25)
        for r in s.rewards:
            if r.kind=="upgrade":
                label(r.label)
                for key in r.upgrades:
                    var d: Dictionary=v.upgrades.filter(func(d):return d.id==key)[0]
                    label(d.description)
                    button("Acquire "+d.name,func():perform(func():return bridge.Claim(r.id,key)))
            else:button(r.label,func():perform(func():return bridge.Claim(r.id,"")))
        return
    if s.phase=="event":
        var e: Dictionary=v.events.filter(func(e):return e.id==s.pendingEvent)[0];label(e.title,25);label(e.text)
        for choice in e.choices:
            label(choice.description)
            button(choice.label,func():perform(func():return bridge.ChooseEvent(choice.id)))
        return
    label(v.title+" · "+v.date,25);label(v.briefing);label("Objective: "+v.objective);label("Known enemy: "+v.knownEnemy)
    label("Weather: %s · Hills %d · Forests %d · Rivers %d · Crossings %d · Roads %d" % [v.weather,v.terrain.hills,v.terrain.forests,v.terrain.rivers,v.terrain.crossings,v.terrain.roads])
    label("Failure: loss of the objective, collapse of your army, or expiry of the mission deadline.")
    label("Army %d / %d · Victories replace %.0f%% of missing soldiers. Routed survivors remain; destroyed regiments leave their commanders in reserve." % [s.roster.size(),s.rules.capacity,s.rules.autoReplenish*100])
    for regiment in s.roster:
        var officer: Dictionary=s.commanders.filter(func(c):return c.id==regiment.commanderId)[0]
        var unit: Dictionary=v.units.filter(func(a):return a.id==regiment.archetype)[0]
        var signature: String=officer.specialization.replace("_"," ").capitalize()
        var historical: Array=v.historical.filter(func(h):return h.id==officer.get("definitionId",""))
        if not historical.is_empty():signature=historical[0].specializationName
        var upgrade_names: Array=[]
        for key in officer.get("upgrades",[]) if officer.get("upgrades")!=null else []:
            var named: Array=v.upgrades.filter(func(u):return u.id==key)
            upgrade_names.append(named[0].name if not named.is_empty() else key)
        label("%s · %s · %d / %d\n%s · %s · %s\nUpgrades: %s" % [regiment.name,regiment.faction,regiment.strength,regiment.maximum,officer.name,officer.personality.capitalize(),signature,", ".join(upgrade_names)])
        if not historical.is_empty():label(historical[0].description,16)
        var choices: Array=JSON.parse_string(bridge.CompatibleCommanders(regiment.id));var selector:=OptionButton.new();box.add_child(selector)
        for c in choices:selector.add_item(c.name+" · "+c.personality);selector.set_item_metadata(selector.item_count-1,c.id)
        for i in selector.item_count:
            if selector.get_item_metadata(i)==officer.id:selector.select(i)
        selector.item_selected.connect(func(index):perform(func():return bridge.Assign(regiment.id,selector.get_item_metadata(index))))
    var assigned: Array=s.roster.map(func(r):return r.commanderId)
    label("Reserve officers: "+", ".join(s.commanders.filter(func(c):return c.id not in assigned).map(func(c):return c.name)))
    var ai:=CheckBox.new();ai.text="Let both armies fight autonomously (development / spectator mode)";ai.button_pressed=auto_player;ai.toggled.connect(func(value):auto_player=value);box.add_child(ai)
    button("Briefing read — deploy for battle",func():
        if not bridge.Prepare(auto_player):message.text=bridge.Error;return
        get_tree().root.set_meta("menu_mode","campaign");get_tree().change_scene_to_file("res://scenes/battlefield_3d.tscn"))
