namespace Quiberon.Simulation;

/// <summary>Eight bounded escape rays; stable order and no RNG/pathfinding.</summary>
public static class RoutingSystem
{
    private static readonly double[] offsets = [0, -Math.PI / 4, Math.PI / 4, -Math.PI / 2, Math.PI / 2, -3 * Math.PI / 4, 3 * Math.PI / 4, Math.PI];
    public static Vec2? Destination(BattleSimulation battle, Regiment u)
    {
        var r = battle.Rules; var home = new Vec2(u.Army == 0 ? -1 : 1, 0);
        if (u.RoutHeading is null)
        { u.TransitionLeft = 0; u.NextFormation = null; u.SettlingGoal = null; u.SettlingFacing = null; }
        if (u.RoutHeading is null || battle.Time >= u.RoutNextPlan)
        {
            var threats = new List<(Regiment Unit, double Distance, double Weight)>();
            foreach (var enemy in battle.Combat.Nearby(u.Position, r.RoutThreatRadius))
            {
                if (enemy.Army == u.Army || !enemy.Effective) continue;
                double distance = (enemy.Position - u.Position).Length;
                if (distance > r.RoutThreatRadius || distance > 60 && !battle.Perceives(u, enemy)) continue;
                double weight = .5 + .5 * Math.Min(1, enemy.Strength / (double)Math.Max(1, enemy.MaximumStrength));
                if (enemy.Archetype.Category == UnitCategory.Cavalry) weight *= 1.5;
                threats.Add((enemy, distance, weight));
            }
            var heading = u.RoutHeading ?? home;
            if (threats.Count > 0)
            {
                var away = Vec2.Zero; double baseline = 0;
                foreach (var (enemy, distance, weight) in threats)
                {
                    away += (u.Position - enemy.Position).Normalized * (weight / Math.Pow(Math.Max(10, distance), 2));
                    baseline += weight / Math.Max(8, distance);
                }
                if (away.Length < 1e-9)
                {
                    var closest = threats.OrderBy(t => t.Distance).ThenBy(t => t.Unit.Id).First().Unit;
                    away = (u.Position - closest.Position).Normalized; if (away.Length < 1e-9) away = home;
                }
                double angle = Vec2.AngleTo(Vec2.Zero, away), best = double.NegativeInfinity;
                foreach (double offset in offsets)
                {
                    var step = Vec2.Direction(angle + offset); var point = u.Position + step * r.RoutLookahead;
                    var middle = (u.Position + point) * .5; double risk = 0; bool blocked = false;
                    foreach (var (enemy, _, weight) in threats)
                    {
                        risk += weight * (1 / Math.Max(8, (point - enemy.Position).Length) + .5 / Math.Max(8, (middle - enemy.Position).Length));
                        if (OrientedRect.Segment(u.Position, point, enemy.Rect) is { } entry && entry > 1e-6) blocked = true;
                    }
                    double persistence = u.RoutHeading is { } old ? .08 * step.Dot(old) : 0;
                    double score = (1.5 * baseline - risk) / baseline + persistence + .02 * step.Dot(home) - (blocked ? 2 : 0);
                    if (score > best) { best = score; heading = step; }
                }
            }
            u.RoutHeading = heading; u.RoutNextPlan = battle.Time + r.RoutPlanSeconds;
            u.StateReason = threats.Count > 0 ? "Routing: escape nearby danger" : "Routing: continue escape";
        }
        var direction = u.RoutHeading.Value; double minX = double.PositiveInfinity, minY = minX, maxX = double.NegativeInfinity, maxY = maxX;
        for (int i = 0; i < 4; i++) { var p = u.Rect.Corner(i); minX = Math.Min(minX, p.X); minY = Math.Min(minY, p.Y); maxX = Math.Max(maxX, p.X); maxY = Math.Max(maxY, p.Y); }
        bool exits = direction.X < -.25 && minX <= r.RoutExitMargin || direction.X > .25 && maxX >= r.Width - r.RoutExitMargin ||
            direction.Y < -.25 && minY <= r.RoutExitMargin || direction.Y > .25 && maxY >= r.Height - r.RoutExitMargin;
        if (exits)
        {
            u.Withdrawn = true; battle.Metrics.Escapes++; u.StateReason = "Escaped while routing";
            battle.Emit("withdraw", u, null, u.Position, 3, 0, $"{u.Name} escaped the battlefield with {u.Strength} survivors"); return null;
        }
        return u.Position + direction * r.RoutLookahead;
    }
}
