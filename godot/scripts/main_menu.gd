extends Control
func _ready() -> void:
    if not OS.get_cmdline_user_args().is_empty():enter("viewer");return
    set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    var background:=ColorRect.new();background.color=Color("#172b27");background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(background)
    var center:=CenterContainer.new();center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(center)
    var box:=VBoxContainer.new();box.custom_minimum_size=Vector2(430,0);box.add_theme_constant_override("separation",16);center.add_child(box)
    var title:=Label.new();title.text="QUIBERON";title.add_theme_font_size_override("font_size",42);title.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;box.add_child(title)
    var subtitle:=Label.new();subtitle.text="Combined-arms tactics · Commonwealth campaign";subtitle.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;box.add_child(subtitle)
    for spec in [["New Campaign","campaign-new"],["Continue Campaign","campaign-continue"],["Custom Battle","custom"],["Live scenarios / AI battles","live"],["Python Battle Replay","replay"],["Quit","quit"]]:
        var b:=Button.new();b.text=spec[0];b.custom_minimum_size.y=48;box.add_child(b);var key: String=spec[1];b.pressed.connect(func():enter(key))
        if key=="campaign-continue":
            var state=load("res://scripts/simulation_adapter/CampaignBridge.cs").new();b.disabled=not state.HasSave();state.free()
func enter(mode: String) -> void:
    if mode.begins_with("campaign-"):
        var c=load("res://scripts/simulation_adapter/CampaignBridge.cs").new()
        if mode=="campaign-new":c.NewCampaign(str(Time.get_unix_time_from_system()).get_slice(".",0))
        else:
            if not c.LoadCampaign():c.free();return
        c.free();get_tree().change_scene_to_file.call_deferred("res://scenes/campaign.tscn");return
    if mode=="quit":get_tree().quit();return
    get_tree().root.set_meta("menu_mode",mode)
    get_tree().change_scene_to_file.call_deferred("res://scenes/battlefield_3d.tscn")
