extends AcceptDialog
## Catalogue shared by both custom rosters. Selection never changes a live battle.
signal units_added(army: int, archetype: String, amount: int)
var catalogue: Array=[]
var army: int=0
var category: String="all"
var setup: Object
var choices: ItemList
var details: Label
var amount: SpinBox
var add_selected: Button
var search: LineEdit
var filters: Dictionary={}
var faction_filter: OptionButton
var filtered: Array=[]
func _ready() -> void:
    title="Add regiments";get_ok_button().text="Back to army"
    var panel:=VBoxContainer.new();panel.custom_minimum_size=Vector2(650,390);add_child(panel)
    var scroll:=ScrollContainer.new();scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL;panel.add_child(scroll)
    var box:=VBoxContainer.new();box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;scroll.add_child(box)
    var bar:=HBoxContainer.new();box.add_child(bar)
    for key in ["all","infantry","cavalry","artillery"]:
        var b:=Button.new();b.text=key.capitalize();b.toggle_mode=true;bar.add_child(b);filters[key]=b
        b.pressed.connect(func():set_filter(key))
    faction_filter=OptionButton.new();box.add_child(faction_filter)
    faction_filter.item_selected.connect(func(_i):refresh())
    search=LineEdit.new();search.placeholder_text="Search regiments or factions";box.add_child(search);search.text_changed.connect(func(_text):refresh())
    var content:=HBoxContainer.new();box.add_child(content)
    choices=ItemList.new();choices.custom_minimum_size=Vector2(300,260);choices.size_flags_horizontal=Control.SIZE_EXPAND_FILL;content.add_child(choices)
    choices.item_selected.connect(func(_i):show_details())
    details=Label.new();details.custom_minimum_size.x=260;details.size_flags_horizontal=Control.SIZE_EXPAND_FILL;details.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;content.add_child(details)
    var footer:=HBoxContainer.new();panel.add_child(footer)
    var label:=Label.new();label.text="Number to add";footer.add_child(label)
    amount=SpinBox.new();amount.min_value=1;amount.max_value=64;amount.step=1;footer.add_child(amount);amount.value_changed.connect(func(_v):show_details())
    add_selected=Button.new();add_selected.text="Add to army";footer.add_child(add_selected);add_selected.pressed.connect(confirm_add)
func open_picker(owner_setup: Object,side: int,definitions: Array) -> void:
    setup=owner_setup;army=side;catalogue=definitions;amount.value=1
    title=("Blue" if army==0 else "Red")+" army — add regiments"
    var old_faction:=faction_filter.get_item_text(faction_filter.selected) if faction_filter.item_count>0 else "All factions"
    faction_filter.clear();faction_filter.add_item("All factions")
    var factions: Array=[]
    for a in catalogue:
        if not a.faction in factions:factions.append(a.faction)
    factions.sort()
    for value in factions:faction_filter.add_item(value)
    for i in faction_filter.item_count:
        if faction_filter.get_item_text(i)==old_faction:faction_filter.select(i)
    set_filter(category);popup_centered_clamped(Vector2i(840,540),.95)
func set_filter(value: String) -> void:
    category=value
    for key in filters:filters[key].button_pressed=key==category
    refresh()
func refresh() -> void:
    var previous: String=filtered[choices.get_selected_items()[0]].id if not choices.get_selected_items().is_empty() else ""
    filtered=catalogue.filter(func(a):return (category=="all" or a.category==category) and (faction_filter.selected<=0 or a.faction==faction_filter.get_item_text(faction_filter.selected)) and (search.text.is_empty() or (a.name+" "+a.faction).to_lower().contains(search.text.to_lower())))
    choices.clear();var index:=0
    for a in filtered:
        choices.add_item(a.name)
        if a.id==previous:index=choices.item_count-1
    if not filtered.is_empty():choices.select(index)
    show_details()
func show_details() -> void:
    if setup==null:return
    var selected:=choices.get_selected_items();add_selected.disabled=selected.is_empty()
    if selected.is_empty():details.text="No matching regiments.";return
    var a: Dictionary=filtered[selected[0]];var existing:=int(setup.counts[army][a.id].value)
    var total: int=setup.roster_total(0)+setup.roster_total(1)
    var copies:=2 if setup.symmetric.button_pressed else 1
    var fits: bool=existing+int(amount.value)<=int(setup.per_type_input.value) and total+int(amount.value)*copies<=int(setup.total_input.value) and not (army==1 and setup.symmetric.button_pressed)
    add_selected.disabled=not fits
    var weapon: String="Range %.0f m · Reload %.1f s" % [a.range,a.reload] if a.range>0 else "Close combat; no ranged weapon"
    details.text="%s\n%s · %s\n\nStrength %d · Speed %.1f m/s\n%s\nFormations: %s\n\n%s\n\nIn this army: %d\nTotal regiments: %d / %d%s" % [a.name,a.faction,a.category.capitalize(),a.maximum,a.speed,weapon,", ".join(a.formations),a.ability,existing,total,int(setup.total_input.value),"\nSymmetric rosters: also adds to Red." if copies==2 else ""]
    if not fits:details.text+="\nCannot add: army locked or regiment limit reached."
func confirm_add() -> void:
    show_details()
    if add_selected.disabled:return
    units_added.emit(army,filtered[choices.get_selected_items()[0]].id,int(amount.value));hide()
