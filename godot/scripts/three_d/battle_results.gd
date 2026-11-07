extends AcceptDialog
## A frozen native report using the existing battlefield/HUD; no campaign flow.
signal action_requested(action: String)
var report: Dictionary={}
var campaign_button: Button
var sandbox_buttons: Array[Button]=[]
var summary: Label
var table: Tree
var army_filter: OptionButton
var view_filter: OptionButton
var sort_filter: OptionButton
var page_label: Label
var detail: Label
var page: int=0
var file: FileDialog
const PAGE_SIZE:=12
const SORTS: Array=["inflicted","lost","remaining","salvos","charges","name"]
func _ready() -> void:
    title="Battle results";get_ok_button().text="Return to battlefield"
    var scroll:=ScrollContainer.new();scroll.custom_minimum_size=Vector2(680,430);add_child(scroll)
    var box:=VBoxContainer.new();box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;scroll.add_child(box)
    summary=Label.new();summary.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;summary.custom_minimum_size.x=680;box.add_child(summary)
    var row:=HBoxContainer.new();box.add_child(row)
    army_filter=OptionButton.new();row.add_child(army_filter)
    for value in ["Both armies","Blue","Red"]:army_filter.add_item(value)
    view_filter=OptionButton.new();row.add_child(view_filter)
    for value in ["Regiments","Archetypes"]:view_filter.add_item(value)
    sort_filter=OptionButton.new();row.add_child(sort_filter)
    for value in ["Caused","Lost","Remaining","Ranged salvos","Charges","Name"]:sort_filter.add_item(value)
    for option in [army_filter,view_filter,sort_filter]:option.item_selected.connect(func(_i):page=0;refresh())
    table=Tree.new();table.columns=8;table.hide_root=true;table.column_titles_visible=true;table.custom_minimum_size=Vector2(680,260);box.add_child(table)
    var titles: Array=["Regiment / archetype","Army","Start","Left","Lost","Caused","Salvos","Status"]
    for i in titles.size():table.set_column_title(i,titles[i]);table.set_column_expand(i,i==0);table.set_column_custom_minimum_width(i,185 if i==0 else 65)
    table.item_selected.connect(inspect_row)
    var pages:=HBoxContainer.new();box.add_child(pages)
    button(pages,"‹ Previous",func():page=maxi(0,page-1);refresh());page_label=Label.new();pages.add_child(page_label)
    button(pages,"Next ›",func():page+=1;refresh())
    detail=Label.new();detail.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;detail.custom_minimum_size.y=58;box.add_child(detail)
    var hint:=Label.new();hint.text="Lost counts casualties. Living routed and escaped troops remain survivors. Caused includes friendly fire.";hint.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(hint)
    var actions:=HBoxContainer.new();box.add_child(actions)
    for spec in [["Restart","restart"],["New seed","rematch"],["Edit setup","setup"],["Main menu","menu"]]:
        var key: String=spec[1];button(actions,spec[0],func():hide();action_requested.emit(key))
    button(actions,"Export report",func():file.popup_centered_ratio(.8))
    campaign_button=Button.new();campaign_button.text="Continue campaign";actions.add_child(campaign_button);campaign_button.visible=false;campaign_button.pressed.connect(func():hide();action_requested.emit("campaign:continue"))
    file=FileDialog.new();file.access=FileDialog.ACCESS_FILESYSTEM;file.file_mode=FileDialog.FILE_MODE_SAVE_FILE;file.current_file="battle-report.json";file.filters=PackedStringArray(["*.json ; Battle report"]);add_child(file)
    file.file_selected.connect(func(path):
        var out:=FileAccess.open(path,FileAccess.WRITE)
        if out==null:detail.text="Cannot save report: "+error_string(FileAccess.get_open_error())
        else:out.store_string(JSON.stringify(report,"  ")+"\n");detail.text="Report saved to "+path)
func button(parent: Node,text: String,callback: Callable) -> void:
    var b:=Button.new();b.text=text;parent.add_child(b);b.pressed.connect(callback)
    if text in ["Restart","New seed","Edit setup"]:sandbox_buttons.append(b)
