extends SceneTree
const Menu=preload("res://scripts/main_menu.gd")
var checks:=0
var failed:=false
func check(value: bool,message: String) -> void:
    checks+=1
    if not value:failed=true;push_error(message)
func _initialize() -> void:run.call_deferred()
func run() -> void:
    root.size=Vector2i(1280,800)
    var menu:=Menu.new();root.add_child(menu);current_scene=menu
    await process_frame
    check(menu.get_child_count()>0,"Main menu is constructed")
    menu.enter("custom")
    for i in 8:await process_frame
    var viewer: Node=current_scene
    check(viewer.has_method("start_live") and viewer.hud.setup_dialog.visible,"Main menu opens custom battle setup")
    check(not viewer.is_live,"Editing a recipe does not begin a battle")
    viewer.hud.setup_dialog.hide();viewer.action("menu")
    for i in 3:await process_frame
    check(current_scene is Menu,"Battlefield returns to the main menu")
    current_scene.enter("live")
    for i in 8:await process_frame
    check(current_scene.is_live and not current_scene.playback.playing,"Live menu opens a paused player-versus-AI battle")
    current_scene.action("menu")
    for i in 3:await process_frame
    current_scene.enter("replay")
    for i in 8:await process_frame
    check(not current_scene.is_live and not current_scene.playback.current.units.is_empty(),"Replay menu preserves Python recordings")
    current_scene.action("menu")
    for i in 3:await process_frame
    current_scene.enter("campaign-new")
    for i in 8:await process_frame
    check(current_scene.has_method("refresh") and current_scene.bridge.HasCampaign(),"Main menu starts native campaign overview")
    check(JSON.parse_string(current_scene.bridge.GetView()).state.roster.size()==5,"New campaign menu creates persistent starting army")
    print("Godot main-menu checks: ",checks,", failed: ",failed);quit(1 if failed else 0)
