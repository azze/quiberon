namespace Quiberon.Simulation;

/// <summary>Stable priorities and bounded alternate positions, without rewriting orders.</summary>
public static class SeparationSystem
{
    public static void Reset(Regiment u)
    {
        u.SettlingGoal = null; u.SettlingFacing = null; u.PositionPreference = null; u.PositionKey = null;
        u.StationaryOverlap = 0; u.SettlingRetryAt = 0;
    }
    private static (int, double, int) Priority(Regiment u) => (u.PlayerOrder && u.Order.Kind == OrderKind.Hold ? 4 : u.Order.Kind is OrderKind.Hold or OrderKind.Reserve ? 3 : u.CombatState==CombatState.Firing?2:1, u.RestTime, -u.Id);
    private static bool Eligible(Regiment u, Vec2? intent)
    {
        if (!u.Effective || u.TransitionLeft > 0 || u.CombatState==CombatState.Melee) return false;
        if (u.Order.Kind is not (OrderKind.Hold or OrderKind.Reserve or OrderKind.Defend or OrderKind.Move or OrderKind.Advance)) return false;
        if (u.Order.Kind == OrderKind.Advance) return intent is null;
        return intent is null || (intent.Value - u.Position).Length < 12 || u.SettlingGoal is not null;
    }
    public static void Settle(BattleSimulation battle, IReadOnlyList<Regiment> units, Dictionary<int, Vec2?> intents, IReadOnlyList<Overlap> overlaps)
    {
        var allowed = new Dictionary<int, bool>(units.Count);
        foreach (var u in units)
        {
            u.RestTime = u.Speed < .1 ? u.RestTime + Rules.Dt : 0;
            var key = (u.Order.Kind, u.Order.Kind is OrderKind.Move or OrderKind.Defend ? u.Order.Destination : null, u.Order.Facing);
            if (u.PositionKey != key) { Reset(u); u.PositionKey = key; }
            allowed[u.Id] = Eligible(u, intents[u.Id]);
            if (!allowed[u.Id]) { u.SettlingGoal = null; u.SettlingFacing = null; u.StationaryOverlap = 0; }
        }
        var losers = new HashSet<int>(); var blocked = new HashSet<int>();
        foreach (var pair in overlaps)
        {
            var a = pair.A; var b = pair.B;
            if (Math.Min(pair.FractionA, pair.FractionB) < battle.Rules.SettlingOverlap || !allowed[a.Id] || !allowed[b.Id]) continue;
            blocked.Add(a.Id); blocked.Add(b.Id);
            losers.Add(Priority(a).CompareTo(Priority(b)) >= 0 ? b.Id : a.Id);
        }
        foreach (var u in units) u.StationaryOverlap = blocked.Contains(u.Id) ? u.StationaryOverlap + Rules.Dt : 0;
        var planning = new List<Regiment>();
        foreach (var u in units)
        {
            if (!allowed[u.Id]) continue;
            if (u.SettlingGoal is { } goal)
            {
                if (battle.Time - u.SettlingStarted > battle.Rules.SettlingTimeout && (u.Position - goal).Length > 1)
                { u.SettlingGoal = null; u.SettlingFacing = null; u.SettlingRetryAt = battle.Time + battle.Rules.SettlingRetry; }
                else { intents[u.Id] = goal; continue; }
            }
            if (!losers.Contains(u.Id) || u.StationaryOverlap < battle.Rules.SettlingDelay || battle.Time < u.SettlingRetryAt) continue;
            planning.Add(u);
        }
        if (planning.Count == 0) return;
        var index = new SpatialIndex(units);
        foreach (var u in planning.OrderByDescending(Priority))
        {
            u.PositionPreference = u.Order.Kind is OrderKind.Move or OrderKind.Defend ? u.Order.Destination : u.Position;
            var point = Alternative(battle, u, units, index);
            u.SettlingRetryAt = battle.Time + battle.Rules.SettlingRetry;
            if (point is null) continue;
            u.SettlingGoal = point; u.SettlingFacing = u.Order.Facing ?? u.Facing; u.SettlingStarted = battle.Time; intents[u.Id] = point;
        }
    }
    private static Vec2? Alternative(BattleSimulation battle, Regiment u, IReadOnlyList<Regiment> units, SpatialIndex index)
    {
        var rules = battle.Rules; double facing = u.Order.Facing ?? u.Facing, radius = u.Rect.Radius + 1;
        Vec2? best = null; double score = double.PositiveInfinity;
        foreach (double distance in new[] { Math.Max(u.Depth + rules.SettlingGap, 18), u.Width + rules.SettlingGap, rules.SettlingRadius })
        {
            if (distance > rules.SettlingRadius) continue;
            foreach (double angle in new[] { 0, Math.PI, Math.PI / 2, -Math.PI / 2, Math.PI / 4, -Math.PI / 4, 3 * Math.PI / 4, -3 * Math.PI / 4 })
            {
                var point = u.Position + Vec2.Direction(facing + angle) * distance; var preference = u.PositionPreference ?? u.Position;
                if ((point - preference).Length > rules.SettlingRadius || !MovementSystem.InCircleBounds(point, radius, rules)) continue;
                var clearance = new OrientedRect(point, facing, u.Width + 2 * rules.SettlingGap, u.Depth + 2 * rules.SettlingGap);
                if (index.Segment(point, point, radius + 2 * rules.SettlingGap).Any(other => other.Id != u.Id && OrientedRect.Separation(clearance, other.Rect) is not null)) continue;
                if (units.Any(other => other.Id != u.Id && other.SettlingGoal is { } goal && OrientedRect.Separation(clearance, new OrientedRect(goal, other.SettlingFacing ?? other.Facing, other.Width, other.Depth)) is not null)) continue;
                if (index.Segment(u.Position, point, radius).Any(other => other.Army != u.Army && OrientedRect.Segment(u.Position, point, other.Rect, radius) is not null)) continue;
                if(!battle.Terrain.Environment.Passable(clearance,u.Archetype.Category) || !battle.Terrain.Environment.Swept(u.Rect,clearance,u.Archetype.Category))continue;
                double difficulty = battle.Terrain.Empty ? 0 : battle.Terrain.ForestDensity(point) * 2 + battle.Terrain.Gradient(point).Length * 4;
                double value = (point - preference).Length + difficulty;
                if (value < score) { score = value; best = point; }
            }
        }
        return best;
    }
}
