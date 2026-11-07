extends Node2D
## Presentation orchestration only. The source can later be a C# frame adapter.
const Source = preload("res://scripts/recording_source.gd")
const Playback = preload("res://scripts/playback.gd")
const TerrainView = preload("res://scripts/terrain_view.gd")
const UnitsView = preload("res://scripts/regiment_view.gd")

var playback: Playback
var terrain_view: TerrainView
var units_view: UnitsView
var camera: Camera2D
var status: Label
var inspect: Label
var notices: Label
var clock_label: Label
var play_button: Button
var speeds: OptionButton
var timeline: HSlider
var dialog: FileDialog
var ui_updating := false
var dragging := false
var ui_elapsed := 0.0
var load_ms := 0.0
var load_error := ""
const INSPECTION_HINT := "REGIMENT INSPECTION\n\nSelect any regiment.\n\nRectangle: infantry\nChevron: cavalry\nGun: artillery\nDispersed dots: skirmishers\n\nBorder = allegiance\nArrow = facing\nGreen bar = morale\nGold ring = current target"
var benchmark_frames := 0
var benchmark_output := ""
var screenshot_path := ""
var frame_samples: Array = []
var last_process_us: int = 0
var draw_samples: Array = []
var warmup := 60
var screenshot_written := false

func _ready() -> void:
    terrain_view = TerrainView.new();add_child(terrain_view)
    units_view = UnitsView.new();add_child(units_view)
    camera = Camera2D.new();add_child(camera)
    build_ui()
    get_viewport().size_changed.connect(fit_battlefield)
    var path := "res://recordings/combined-arms/metadata.json"
    var paused := false
    var seek_to := -1.0
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--recording="):path = arg.trim_prefix("--recording=")
        elif arg == "--paused":paused = true
        elif arg.begins_with("--seek="):seek_to = float(arg.trim_prefix("--seek="))
        elif arg.begins_with("--benchmark-frames="):benchmark_frames = int(arg.trim_prefix("--benchmark-frames="))
        elif arg.begins_with("--benchmark-output="):benchmark_output = arg.trim_prefix("--benchmark-output=")
        elif arg.begins_with("--screenshot="):screenshot_path = arg.trim_prefix("--screenshot=")
    load_recording(path)
    if playback != null:
        playback.playing = not paused
        if seek_to >= 0:playback.seek(seek_to)
        refresh_frame();refresh_ui()
    if benchmark_frames > 0:
        Engine.max_fps = 0
        if DisplayServer.get_name() != "headless":DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)

func button(label: String, callback: Callable, box: Container) -> Button:
    var item := Button.new();item.focus_mode = Control.FOCUS_NONE;item.text = label;item.pressed.connect(callback);box.add_child(item)
    return item

func panel(parent: Control, left: float, top: float, right: float, bottom: float, anchor_left: float = 0, anchor_top: float = 0, anchor_right: float = 0, anchor_bottom: float = 0) -> PanelContainer:
    var result := PanelContainer.new();parent.add_child(result)
    result.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
    result.anchor_left = anchor_left;result.anchor_top = anchor_top;result.anchor_right = anchor_right;result.anchor_bottom = anchor_bottom
    result.offset_left = left;result.offset_top = top;result.offset_right = right;result.offset_bottom = bottom
    var padding := StyleBoxFlat.new();padding.bg_color = Color(0.055, 0.08, 0.07, 0.96)
    padding.content_margin_left = 12;padding.content_margin_top = 8;padding.content_margin_right = 12;padding.content_margin_bottom = 8
    result.add_theme_stylebox_override("panel", padding)
    return result

