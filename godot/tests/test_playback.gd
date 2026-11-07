extends SceneTree
## Run with: godot --headless --path godot --script tests/test_playback.gd
const Source = preload("res://scripts/recording_source.gd")
const Playback = preload("res://scripts/playback.gd")
const Frame = preload("res://scripts/battle_frame.gd")
const World = preload("res://scripts/world_coordinates.gd")
const TerrainView = preload("res://scripts/terrain_view.gd")
const Viewer = preload("res://scripts/viewer.gd")
var checks: int = 0
var failed: bool = false

func check(condition: bool, message: String) -> void:
    checks += 1
    if not condition:
        failed = true;push_error("TEST FAILED: " + message)

func fixture() -> String:
    var directory := "user://test_recording"
    DirAccess.make_dir_recursive_absolute(directory)
    var input := "res://recordings/combined-arms/"
    for name in ["metadata.json", "frames.jsonl", "events.jsonl", "index.jsonl"]:
        var source := FileAccess.open(input + name, FileAccess.READ)
        var target := FileAccess.open(directory.path_join(name), FileAccess.WRITE)
        target.store_buffer(source.get_buffer(source.get_length()))
    return directory

func write_json(path: String, value: Variant) -> void:
    var file := FileAccess.open(path, FileAccess.WRITE);file.store_string(JSON.stringify(value))

func _initialize() -> void:
    run.call_deferred()

