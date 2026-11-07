class_name TacticalCameraSettings
extends Resource
## All speeds use real seconds and world metres; replay rate never enters here.
@export var move_speed: float = 90.0
@export var fast_multiplier: float = 3.0
@export var movement_acceleration: float = 10.0
@export var movement_smoothing: float = 12.0
@export var mouse_pan_sensitivity: float = 1.0
@export var rotation_speed: float = 1.2
@export var mouse_rotation_sensitivity: float = 0.005
@export var rotation_smoothing: float = 14.0
@export var zoom_sensitivity: float = 0.18
@export var zoom_smoothing: float = 12.0
@export var minimum_zoom: float = 18.0 # Vertical span in metres in either mode.
@export var maximum_zoom_diagonals: float = 1.6
@export var minimum_pitch: float = 0.0
@export var maximum_pitch: float = 88.0
@export var default_pitch: float = 55.0
@export var overhead_pitch: float = 87.0
@export var focus_smoothing: float = 10.0
@export var boundary_margin_fraction: float = 0.08
@export var boundary_margin_maximum: float = 250.0
@export var terrain_clearance: float = 3.0
@export var default_perspective: bool = true
@export var perspective_fov: float = 55.0

@export var minimum_near_clip: float = 0.15
@export var maximum_near_clip: float = 20.0
@export var near_clip_distance_ratio: float = 0.002