func build_ui() -> void:
    var layer := CanvasLayer.new();add_child(layer)
    var root := Control.new();root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);root.mouse_filter = Control.MOUSE_FILTER_IGNORE;layer.add_child(root)
    var top := panel(root, 10, 10, -10, 113, 0, 0, 1, 0)
    var box := VBoxContainer.new();top.add_child(box)
    var row := HBoxContainer.new();row.add_theme_constant_override("separation", 8);box.add_child(row)
    button("Open recording", func(): dialog.popup_centered_ratio(0.8), row)
    play_button = button("Pause [Space]", toggle_play, row)
    button("Restart [Home]", restart_playback, row)
    button("Fit [F]", fit_battlefield, row)
    speeds = OptionButton.new();speeds.focus_mode = Control.FOCUS_NONE
    for speed in [0.25, 0.5, 1.0, 2.0, 4.0]:speeds.add_item(str(speed) + "×")
    speeds.select(2);speeds.item_selected.connect(func(index):
        if playback != null:playback.speed = [0.25, 0.5, 1.0, 2.0, 4.0][index])
    row.add_child(speeds)
    status = Label.new();status.text = "Open a Python battle recording.";status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS;box.add_child(status)
    var help := Label.new();help.text = "Wheel zoom · Middle-drag / WASD / arrows pan · Click regiment to inspect · Playback is read-only"
    help.add_theme_font_size_override("font_size", 13);box.add_child(help)
    var side := panel(root, -300, 124, -10, -96, 1, 0, 1, 1)
    var scroll := ScrollContainer.new();side.add_child(scroll)
    inspect = Label.new();inspect.custom_minimum_size = Vector2(260, 0);inspect.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    inspect.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART;scroll.add_child(inspect)
    inspect.text = INSPECTION_HINT
    var bottom := panel(root, 10, -86, -10, -10, 0, 1, 1, 1)
    var column := VBoxContainer.new();bottom.add_child(column)
    var strip := HBoxContainer.new();column.add_child(strip)
    clock_label = Label.new();clock_label.custom_minimum_size.x = 240;strip.add_child(clock_label)
    timeline = HSlider.new();timeline.focus_mode = Control.FOCUS_NONE;timeline.size_flags_horizontal = Control.SIZE_EXPAND_FILL;timeline.step = 0.001
    timeline.value_changed.connect(func(value):
        if not ui_updating and playback != null:
            if not playback.seek(value):status.text = playback.source.error
            refresh_frame();refresh_ui())
    strip.add_child(timeline)
    notices = Label.new();notices.add_theme_font_size_override("font_size", 13);notices.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS;column.add_child(notices)
    dialog = FileDialog.new();dialog.title = "Open battle recording metadata.json";dialog.access = FileDialog.ACCESS_FILESYSTEM
    dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE;dialog.filters = PackedStringArray(["*.json ; Battle metadata (metadata.json)"])
    dialog.current_dir = ProjectSettings.globalize_path("res://recordings")
    dialog.file_selected.connect(load_recording);root.add_child(dialog)

func load_recording(path: String) -> bool:
    var start := Time.get_ticks_usec()
    var source := Source.new()
    if not source.load_recording(path):
        load_error = source.error;status.text = load_error
        return false
    var next := Playback.new()
    if not next.attach(source):
        load_error = source.error;status.text = load_error
        return false
    load_error = ""
    playback = next;units_view.selected = -1;units_view.army_colors = source.armies
    terrain_view.configure(source.terrain);fit_battlefield()
    ui_updating = true;timeline.min_value = source.times[0];timeline.max_value = source.times[-1];timeline.value = source.times[0];ui_updating = false
    speeds.select(2)
    load_ms = (Time.get_ticks_usec() - start) / 1000.0
    refresh_frame();refresh_ui()
    return true

func fit_battlefield() -> void:
    if playback == null:return
    var size := get_viewport_rect().size
    var available := Vector2(maxf(100, size.x - 345), maxf(100, size.y - 245))
    var world := playback.source.world_size
    var zoom := clampf(minf(available.x / world.x, available.y / world.y), 0.01, 6.0)
    camera.zoom = Vector2.ONE * zoom
    camera.position = world / 2.0 + Vector2(155.0 / zoom, -17.0 / zoom)
    camera.force_update_scroll()

func toggle_play() -> void:
    if playback == null:return
    if playback.time >= playback.source.times[-1]:playback.restart()
    else:playback.playing = not playback.playing
    refresh_ui()

func restart_playback() -> void:
    if playback != null:
        playback.restart();refresh_frame();refresh_ui()

func refresh_frame() -> void:
    if playback == null:return
    units_view.zoom = camera.zoom.x
    units_view.display(playback.current, playback.following, playback.alpha, playback.time, playback.events)

func refresh_ui() -> void:
    if playback == null:return
    var frame: Variant = playback.current
    status.text = "%s | seed %s | %d regiments | %d balls | FPS %d" % [playback.source.title, playback.source.seed_text, frame.units.size(), frame.shots.size(), Engine.get_frames_per_second()]
    if playback.source.error != "":status.text = playback.source.error
    if load_error != "":status.text = load_error
    play_button.text = "Pause [Space]" if playback.playing else "Play [Space]"
    clock_label.text = "%.1f / %.1f s  %s" % [playback.time, playback.source.times[-1], frame.result]
    ui_updating = true;timeline.value = playback.time;ui_updating = false
    var text := ""
    for event in playback.events:
        if event.message != "":text = event.message
    notices.text = text if text != "" else "Recorded state only · no battle rules execute in Godot"
    if not frame.units.has(units_view.selected):
        inspect.text = INSPECTION_HINT;return
    var u: Variant = frame.units[units_view.selected]
    var target: String = str(u.target) if u.target >= 0 else "None"
    if frame.units.has(u.target):target += " — " + frame.units[u.target].info.name
    inspect.text = "%s\n\n%s\nArmy %d · #%d\n\nCommander\n%s\n\nStrength: %d / %d\nMorale: %.1f\nCohesion: %.1f\n\nFormation: %s\nState: %s\nCombat: %s\nOrder: %s\nTarget: %s\n\nCharge: %s\nMomentum: %.0f%%\nSpeed: %.1f m/s\n\nPosition: %.1f, %.1f m\nFacing: %.1f°\n%s" % [u.info.name, u.info.category + " / " + u.info.archetype, u.info.army, u.info.id, u.info.commander, u.strength, u.info.maximum, u.morale, u.cohesion, u.formation, u.state, u.combat_state, u.order, target, u.charge_state, u.momentum * 100, u.speed, u.position.x, u.position.y, rad_to_deg(u.facing), "Withdrawn/destroyed" if not u.active else ""]