func run() -> void:
    var source := Source.new()
    check(source.load_recording("res://recordings/combined-arms/metadata.json"), "Load complete demo: " + source.error)
    if source.times.is_empty():quit(1);return
    check(source.metadata.result in ["army_0", "army_1", "draw"], "Demo has a real result")
    check(source.seed_text == "7", "Seed retained as decimal text")
    var playback := Playback.new();check(playback.attach(source), "Attach source")
    check(playback.current.tick == 0, "Playback begins at initial state")
    var first_count := playback.current.units.size()
    check(first_count == 12, "Regiment metadata/frames parse")
    check(source.frame(0).units[0].info.commander != "", "Commander parsed")
    check(source.frame(0).units[0].position.x > 0, "World coordinates retained")
    playback.playing = false;var previous := playback.time;playback.advance(5)
    check(playback.time == previous, "Pause does not advance")
    playback.playing = true;playback.speed = 4;playback.advance(0.125)
    check(is_equal_approx(playback.time, 0.5), "Playback speed")
    check(playback.seek(-100) and playback.time == source.times[0], "Seek clamps at start")
    check(playback.seek(100000) and playback.time == source.times[-1] and not playback.playing, "End clamps and pauses")
    check(playback.current.result == source.metadata.result, "Final frame result")
    check(playback.restart() and playback.playing and playback.time == 0, "Restart")
    check(playback.seek(0.25) and is_equal_approx(playback.alpha, 0.5), "Interpolation fraction")
    var a := Frame.UnitState.new();a.position = Vector2(10, 20);a.facing = deg_to_rad(179)
    var b := Frame.UnitState.new();b.position = Vector2(30, 40);b.facing = deg_to_rad(-179)
    check(World.position_between(a, b, 0.5).is_equal_approx(Vector2(20, 30)), "Position interpolation")
    check(absf(absf(World.facing_between(a, b, 0.5)) - PI) < 0.00001, "Shortest-angle interpolation")
    check(World.to_canvas(Vector2(400, 200)) == Vector2(400, 200), "One canvas unit per metre")
    var corners := World.footprint(Vector2(100, 100), 0, 64, 12)
    check(corners[0].is_equal_approx(Vector2(106, 132)), "Frontage perpendicular to facing")
    check(World.contains(Vector2(105, 130), Vector2(100, 100), 0, 64, 12), "Hit testing")
    check(not World.contains(Vector2(110, 100), Vector2(100, 100), 0, 64, 12), "Hit testing rejects outside depth")
    var terrain := Frame.TerrainData.new();terrain.size = Vector2(1000, 600)
    terrain.hills = [{"center": Vector2(500, 300), "radius": Vector2(100, 80), "height": 40.0, "compact": false}]
    terrain.forests = [{"center": Vector2(500, 300), "radius": Vector2(100, 80), "density": 0.8}]
    check(is_equal_approx(terrain.elevation(Vector2(500, 300)), 40), "Analytic Gaussian hill centre")
    check(is_equal_approx(terrain.elevation(Vector2(600, 300)), 40 * exp(-0.5)), "Gaussian hill edge")
    terrain.hills[0].compact = true
    check(is_equal_approx(terrain.elevation(Vector2(600, 300)), 40 * pow(1.0 - 1.0 / 9.0, 4)), "Compact hill shape")
    check(terrain.elevation(Vector2(801, 300)) == 0, "Compact hill support")
    check(is_equal_approx(terrain.forest_density(Vector2(500, 300)), 0.8), "Forest density centre")
    check(terrain.forest_density(Vector2(601, 300)) == 0, "Forest region edge")
    var ball := Frame.ShotState.new();ball.position = Vector2(100, 200);ball.height = 30;ball.ground = 20
    check(World.ball_position(ball, null, 0).is_equal_approx(Vector2(100, 190)), "Absolute height above actual ground")
    var next := Frame.ShotState.new();next.position = Vector2(120, 200);next.height = 40;next.ground = 20
    check(World.ball_position(ball, next, 0.5).is_equal_approx(Vector2(110, 185)), "Projectile interpolation")
    next.bounces = 1
    check(World.ball_position(ball, next, 0.5).is_equal_approx(Vector2(100, 190)), "No interpolation through bounce")
    var events: Dictionary = {}
    for e in source.events:events[e.kind] = true
    for kind in ["volley", "artillery_fire", "projectile_spawn", "impact", "charge_start", "charge_impact", "rout", "rally", "result"]:
        check(events.has(kind), "Demo contains " + kind)
    # Walk all snapshots, including withdrawal/rout/rally/removal transitions.
    var max_balls := 0
    for index in range(source.times.size()):
        var frame := source.frame(index)
        if frame == null:check(false, "Frame parsing " + str(index) + ": " + source.error);break
        max_balls = maxi(max_balls, frame.shots.size())
    check(max_balls > 0, "Active projectile snapshots")
    check(source.frame_cache.size() <= 4, "Decoded frames bounded")
    var decoded := source.decoded_frames;source.frame(source.times.size() - 1)
    check(decoded == source.decoded_frames, "Unchanged frame not reparsed")
    # Malformed/missing files fail without an engine exception.
    var bad := Source.new();check(not bad.load_recording("user://does-not-exist.json") and bad.error != "", "Missing recording error")
    var folder := fixture()
    var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("metadata.json")))
    data.version = 99;write_json(folder.path_join("metadata.json"), data)
    check(not Source.new().load_recording(folder.path_join("metadata.json")), "Reject unknown format")
    data.version = 1;data.world.y_axis = "up";write_json(folder.path_join("metadata.json"), data)
    check(not Source.new().load_recording(folder.path_join("metadata.json")), "Reject incompatible coordinates")
    data.world.y_axis = "down";data.status = "incomplete";write_json(folder.path_join("metadata.json"), data)
    check(not Source.new().load_recording(folder.path_join("metadata.json")), "Reject incomplete export")
    data.status = "complete";write_json(folder.path_join("metadata.json"), data)
    var valid := Source.new();check(valid.load_recording(folder.path_join("metadata.json")), "Fixture restored: " + valid.error)
    # Corrupt a middle frame only after valid header/index loading. Atomic seek
    # must stop safely and retain the last valid pair.
    var test_player := Playback.new();test_player.attach(valid)
    var before = test_player.current
    var file := FileAccess.open(folder.path_join("frames.jsonl"), FileAccess.READ_WRITE)
    file.seek(valid.offsets[20]);file.store_string("!");file.close()
    check(not test_player.seek(valid.times[20]), "Lazy invalid frame stops playback")
    check(test_player.current == before and not test_player.playing, "Invalid seek preserves last valid state")
    # Scene/controller/selection integration, using the same nodes as the viewer.
    var viewer := Viewer.new();root.add_child(viewer)
    await process_frame
    check(viewer.playback != null, "Main scene loads default recording")
    viewer.playback.playing = false;viewer.playback.seek(60);viewer.refresh_frame()
    var u = viewer.playback.current.units[0];var pose: Dictionary = viewer.units_view.unit_pose(u)
    check(viewer.units_view.pick(pose.position) >= 0, "Selection at interpolated position")
    viewer.units_view.selected = 0;viewer.refresh_ui()
    check(viewer.inspect.text.contains(u.info.commander), "Inspection panel shows commander")
    viewer.set_process(false)
    var absent := Frame.new()
    viewer.units_view.following = absent
    check(viewer.units_view.unit_pose(u).position == u.position, "Missing next regiment has no invented motion")
    viewer.units_view.display(absent, absent, 0.0, 0.0, [])
    await process_frame
    check(viewer.units_view.pick(Vector2.ZERO) == -1, "Empty/disappeared formations render and pick safely")
    viewer.refresh_frame()
    var builds: int = viewer.terrain_view.builds;viewer.fit_battlefield();viewer.refresh_frame()
    check(viewer.terrain_view.builds == builds, "Camera fitting does not rebuild terrain")
    check(not viewer.load_recording("user://missing.json") and viewer.playback != null, "Invalid load retains current battle")
    viewer.refresh_ui();check(viewer.status.text.contains("Cannot open"), "Load error remains visible")
    viewer.units_view.selected = -1;viewer.refresh_ui()
    check(viewer.inspect.text.contains("Select any regiment"), "Deselect clears stale inspection")
    var old_zoom := viewer.camera.zoom.x
    viewer.playback.source.world_size = Vector2(4800, 3000);viewer.fit_battlefield()
    check(viewer.camera.zoom.x < old_zoom, "Camera fits large maps in metres")
    viewer.dragging = true
    var release := InputEventMouseButton.new();release.button_index = MOUSE_BUTTON_MIDDLE;release.pressed = false
    viewer._input(release);check(not viewer.dragging, "Release over UI ends pan")
    viewer.queue_free();await process_frame
    print("Godot playback checks: %d, failed: %s" % [checks, failed])
    quit(1 if failed else 0)
