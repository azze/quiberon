extends RefCounted
## Defaults only: configured Project Settings/InputMap mappings take precedence.
const KEYS = {
    "camera_forward": [KEY_W, KEY_UP], "camera_backward": [KEY_S, KEY_DOWN],
    "camera_left": [KEY_A, KEY_LEFT], "camera_right": [KEY_D, KEY_RIGHT],
    "camera_yaw_left": [KEY_Q], "camera_yaw_right": [KEY_E],
    "camera_fast": [KEY_SHIFT], "camera_orbit_modifier": [KEY_ALT],
    "camera_fit": [KEY_HOME], "camera_focus": [KEY_F], "camera_follow": [KEY_C],
    "camera_overhead": [KEY_T], "camera_projection": [KEY_P]
}
static func install() -> void:
    for action in KEYS:
        if InputMap.has_action(action):continue
        InputMap.add_action(action)
        for key in KEYS[action]:
            var event := InputEventKey.new();event.physical_keycode = key;InputMap.action_add_event(action, event)
    for pair in [["camera_drag", MOUSE_BUTTON_MIDDLE], ["camera_zoom_in", MOUSE_BUTTON_WHEEL_UP], ["camera_zoom_out", MOUSE_BUTTON_WHEEL_DOWN]]:
        if InputMap.has_action(pair[0]):continue
        InputMap.add_action(pair[0]);var event := InputEventMouseButton.new();event.button_index = pair[1];InputMap.action_add_event(pair[0], event)
