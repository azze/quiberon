extends SceneTree
const Screen=preload("res://scripts/campaign_screen.gd")
const Viewer=preload("res://scripts/three_d/viewer_3d.gd")
var failed:=false
var checks:=0
func check(value: bool,text: String) -> void:
    checks+=1
    if not value:failed=true;push_error(text)
func _initialize() -> void:run.call_deferred()
func capture(path: String) -> void:
    if DisplayServer.get_name()=="headless" or "--test-capture" not in OS.get_cmdline_user_args():return
    await process_frame;await process_frame;RenderingServer.force_draw();root.get_texture().get_image().save_png(path)
func run() -> void:
    root.size=Vector2i(1280,800)
    if DisplayServer.get_name()!="headless":root.show()
    var b=load("res://scripts/simulation_adapter/CampaignBridge.cs").new();root.add_child(b)
    check(b.NewCampaign("1796"),"Native campaign starts")
    check(b.HasSave(),"Versioned campaign autosave exists")
    var screen:=Screen.new();root.add_child(screen);await process_frame
    var view: Dictionary=JSON.parse_string(b.GetView())
    check(view.state.roster.size()==5 and view.state.stage==1,"Starting roster reaches actual overview UI")
    check(view.state.commanders.size()==6,"Replaced generic leader remains in reserve")
    await capture("/tmp/rtt-campaign-overview.png")
    screen.queue_free();await process_frame
    check(b.Prepare(true),"Prepared campaign encounter has independent deterministic battle seed")
    get_root().set_meta("menu_mode","campaign")
    var v:=Viewer.new();root.add_child(v);await process_frame;await process_frame;v.set_process(false)
    check(v.is_live and v.playback.backend.IsCampaign(),"Campaign uses existing C# live renderer")
    check(v.playback.backend.IsDeployment(),"Campaign enters deployment")
    check(v.playback.current.units.size()==9,"Starting player force plus authored Prussians")
    check(not v.playback.backend.EditDeployment(100,Vector2(200,300),0,"line"),"Cannot deploy enemy forces")
    check(not v.playback.backend.EditDeployment(1,Vector2(950,300),0,"line"),"Player deployment zone enforced")
    check(v.playback.backend.EditDeployment(1,Vector2(330,150),0,"line"),"Player can reposition persistent regiment")
    v.playback.synchronize();v.refresh_frame();v.refresh_ui()
    check(not v.playback.backend.RerollCommander(1),"Campaign officers cannot be rerolled in sandbox AI dialog")
    check(v.mission_panel.visible and v.mission_panel.text.contains("Prussian"),"Objective panel displayed")
    await capture("/tmp/rtt-campaign-frontier.png")
    v.action("deploy:start");v.playback.playing=false
    check(not v.playback.backend.IsDeployment(),"Existing deployment start enters battle")
    check(JSON.parse_string(b.GetView()).state.phase=="battle","Campaign state crosses battle boundary once")
    for i in 6500:
        v.playback.single_step()
        if v.playback.result!="":break
    check(v.playback.result!="","Actual autonomous opening battle concludes")
    v._process(0);v.set_process(false)
    check(v.hud.results_dialog.visible,"Existing battle results screen opens")
    check(v.hud.results_dialog.campaign_button.visible,"Same results screen offers campaign transition")
    check(JSON.parse_string(b.GetView()).state.history.size()==1,"Result committed before player can leave results")
    check(v.playback.backend.CompleteCampaign(),"Repeated presentation callback is idempotent")
    check(JSON.parse_string(b.GetView()).state.history.size()==1,"No duplicated history/rewards")
    await capture("/tmp/rtt-campaign-results.png")
    check(b.LoadCampaign(),"Committed reward/defeat screen survives reload")
    var state: Dictionary=JSON.parse_string(b.GetView()).state
    if state.phase=="rewards":
        var reward: Dictionary=state.rewards[0]
        check(b.Claim(reward.id,reward.upgrades[0] if reward.get("upgrades")!=null else ""),"Reward choice transitions to event")
        var event_view: Dictionary=JSON.parse_string(b.GetView())
        var e: Dictionary=event_view.events.filter(func(e):return e.id==event_view.state.pendingEvent)[0]
        check(b.ChooseEvent(e.choices[0].id),"Allied event resolves to next overview")
        check(JSON.parse_string(b.GetView()).state.stage==2,"Native UI actions reach second campaign stage")
    v.queue_free();await process_frame
    check(b.PrepareLaboratory(4,"1796","intercept"),"Isolated interception laboratory prepares without overwriting the save")
    get_root().set_meta("menu_mode","campaign")
    var convoy_view:=Viewer.new();root.add_child(convoy_view);await process_frame;await process_frame;convoy_view.set_process(false)
    check(convoy_view.playback.current.units[900].transport and convoy_view.units.mesh_cache.has("transport"),"Physical transport actors render with wagon silhouettes")
    await capture("/tmp/rtt-campaign-convoy.png")
    convoy_view.queue_free();await process_frame
    check(b.PrepareLaboratory(4,"1796","rescue"),"Rescue laboratory prepares")
    get_root().set_meta("menu_mode","campaign")
    var rescue_view:=Viewer.new();root.add_child(rescue_view);await process_frame;await process_frame;rescue_view.set_process(false)
    check(not rescue_view.playback.backend.EditDeployment(850,Vector2(180,450),0,"line"),"Cannot bypass rescue by redeploying the separated allied detachment")
    rescue_view.queue_free();b.queue_free();await process_frame
    print("Godot campaign checks: ",checks," failed: ",failed);quit(1 if failed else 0)
