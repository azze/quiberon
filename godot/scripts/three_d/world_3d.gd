class_name BattlefieldCoordinates3D
extends RefCounted
## Presentation only: Python (x,y) -> Godot (x,elevation,z=y), 1 unit/metre.

static func ground(point: Vector2, elevation: float) -> Vector3:
    return Vector3(point.x, elevation, point.y)

static func horizontal(point: Vector3) -> Vector2:
    return Vector2(point.x, point.z)

static func yaw(facing: float) -> float:
    # Models face local +X; Godot Y rotations have opposite handedness to XY.
    return -facing

static func facing_basis(facing: float) -> Basis:
    return Basis(Vector3.UP, yaw(facing))

static func point_between(a: Object, b: Object, alpha: float) -> Vector2:
    return a.position.lerp(b.position, alpha) if b != null else a.position

static func angle_between(a: Object, b: Object, alpha: float) -> float:
    return lerp_angle(a.facing, b.facing, alpha) if b != null else a.facing

static func projectile(a: Object, b: Object, alpha: float) -> Vector3:
    var t := alpha if b != null and b.bounces == a.bounces else 0.0
    var pos := point_between(a, b, t)
    # Python height is already ABSOLUTE elevation: never add ground twice.
    var height: float = lerpf(a.height, b.height, t) if b != null else a.height
    return ground(pos, height)
