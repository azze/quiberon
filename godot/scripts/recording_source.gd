class_name RecordingSource
extends RefCounted
## Wire-format adapter. Index + events in memory, four decoded frames maximum.
const Frame = preload("res://scripts/battle_frame.gd")
const MAX_LINE := 4 * 1024 * 1024
var error: String = ""
var title: String = ""
var seed_text: String = ""
var world_size: Vector2
var terrain: Frame.TerrainData
var armies: Dictionary = {}
var definitions: Dictionary = {}
var times: PackedFloat64Array = PackedFloat64Array()
var offsets: PackedInt64Array = PackedInt64Array()
var ticks: PackedInt64Array = PackedInt64Array()
var events: Array = []
var frame_cache: Dictionary = {}
var stream: FileAccess
var metadata: Dictionary = {}
var decoded_frames: int = 0

static func number(v: Variant) -> bool:
    return (v is float or v is int) and is_finite(float(v))

static func integer(v: Variant) -> bool:
    return number(v) and float(v) == floor(float(v)) and absf(float(v)) < 9007199254740992.0

static func vector(v: Variant) -> bool:
    return v is Array and v.size() == 2 and number(v[0]) and number(v[1])

func fail(message: String) -> bool:
    error = message
    return false

func read_json(text: String, where: String) -> Variant:
    var parser := JSON.new()
    if text.length() > MAX_LINE or parser.parse(text) != OK:
        fail("Invalid JSON in " + where + ": " + parser.get_error_message())
        return null
    return parser.data

