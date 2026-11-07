extends Control
## Readable markers drawn above trees, independent of 3D geometry occlusion.
const World = preload("res://scripts/three_d/world_3d.gd")
var renderer: Object
var camera: Camera3D
var regions: Dictionary={}
var font: Font=ThemeDB.fallback_font
func _ready() -> void:mouse_filter=Control.MOUSE_FILTER_IGNORE
func _draw() -> void:
    regions.clear()
    if renderer==null or renderer.current==null:return
    for u in renderer.current.units.values():
        if not u.active or not u.observed or not renderer.poses.has(u.info.id):continue
        var world: Vector3=renderer.poses[u.info.id].world+Vector3(0,11,0)
        if camera.is_position_behind(world):continue
        var point := camera.unproject_position(world)
        if not get_rect().grow(25).has_point(point):continue
        var selected: bool=u.info.id==renderer.selected
        var color: Color=renderer.army_colors.get(u.info.army,Color.WHITE)
        var rect := Rect2(point-Vector2(22,19),Vector2(44,30));regions[u.info.id]=rect
        draw_rect(rect,Color(.04,.065,.06,.85),true)
        draw_rect(rect,Color("#ffe286") if selected else color,false,2)
        draw_string(font,point+Vector2(-17,-4),str(u.info.id)+":"+u.info.symbol,HORIZONTAL_ALIGNMENT_LEFT,-1,13,Color(.96,.95,.85))
        var bar: float=u.morale/100 if u.morale_simulated else float(u.strength)/maxi(1,u.info.maximum)
        draw_rect(Rect2(point+Vector2(-18,2),Vector2(36*bar,3)),Color(.4,.85,.4) if u.morale_simulated else Color(.95,.8,.45))
        draw_rect(Rect2(point+Vector2(-18,6),Vector2(36*u.cohesion/100,2)),Color(.5,.76,.95))
        if u.morale_simulated:draw_rect(Rect2(point+Vector2(-18,9),Vector2(36*float(u.strength)/maxi(1,u.info.maximum),1)),Color(.95,.8,.45))
        if u.state=="routing":draw_string(font,point+Vector2(25,-2),"ROUT",HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("#f4a0df"))
        elif u.state=="rallying":draw_string(font,point+Vector2(25,-2),"RALLY",HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("#7de6ae"))
        elif u.state in ["shaken","wavering"]:draw_string(font,point+Vector2(25,-2),"WAV" if u.state=="wavering" else "SHK",HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("#ffbf6f"))
        if u.cavalry_simulated and u.info.category=="cavalry" and u.charge_state in ["charging","pursuit","recoil","reforming"]:
            draw_string(font,point+Vector2(-20,-24),u.charge_state.to_upper(),HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("#ffe286"))
        if u.combat_state=="melee":draw_string(font,point+Vector2(25,-2),"MELEE",HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("#ffb174"))
    for shot in renderer.current.shots.values():
        var ball:=World.projectile(shot,renderer.following.shots.get(shot.id),renderer.alpha)
        if not camera.is_position_behind(ball):draw_circle(camera.unproject_position(ball),2,Color("#ffd884"))
    var chosen: Variant=renderer.current.units.get(renderer.selected)
    if chosen!=null and chosen.destination!=null and renderer.poses.has(renderer.selected):
        var from: Vector3=renderer.poses[renderer.selected].world+Vector3(0,1,0)
        var to:=World.ground(chosen.destination,renderer.surface.height_at(chosen.destination))+Vector3(0,1,0)
        if not camera.is_position_behind(from) and not camera.is_position_behind(to):
            var pixel:=camera.unproject_position(to)
            draw_dashed_line(camera.unproject_position(from),pixel,Color("#e9dab0"),1,5)
            draw_line(pixel-Vector2(5,5),pixel+Vector2(5,5),Color("#ffe286"),2)
            draw_line(pixel+Vector2(-5,5),pixel+Vector2(5,-5),Color("#ffe286"),2)
    if chosen!=null and renderer.poses.has(chosen.target) and renderer.poses.has(renderer.selected):
        var a: Vector3=renderer.poses[renderer.selected].world+Vector3(0,12,0)
        var b: Vector3=renderer.poses[chosen.target].world+Vector3(0,12,0)
        if not camera.is_position_behind(a) and not camera.is_position_behind(b):
            draw_dashed_line(camera.unproject_position(a),camera.unproject_position(b),Color("#e59374") if chosen.sight_transmission<=0 else Color("#ffe286"),1,6)
            draw_arc(camera.unproject_position(b),26,0,TAU,32,Color("#ffe286"),2,true)
func pick(pixel: Vector2) -> int:
    var ids := regions.keys();ids.reverse()
    for uid in ids:
        if regions[uid].has_point(pixel):return uid
    return -1