func _process(delta: float) -> void:
    var now := Time.get_ticks_usec()
    var wall_frame_ms := (now - last_process_us) / 1000.0 if last_process_us > 0 else 0.0
    last_process_us = now
    if playback == null:return
    if not playback.advance(delta):status.text = playback.source.error
    if not dialog.visible and get_viewport().gui_get_focus_owner() == null:
        var pan := Vector2(float(Input.is_physical_key_pressed(KEY_D) or Input.is_physical_key_pressed(KEY_RIGHT)) - float(Input.is_physical_key_pressed(KEY_A) or Input.is_physical_key_pressed(KEY_LEFT)), float(Input.is_physical_key_pressed(KEY_S) or Input.is_physical_key_pressed(KEY_DOWN)) - float(Input.is_physical_key_pressed(KEY_W) or Input.is_physical_key_pressed(KEY_UP)))
        camera.position += pan.normalized() * delta * 550.0 / camera.zoom.x
    refresh_frame();ui_elapsed += delta
    if ui_elapsed >= 0.1:refresh_ui();ui_elapsed = 0.0
    if screenshot_path != "" and not screenshot_written:
        screenshot_written = true
        save_screenshot.call_deferred()
    if benchmark_frames > 0:
        if warmup > 0:warmup -= 1
        else:
            frame_samples.append(wall_frame_ms);draw_samples.append(units_view.last_draw_us / 1000.0)
            if frame_samples.size() >= benchmark_frames:finish_benchmark()

func save_screenshot() -> void:
    await RenderingServer.frame_post_draw
    if DisplayServer.get_name() != "headless":get_viewport().get_texture().get_image().save_png(screenshot_path)

func stats(values: Array) -> Dictionary:
    values.sort()
    var total := 0.0
    for v in values:total += v
    return {"mean_ms": total / values.size(), "median_ms": values[values.size() / 2], "p95_ms": values[mini(values.size() - 1, int(values.size() * 0.95))]}

func finish_benchmark() -> void:
    benchmark_frames = 0
    var result := {"mode": DisplayServer.get_name(), "godot": Engine.get_version_info().string, "units": playback.current.units.size(), "frames": frame_samples.size(), "frame": stats(frame_samples), "unit_draw_cpu": stats(draw_samples), "load_ms": load_ms, "terrain_build_ms": terrain_view.build_ms, "terrain_builds": terrain_view.builds, "decoded_frames": playback.source.decoded_frames, "snapshot_cache": playback.source.frame_cache.size(), "snapshot_count": playback.source.times.size()}
    print(JSON.stringify(result))
    if benchmark_output != "":
        var file := FileAccess.open(benchmark_output, FileAccess.WRITE)
        if file != null:file.store_string(JSON.stringify(result, "  ") + "\n")
    get_tree().quit()

func _input(event: InputEvent) -> void:
    # A release over a HUD panel still ends a camera drag.
    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_MIDDLE and not event.pressed:dragging = false

func _notification(what: int) -> void:
    if what == NOTIFICATION_WM_WINDOW_FOCUS_OUT:dragging = false

func _unhandled_input(event: InputEvent) -> void:
    if dialog.visible:return
    if event is InputEventMouseButton:
        if event.button_index == MOUSE_BUTTON_MIDDLE:dragging = event.pressed
        if event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
            var before := get_global_mouse_position()
            camera.zoom = Vector2.ONE * clampf(camera.zoom.x * (1.15 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 1.15), 0.01, 6.0)
            camera.force_update_scroll();camera.position += before - get_global_mouse_position();camera.force_update_scroll()
        if event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
            units_view.selected = units_view.pick(get_global_mouse_position());refresh_ui()
    elif event is InputEventMouseMotion and dragging:camera.position -= event.relative / camera.zoom.x
    elif event is InputEventKey and event.pressed and not event.echo:
        match event.keycode:
            KEY_SPACE:toggle_play()
            KEY_F:fit_battlefield()
            KEY_HOME:restart_playback()
            KEY_ESCAPE:units_view.selected = -1
            KEY_1, KEY_2, KEY_4:
                if playback != null:
                    var speed := int(event.keycode) - KEY_0
                    playback.speed = float(speed);speeds.select({1: 2, 2: 3, 4: 4}[speed])