func load_recording(path: String) -> bool:
    error = "";armies.clear();definitions.clear();times.clear();offsets.clear();ticks.clear();events.clear();frame_cache.clear();stream = null
    if path.get_extension().to_lower() != "json":
        return fail("Open the recording's metadata.json file.")
    var header := FileAccess.open(path, FileAccess.READ)
    if header == null:
        return fail("Cannot open recording: " + path)
    if header.get_length() > MAX_LINE:
        return fail("Metadata is too large.")
    var data: Variant = read_json(header.get_as_text(), "metadata")
    if not data is Dictionary:
        return fail("Recording metadata must be an object.")
    if data.get("format") != "quiberon-battle-recording" or data.get("version") != 1:
        return fail("Unsupported recording format/version.")
    if not data.get("status") in ["complete", "limit"]:
        return fail("Recording was not closed successfully (incomplete export).")
    if data.get("files") != {"frames": "frames.jsonl", "index": "index.jsonl", "events": "events.jsonl"}:
        return fail("Unsupported recording file names.")
    var world: Variant = data.get("world")
    if not world is Dictionary or not number(world.get("width")) or not number(world.get("height")):
        return fail("Missing battlefield dimensions.")
    if world.width <= 0 or world.height <= 0 or world.width > 100000 or world.height > 100000:
        return fail("Invalid battlefield dimensions.")
    if world.get("units") != "metres" or world.get("y_axis") != "down" or world.get("facing") != "clockwise_radians_from_positive_x" or world.get("frontage_axis") != "local_y":
        return fail("Unsupported coordinate convention.")
    if not number(data.get("dt")) or data.dt <= 0 or not integer(data.get("interval_ticks")) or data.interval_ticks < 1:
        return fail("Invalid snapshot timestep.")
    if not data.get("regiments") is Array or not data.get("archetypes") is Array or not data.get("armies") is Array:
        return fail("Missing regiment/archetype/army definitions.")
    var archetypes: Dictionary = {}
    for a in data.archetypes:
        if not a is Dictionary or not a.get("id") is String or archetypes.has(a.id):
            return fail("Invalid or duplicate archetype.")
        archetypes[a.id] = a
    for a in data.armies:
        if not a is Dictionary or not integer(a.get("id")) or armies.has(int(a.id)) or not a.get("color") is Array or a.color.size() != 3:
            return fail("Invalid army.")
        for channel in a.color:
            if not number(channel) or channel < 0 or channel > 255:
                return fail("Invalid army colour.")
        armies[int(a.id)] = Color(a.color[0] / 255.0, a.color[1] / 255.0, a.color[2] / 255.0)
    for d in data.regiments:
        if not d is Dictionary or not integer(d.get("id")) or definitions.has(int(d.id)) or not integer(d.get("army")) or not armies.has(int(d.army)) or not d.get("name") is String or not archetypes.has(d.get("archetype")):
            return fail("Invalid or duplicate regiment identity.")
        if not d.get("category") in ["infantry", "cavalry", "artillery"] or not integer(d.get("max_strength")) or d.max_strength <= 0:
            return fail("Invalid regiment category/strength.")
        var info := Frame.RegimentInfo.new()
        info.id = int(d.id); info.army = int(d.army); info.name = d.name
        info.archetype = d.archetype; info.category = d.category; info.maximum = int(d.max_strength)
        var a: Dictionary = archetypes[d.archetype]
        var stats: Variant=a.get("stats",{})
        var weapon_range: Variant=stats.get("range",0) if stats is Dictionary else 0
        info.weapon_range=float(weapon_range) if number(weapon_range) and weapon_range>=0 else 0
        info.symbol = str(a.get("symbol", "?"))
        info.guns = int(a.get("guns", 0));info.faction = str(a.get("faction", ""))
        var accent: Variant = a.get("accent", [230, 225, 180])
        if not accent is Array or accent.size() != 3:
            return fail("Invalid archetype accent.")
        for c in accent:
            if not number(c) or c < 0 or c > 255:
                return fail("Invalid archetype accent.")
        info.accent = Color(accent[0] / 255.0, accent[1] / 255.0, accent[2] / 255.0)
        if d.get("commander") != null and not d.commander is Dictionary:
            return fail("Invalid commander.")
        info.commander = (str(d.commander.get("rank", "")) + " " + str(d.commander.get("name", ""))).strip_edges() if d.get("commander") != null else "Unassigned"
        definitions[info.id] = info
    if definitions.is_empty():
        return fail("Recording has no regiments.")
    world_size = Vector2(world.width, world.height)
    if not load_terrain(data.get("terrain")):
        return false
    var folder := path.get_base_dir()
    stream = FileAccess.open(folder.path_join("frames.jsonl"), FileAccess.READ)
    var index := FileAccess.open(folder.path_join("index.jsonl"), FileAccess.READ)
    var event_file := FileAccess.open(folder.path_join("events.jsonl"), FileAccess.READ)
    if stream == null or index == null or event_file == null:
        return fail("Recording needs frames.jsonl, index.jsonl and events.jsonl beside metadata.json.")
    while index.get_position() < index.get_length():
        var row: Variant = read_json(index.get_line(), "snapshot index")
        if not row is Dictionary or not number(row.get("time")) or not integer(row.get("offset")) or not integer(row.get("tick")):
            return fail("Invalid snapshot index.")
        if row.offset < 0 or row.offset >= stream.get_length() or row.tick < 0 or row.time < 0 or absf(row.time - row.tick * data.dt) > 0.000001:
            return fail("Index offset/time outside the recording.")
        if not times.is_empty() and (row.time <= times[-1] or row.tick <= ticks[-1] or row.offset <= offsets[-1]):
            return fail("Snapshot index must be strictly increasing.")
        times.append(row.time); ticks.append(int(row.tick)); offsets.append(int(row.offset))
        if times.size() > 1000000:
            return fail("Recording exceeds one million indexed frames.")
    if times.is_empty() or times.size() != data.get("frame_count") or not number(data.get("start_time")) or not number(data.get("end_time")) or absf(times[0] - data.start_time) > 0.000001 or absf(times[-1] - data.end_time) > 0.000001:
        return fail("Metadata and snapshot index disagree.")
    while event_file.get_position() < event_file.get_length():
        var row: Variant = read_json(event_file.get_line(), "events")
        if not row is Dictionary or not integer(row.get("seq")) or row.seq != events.size() or not number(row.get("time")) or not row.get("kind") is String:
            return fail("Invalid event identity/time.")
        if row.time < times[0] or row.time > times[-1] or (not events.is_empty() and row.time < events[-1].time):
            return fail("Events must be in simulation-time order.")
        var event := Frame.BattleEvent.new()
        event.sequence = int(row.seq); event.time = row.time; event.kind = row.kind
        event.message = str(row.get("message", ""))
        if row.get("position") != null:
            if not vector(row.position): return fail("Invalid event position.")
            event.has_position = true; event.position = Vector2(row.position[0], row.position[1])
        for field in ["duration", "width", "facing"]:
            if row.has(field) and not number(row[field]): return fail("Invalid effect geometry.")
        event.duration = clampf(row.get("duration", 3.0), 0.0, 3.0)
        event.width = row.get("width", 0.0); event.facing = row.get("facing", 0.0)
        if row.get("unit_id") != null:
            if not integer(row.unit_id):return fail("Invalid event unit ID.")
            event.unit_id = int(row.unit_id)
        events.append(event)
        if events.size() > 1000000: return fail("Too many events.")
    if events.size() != data.get("event_count"):
        return fail("Metadata and event count disagree.")
    metadata = data; title = str(data.get("scenario", "Recorded battle")); seed_text = str(data.get("seed", "?"))
    if frame(0) == null or frame(times.size() - 1) == null:
        return false
    return true

