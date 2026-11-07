# Tactical camera contract

The rig owns a Camera3D and a ground focal point. It knows a sampled terrain surface, input values and an optional followed position; it knows no replay clock or battle rules. The controller supplies **real frame delta**, never multiplied by playback speed. Pausing or seeking therefore does not stop navigation.

Default view is perspective, 55° above horizontal, with a fixed 55° lens field of view. Wheel zoom is a **physical dolly**: the camera approaches or retreats from the terrain under the cursor. It does not zoom by changing the lens. All keyboard camera translation is XZ; focal height follows the surface, and a safety clearance keeps the eye above terrain. The rig never flies vertically because of WASD. A long-distance near plane adapts for depth precision; near inspection retains a 0.15 m minimum clip.

At 0° the view is parallel to the ground. Below 10° the look point lifts gradually
with the eye so terrain clearance does not force the camera to keep looking down.
Alt-middle drag reaches the horizon; the minimum tilt is adjustable in Camera
settings. Ground ray misses above the horizon retain the normal zoom fallback.

## Motion and input

Keyboard movement follows the camera's yaw, with exponential acceleration/deceleration and separate focus smoothing. Cheap integration substeps of at most 1/120 s limit frame-rate differences, while pose/ray work happens once per rendered frame. This is only camera integration, not a change to the Python simulation timestep. Q/E and Alt-middle orbit around the current focal point; turning does not orbit the world origin.

Middle drag is intentionally a **direct ground grab**, with no extra spring lag. At sensitivity 1, the terrain point captured at press follows the cursor. Alt-middle instead smooths yaw/pitch. Release over a HUD panel and window focus loss end dragging. Right-click is unused for camera motion; live mode uses press/motion/release signals for destination-and-facing gestures through the shared terrain ray query. No order is committed until release.

Wheel input records a terrain-ray hit and eases the camera's physical distance towards its new value. The internal `span` remains a scale-compatible control value: `distance = span / (2*tan(fov/2))`, with fixed FOV. During the transition, reprojection corrections retain that original world point under the cursor, including when focal height changes uphill. Rays intersect the same sampled triangles used by the mesh; there is no competing flat plane or per-soldier collision query. Sky/outside-map rays gracefully fall back to dollying towards the current focus. At the camera's outer boundary margin exact cursor anchoring can relax rather than moving beyond the allowed region.

Camera hotkeys use physical-key `camera_*` InputMap actions. Existing mappings, including intentionally unbound actions, are respected. The global controller routes these shortcuts before SubViewport forwarding, but rejects them in file/settings/speed popups and text fields. Mouse events enter only the battlefield SubViewport; scrolling/clicking the HUD cannot zoom/pick the world.

## Focus, follow and modes

F eases towards a valid selected regiment without changing its scale/angle. C follows its interpolated ground position, without tracking facing/yaw. Selection changes update the followed target; destruction, withdrawal or disappearance ends follow. Manual pan/orbit cancels it immediately, including outstanding automatic focus motion. Zoom keeps following with an accumulated focal offset so the zoom anchor and follow target do not fight each other.

T saves yaw, pitch, view span and projection, then eases to 87° and orthographic presentation. T again restores the saved view while keeping the approximate ground focus. **Scrolling in an orthographic/overhead view switches to perspective and dollies**, retaining the viewing angle and terrain cursor anchor. T can still restore the pre-overhead view afterwards. Manual orbit leaves the overhead mode. P switches projection at equal focal-plane scale; objects at different depths naturally change apparent scale. Home computes a fit for the actual viewport aspect; perspective fitting accounts for near/far corners and terrain height bounds rather than reusing an orthographic rectangle.

Targets are bounded to a margin outside the field; the visible focus eases towards those targets, avoiding repeated push/clamp jitter. On resize, a fitted view eases to a new fit. A free/following view retains focus and span; stale mouse drag/zoom anchors are cleared because their old pixel coordinates no longer describe the resized viewport.

## Defaults and configuration

All values are in `resources/tactical_camera.tres` and its exported script. Runtime **Camera settings** adjusts common sensitivities/responsiveness without changing the saved resource.

| Parameter | Default |
|---|---:|
| Initial projection (`default_perspective`) | Perspective |
| Pan speed at 200 m view span | 90 m/s |
| Pan scaling with view span | 0.12–12× |
| Shift multiplier | 3× |
| Movement acceleration / smoothing | 10 / 12 s⁻¹ |
| Focus/follow smoothing | 10 s⁻¹ |
| Keyboard yaw rate | 1.2 rad/s |
| Mouse orbit sensitivity | 0.005 rad/pixel |
| Ground drag sensitivity | 1.0 |
| Rotation / zoom smoothing | 14 / 12 s⁻¹ |
| Wheel exponential scale | 0.18 per notch |
| Minimum view span | 18 m |
| Maximum view span | 1.6× map diagonal |
| Pitch limits / default / overhead | 0–88° / 55° / 87° |
| Boundary margin | 8% of smaller dimension, capped at 250 m |
| Eye terrain clearance | 3 m |
| Perspective vertical FOV | 55° |
| Near plane | distance ×0.002, clamped to 0.15–20 m |

Higher smoothing rates respond faster. Ground drag sensitivity other than 1 intentionally changes the grab ratio. Positive speed/range values and a pitch below 90° are required; live widgets constrain their exposed ranges. More extreme source-resource tuning should be validated with the camera test suite.