func open_report(json: String) -> void:
    var parsed=JSON.parse_string(json)
    if not parsed is Dictionary:return
    report=parsed;page=0;refresh();popup_centered_clamped(Vector2i(1030,680),.95)
func rows() -> Array:
    var selected: Array=report.get("regiments" if view_filter.selected==0 else "archetypes",[]).duplicate(true)
    if army_filter.selected>0:selected=selected.filter(func(r):return int(r.army)==army_filter.selected-1)
    var key: String=SORTS[sort_filter.selected]
    selected.sort_custom(func(a,b):
        if a.get(key,0)==b.get(key,0):return a.army<b.army if a.army!=b.army else a.get("id",0)<b.get("id",0) if a.get("id",0)!=b.get("id",0) else a.name<b.name
        return a.get(key,0)<b.get(key,0) if key=="name" else a.get(key,0)>b.get(key,0))
    return selected
func refresh() -> void:
    if report.is_empty():return
    var result: String=report.get("result","") if report.get("result")!=null else ""
    summary.text=("Blue victory" if result=="army_0" else "Red victory" if result=="army_1" else "Draw" if result=="draw" else "Battle statistics")+" · %.1f s · seed %s · %.0f × %.0f m\n" % [report.duration,report.get("seedText",str(report.seed)),report.width,report.height]
    for army in report.armies:
        summary.text+="%s: %d started · %d survivors · %d lost · %d effective · %d destroyed · %d escaped · %d routs · %d rallies\n" % ["Blue" if army.army==0 else "Red",army.initial,army.remaining,army.lost,army.effective,army.destroyed,army.withdrawn,army.routs,army.rallies]
    summary.text+="Friendly-fire incidents %d · Artillery rounds %d · Charge impacts %d · Pursuit losses %d" % [report.metrics.friendlyFire,report.metrics.artilleryShots,report.metrics.charges,report.metrics.pursuitCasualties]
    var selected:=rows();var last:=maxi(0,(selected.size()-1)/PAGE_SIZE);page=mini(page,last)
    page_label.text="Page %d / %d · %d entries" % [page+1,last+1,selected.size()]
    table.clear();var root:=table.create_item()
    for i in range(page*PAGE_SIZE,mini(selected.size(),(page+1)*PAGE_SIZE)):
        var entry: Dictionary=selected[i];var item:=table.create_item(root);item.set_metadata(0,entry)
        var texts: Array=[entry.name,"Blue" if entry.army==0 else "Red",str(int(entry.initial)),str(int(entry.remaining)),str(int(entry.lost)),str(int(entry.inflicted)),str(int(entry.salvos)),entry.get("status",str(int(entry.get("regiments",1)))+" units")]
        for column in texts.size():item.set_text(column,texts[column]);item.set_tooltip_text(column,texts[column])
    detail.text="Select a row to inspect its commander, abilities, morale, cohesion and charge statistics."
func inspect_row() -> void:
    var item:=table.get_selected()
    if item==null:return
    var row: Dictionary=item.get_metadata(0)
    if row.has("commander"):
        var c: Dictionary=row.commander
        detail.text="%s %s · %s / %s\nAbilities: %s\nMorale %.1f · Cohesion %.1f · Charges %d · Routs %d · Rallies %d" % [c.rank,c.name,c.personality,c.specialization,", ".join(c.get("upgrades",[]) if c.get("upgrades")!=null else []),row.morale,row.cohesion,row.charges,row.routs,row.rallies]
    else:detail.text="%s · %d regiments · Charges %d · Routs %d · Rallies %d" % [row.name,row.regiments,row.charges,row.routs,row.rallies]
func _unhandled_key_input(event: InputEvent) -> void:
    if not visible or not event is InputEventKey or not event.pressed or event.echo:return
    if event.keycode==KEY_TAB:hide();get_viewport().set_input_as_handled()
    elif event.keycode in [KEY_F5,KEY_F6,KEY_F7]:
        hide();action_requested.emit({KEY_F5:"restart",KEY_F6:"rematch",KEY_F7:"setup"}[event.keycode]);get_viewport().set_input_as_handled()

func set_campaign(active: bool,finished: bool) -> void:
    campaign_button.visible=active;campaign_button.disabled=not finished
    for b in sandbox_buttons:b.visible=not active