func load_terrain(raw: Variant) -> bool:
    if not raw is Dictionary or raw.get("width") != world_size.x or raw.get("height") != world_size.y or not raw.get("hills") is Array or not raw.get("forests") is Array:
        return fail("Invalid terrain dimensions/features.")
    terrain = Frame.TerrainData.new(); terrain.size = world_size
    for type in ["hills", "forests"]:
        if raw[type].size() > 10000: return fail("Too many terrain features.")
        for f in raw[type]:
            if not f is Dictionary:return fail("Invalid terrain feature.")
            for k in ["x", "y", "radius_x", "radius_y", "height" if type == "hills" else "density"]:
                if not number(f.get(k)):return fail("Invalid terrain feature number.")
            if f.radius_x <= 0 or f.radius_y <= 0:return fail("Terrain radii must be positive.")
            var item := {"center": Vector2(f.x, f.y), "radius": Vector2(f.radius_x, f.radius_y)}
            if type == "hills":
                if not f.get("compact", false) is bool:return fail("Invalid hill type.")
                item["height"] = f.height; item["compact"] = f.get("compact", false); terrain.hills.append(item)
            else:
                if f.density < 0 or f.density > 1:return fail("Invalid forest density.")
                item["density"] = f.density; terrain.forests.append(item)
    return true

func frame(index: int) -> Frame:
    if frame_cache.has(index):return frame_cache[index]
    if index < 0 or index >= times.size():
        fail("Frame outside recording."); return null
    stream.seek(offsets[index])
    var raw: Variant = read_json(stream.get_line(), "frame " + str(index))
    if not raw is Dictionary or raw.get("time") != times[index] or raw.get("tick") != ticks[index] or not raw.get("units") is Array or not raw.get("projectiles") is Array:
        fail("Frame does not match its index.");return null
    var result := Frame.new(); result.time = raw.time; result.tick = int(raw.tick); result.result = str(raw.result) if raw.get("result") != null else ""
    for row in raw.units:
        if not row is Dictionary or not integer(row.get("id")) or not definitions.has(int(row.id)) or result.units.has(int(row.id)) or not vector(row.get("position")):
            fail("Invalid frame regiment.");return null
        for field in ["facing", "width", "depth", "morale", "cohesion", "speed", "charge_momentum"]:
            if not number(row.get(field)):
                fail("Invalid unit state number: " + field);return null
        var info: Frame.RegimentInfo = definitions[int(row.id)]
        if row.width <= 0 or row.depth <= 0 or not integer(row.get("strength")) or row.strength < 0 or row.strength > info.maximum or row.morale < 0 or row.morale > 100 or row.cohesion < 0 or row.cohesion > 100:
            fail("Regiment state outside valid bounds.");return null
        for field in ["state", "formation", "combat_state", "charge_state"]:
            if not row.get(field) is String:
                fail("Missing regiment state: " + field);return null
        if not row.get("order") is Dictionary or not row.order.get("kind") is String or not row.get("active") is bool or not row.get("withdrawn") is bool:
            fail("Invalid regiment order/activity.");return null
        for field in ["target_id", "pursuit_id"]:
            if row.get(field) != null and not integer(row[field]):
                fail("Invalid target ID.");return null
        var u := Frame.UnitState.new();u.info = info
        u.position = Vector2(row.position[0], row.position[1]);u.facing = row.facing
        u.width = row.width;u.depth = row.depth;u.formation = row.formation;u.strength = int(row.strength)
        u.morale = row.morale;u.cohesion = row.cohesion;u.state = row.state;u.combat_state = row.combat_state
        u.active = row.active;u.withdrawn = row.withdrawn;u.speed = row.speed;u.order = row.order.kind
        u.target = int(row.target_id) if row.get("target_id") != null else -1
        u.pursuit = int(row.pursuit_id) if row.get("pursuit_id") != null else -1
        u.charge_state = row.charge_state;u.momentum = row.charge_momentum
        result.units[info.id] = u
    for row in raw.projectiles:
        if not row is Dictionary or not integer(row.get("id")) or result.shots.has(int(row.id)) or not vector(row.get("position")) or not vector(row.get("velocity")):
            fail("Invalid projectile identity/position.");return null
        for field in ["height", "ground", "energy", "bounces"]:
            if not number(row.get(field)):
                fail("Invalid projectile state.");return null
        var p := Frame.ShotState.new();p.id = int(row.id)
        p.position = Vector2(row.position[0], row.position[1]);p.velocity = Vector2(row.velocity[0], row.velocity[1])
        p.height = row.height;p.ground = row.ground;p.energy = row.energy;p.bounces = int(row.bounces)
        result.shots[p.id] = p
    if frame_cache.size() >= 4:frame_cache.erase(frame_cache.keys()[0])
    frame_cache[index] = result;decoded_frames += 1
    return result

func lower_bound(time: float) -> int:
    var lo := 0
    var hi := times.size()
    while lo < hi:
        var mid := (lo + hi) / 2
        if times[mid] < time:lo = mid + 1
        else:hi = mid
    return lo

func recent_events(time: float) -> Array:
    var lo := 0
    var hi := events.size()
    while lo < hi:
        var mid := (lo + hi) / 2
        if events[mid].time < time - 3.0:lo = mid + 1
        else:hi = mid
    var result: Array = []
    while lo < events.size() and events[lo].time <= time:
        result.append(events[lo]);lo += 1
    return result
