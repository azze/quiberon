class_name WorldCoordinates
extends RefCounted
## One Godot canvas unit == one metre. Both worlds have +Y down and clockwise
## radians from +X. Camera2D is the only world->screen scale/translation.
const HEIGHT_SCALE := 1.0

static func to_canvas(metres: Vector2) -> Vector2:
    return metres

static func position_between(current: Object, next: Object, alpha: float) -> Vector2:
    return current.position.lerp(next.position, alpha) if next != null else current.position

static func facing_between(current: Object, next: Object, alpha: float) -> float:
    return lerp_angle(current.facing, next.facing, alpha) if next != null else current.facing

static func footprint(center: Vector2, facing: float, width: float, depth: float) -> PackedVector2Array:
    var forward := Vector2.from_angle(facing) * depth / 2.0
    var side := Vector2.from_angle(facing + PI / 2.0) * width / 2.0
    return PackedVector2Array([center + forward + side, center + forward - side,
        center - forward - side, center - forward + side, center + forward + side])

static func contains(point: Vector2, center: Vector2, facing: float, width: float, depth: float) -> bool:
    var local := (point - center).rotated(-facing)
    return absf(local.x) <= depth / 2.0 and absf(local.y) <= width / 2.0

static func ball_position(shot: Object, next: Object, alpha: float) -> Vector2:
    # Do not interpolate across a bounce, just as the Python presentation does.
    var blend := alpha if next != null and next.bounces == shot.bounces else 0.0
    var point := position_between(shot, next, blend)
    var height: float = lerpf(shot.height, next.height, blend) if next != null else shot.height
    var ground: float = lerpf(shot.ground, next.ground, blend) if next != null else shot.ground
    return point - Vector2(0.0, maxf(0.0, height - ground) * HEIGHT_SCALE)
