class_name BattlePlayback
extends RefCounted
## Timing and interpolation brackets; the renderer sees only frames and alpha.
const Source = preload("res://scripts/recording_source.gd")
const Frame = preload("res://scripts/battle_frame.gd")
var source: Source
var time: float = 0.0
var speed: float = 1.0
var playing: bool = true
var current: Frame
var following: Frame
var alpha: float = 0.0
var events: Array = []

func attach(value: Source) -> bool:
    source = value
    return seek(source.times[0])

func seek(value: float) -> bool:
    var requested := clampf(value, source.times[0], source.times[-1])
    var upper := source.lower_bound(requested)
    var index := mini(upper, source.times.size() - 1)
    if source.times[index] > requested:index = maxi(0, index - 1)
    var a := source.frame(index)
    var b := source.frame(mini(index + 1, source.times.size() - 1))
    if a == null or b == null:
        playing = false
        return false
    time = requested;current = a;following = b
    alpha = clampf((time - current.time) / (following.time - current.time), 0.0, 1.0) if following.time > current.time else 0.0
    events = source.recent_events(time)
    if time >= source.times[-1]:playing = false
    return true

func advance(delta: float) -> bool:
    return seek(time + maxf(0.0, delta) * speed) if playing else true

func restart() -> bool:
    playing = true
    return seek(source.times[0])
