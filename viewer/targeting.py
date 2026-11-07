"""Read-only target information shared by battlefield markers and HUD."""
from simulation.combat import firing_blocker, in_arc, attack_target
from simulation.regiment import UnitType, MoraleState

TARGET_COLOR = (255, 110, 85)
ORDER_COLOR = (110, 220, 255)


def valid_target(battle, unit, target_id):
    if unit is None or not unit.effective:
        return None
    target = battle.unit(target_id)
    return target if target and target.active and target.army != unit.army else None


def current_target(battle, unit):
    return valid_target(battle, unit, unit.target_id) if unit else None


def ordered_target(battle, unit):
    return valid_target(battle, unit, unit.order.target_id) if unit else None


def target_status(battle, unit, target):
    if not unit.active: return 'Regiment destroyed or withdrawn'
    if unit.state == MoraleState.ROUTING: return 'Routing — ignores attack orders'
    if unit.state == MoraleState.RALLYING: return 'Rallying — cannot attack yet'
    if target is None: return 'No active enemy target'
    if unit.combat_state=='melee': return 'In melee — ranged fire suspended'
    if unit.stats.kind==UnitType.INFANTRY and unit.order.kind.value=='charge': return 'Bayonet charge — closing for melee; musket fire withheld'
    if unit.stats.kind == UnitType.CAVALRY: return 'Pursuit / melee target'
    if unit.transition_left > 0: return 'Changing formation — cannot fire'
    if unit.limbered or unit.setup_left>0:
        return f'Battery relocating / deploying: {unit.limber_left+unit.setup_left:.1f}s'
    if (target.pos-unit.pos).length() > unit.stats.range: return 'Out of range — approaching/tracking'
    if not in_arc(unit,target,battle.rules.firing_half_arc): return 'Outside firing arc — turning/tracking'
    sight=battle.visibility(unit,target)
    if unit.stats.kind != UnitType.ARTILLERY and not sight.visible:
        return f'Target hidden by {sight.reason} — advance or reposition'
    if unit.stats.kind == UnitType.ARTILLERY and unit.army in battle.ai_armies and not unit.player_attack and not battle.perceives(unit,target):
        return 'Target unspotted — needs allied spotting or a player bombardment order'
    blocker = firing_blocker(battle,unit,target)
    if blocker:
        moving_clear = blocker.army == unit.army and attack_target(battle,unit) is target
        reason = 'Moving to clear friendly screen' if moving_clear else 'Line of sight blocked'
        return f'{reason}: {blocker.name} [#{blocker.id}]'
    if unit.combat_state == 'firing': return 'Volley fired; reloading'
    if unit.reload_left > 0: return f'Reloading: {unit.reload_left:.1f}s'
    if unit.stats.kind == UnitType.ARTILLERY: return 'Ready — artillery ignores line of sight'
    if sight.transmission<.9: return f'Partly obscured: {sight.transmission:.0%} effective visibility'
    return 'In range and clear line of sight'
