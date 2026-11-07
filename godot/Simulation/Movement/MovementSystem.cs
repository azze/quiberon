namespace Quiberon.Simulation;

/// <summary>Movement.py translation with shared charge, commander and terrain modifier hooks.</summary>
public static class MovementSystem
{
    public static void ClampToField(Regiment unit, Rules rules)
    {
        var box = unit.Rect; double minX = double.PositiveInfinity, minY = minX, maxX = double.NegativeInfinity, maxY = maxX;
        for (int i = 0; i < 4; i++) { var p = box.Corner(i); minX = Math.Min(minX, p.X); minY = Math.Min(minY, p.Y); maxX = Math.Max(maxX, p.X); maxY = Math.Max(maxY, p.Y); }
        unit.Position += new Vec2(Math.Max(0, -minX) - Math.Max(0, maxX - rules.Width), Math.Max(0, -minY) - Math.Max(0, maxY - rules.Height));
    }
    public static void TurnTo(Regiment unit, double facing, double multiplier=1)
    {
        double limit = unit.Archetype.TurnRate * Formations.Get(unit.Formation).Turn * Rules.Dt * multiplier;
        double turn = Math.Clamp(Vec2.AngleDelta(unit.Facing, facing), -limit, limit);
        unit.Facing += turn; unit.Cohesion = Math.Max(0, unit.Cohesion - Math.Abs(turn) * .6 * SpecialistSystem.Manoeuvre(unit));
    }
    public static void Move(Regiment unit, Vec2? destination, Rules rules, TerrainMap terrain, double? arrivalFacing,
        double? speedCap=null,double? acceleration=null,double turnMultiplier=1,double? followSpeed=null)
    {
        double previousSpeed=unit.Speed;
        unit.Speed = 0; unit.Velocity = Vec2.Zero; unit.TerrainLoss = 0; unit.TerrainSpeed = 1;
        if (!terrain.Empty)
        {
            var stationary = terrain.MovementEffect(unit, Vec2.Zero);
            unit.ForestCover = stationary.Forest; unit.GroundSlope = stationary.Slope; unit.TerrainSpeed = stationary.Speed;
        }
        if (unit.TransitionLeft > 0)
        {
            unit.TransitionLeft = Math.Max(0, unit.TransitionLeft - Rules.Dt);
            if (unit.TransitionLeft == 0) {if(unit.TransitTarget is { } compact){unit.TransitCompact=compact;unit.TransitTarget=null;}else if(unit.NextFormation is { } next){unit.Formation=next;unit.NextFormation=null;} }
            return;
        }
        if (unit.Archetype.Category == UnitCategory.Artillery)
        {
            bool travelling = destination is { } dest && (dest - unit.Position).Length >= 1;
            if (travelling)
            {
                if (!unit.Limbered) { unit.Limbered = true; unit.LimberLeft = unit.Archetype.LimberSeconds*CommanderSystem.Redeploy(unit); }
                unit.SetupLeft = unit.Archetype.SetupSeconds*CommanderSystem.Redeploy(unit);
                unit.LimberLeft = Math.Max(0, unit.LimberLeft - Rules.Dt);
                if (unit.LimberLeft > 0) return;
            }
            else { unit.LimberLeft = 0; unit.SetupLeft = Math.Max(0, unit.SetupLeft - Rules.Dt); if (unit.SetupLeft == 0) unit.Limbered = false; }
        }
        if (destination is not { } goal) return;
        var offset = goal - unit.Position;
        if (offset.Length < 1)
        {
            if (arrivalFacing is { } angle) { TurnTo(unit, angle); ClampToField(unit, rules); }
            return;
        }
        double delta = Vec2.AngleDelta(unit.Facing, Vec2.AngleTo(unit.Position, goal));
        var profile = Formations.Get(unit.Formation);
        TurnTo(unit, Vec2.AngleTo(unit.Position, goal),turnMultiplier);
        double penalty=rules.MoraleEnabled && unit.State is MoraleState.Shaken or MoraleState.Wavering?.65:1;
        unit.Speed = (speedCap??unit.Archetype.Speed * profile.Speed) * Math.Max(0, Math.Cos(delta)) * penalty * (1 - unit.Fatigue * .003) * unit.CongestionSpeed;
        unit.Speed*=CommanderSystem.Advance(unit);
        unit.Speed *= Math.Min(1, offset.Length * unit.Archetype.TurnRate * profile.Turn / Math.Max(.1, unit.Archetype.Speed * profile.Speed));
        var effect = terrain.MovementEffect(unit, Vec2.Direction(unit.Facing));
        unit.TerrainSpeed = effect.Speed; unit.Speed *= effect.Speed;
        if(acceleration is { } gain)unit.Speed=Math.Min(unit.Speed,previousSpeed+gain*Rules.Dt);
        if(followSpeed is { } limit)unit.Speed=Math.Min(unit.Speed,limit);
        var before = unit.Position;
        unit.Position += Vec2.Direction(unit.Facing) * Math.Min(offset.Length, unit.Speed * Rules.Dt);
        unit.Fatigue = Math.Min(100, unit.Fatigue + Rules.Dt * .025);
        ClampToField(unit, rules); unit.Velocity = (unit.Position - before) / Rules.Dt;
        if (!terrain.Empty)
        {
            unit.TerrainLoss = effect.LossPerMetre * (unit.Position - before).Length / Rules.Dt;
            unit.Cohesion = Math.Max(0, unit.Cohesion - unit.TerrainLoss * Rules.Dt);
        }
    }
    public static void ResetAvoidance(Regiment unit)
    {
        unit.TerrainWaypoint = null; unit.TerrainDestination = null; unit.TerrainRouteUsed = false;
        unit.AvoidanceGoal = null; unit.AvoidanceDestination = null; unit.AvoidanceLeft = 0; unit.AvoidanceUsed = false;
    }
    public static Vec2? AvoidFriends(Regiment unit, Vec2? destination, IReadOnlyList<Regiment> units, Rules rules, IReadOnlyDictionary<int, Vec2?> intents)
    {
        if (destination is not { } goal || !rules.AvoidanceEnabled || unit.Order.Kind is not (OrderKind.Move or OrderKind.Advance or OrderKind.Defend)) { unit.AvoidanceGoal = null; return destination; }
        if (unit.AvoidanceDestination is null || (goal - unit.AvoidanceDestination.Value).Length > 20) { ResetAvoidance(unit); unit.AvoidanceDestination = goal; }
        if (unit.AvoidanceGoal is { } waypoint)
        {
            unit.AvoidanceLeft -= Rules.Dt;
            if (unit.AvoidanceLeft > 0 && unit.Congestion < .01 && (waypoint - unit.Position).Length > 4) return waypoint;
            unit.AvoidanceGoal = null;
        }
        if (unit.AvoidanceUsed) return goal;
        var delta = goal - unit.Position;
        if (delta.Length < 1) return goal;
        double radius = unit.Rect.Radius; var forward = delta.Normalized; var side = new Vec2(-forward.Y, forward.X);
        var ahead = unit.Position + forward * Math.Min(rules.AvoidanceLookahead, delta.Length);
        Regiment? obstacle = null; double first = double.PositiveInfinity;
        foreach (var other in units)
        {
            if (other.Id == unit.Id || other.Army != unit.Army) continue;
            if (OrientedRect.Segment(unit.Position, ahead, other.Rect, radius) is not { } t) continue;
            if (t < first || (t == first && other.Id < obstacle!.Id)) { first = t; obstacle = other; }
        }
        if (obstacle is null) return goal;
        unit.AvoidanceUsed = true;
        if (unit.Congestion > .01) return goal;
        if ((intents[obstacle.Id] is { } intent && (intent - obstacle.Position).Length > 1) || obstacle.Speed > .1) return goal;
        double along = 0;
        for (int i = 0; i < 4; i++) along += (obstacle.Rect.Corner(i) - unit.Position).Dot(forward) / 4;
        if (along <= 0) return goal;
        Vec2? best = null; double bestLength = double.PositiveInfinity;
        foreach (int sign in new[] { 1, -1 })
        {
            double edge = double.NegativeInfinity;
            for (int i = 0; i < 4; i++) edge = Math.Max(edge, sign * (obstacle.Rect.Corner(i) - unit.Position).Dot(side));
            double offset = sign * (Math.Max(0, edge) + radius + rules.AvoidanceMargin) * 1.5;
            var point = unit.Position + forward * along + side * offset;
            double length = (point - unit.Position).Length + (goal - point).Length;
            if (length > delta.Length + rules.AvoidanceMaxExtra || length > delta.Length * rules.AvoidanceMaxRatio) continue;
            if (!InCircleBounds(unit.Position, radius, rules) || !InCircleBounds(point, radius, rules) || !InCircleBounds(goal, radius, rules)) continue;
            if (units.Any(other => other.Id != unit.Id && (OrientedRect.Segment(unit.Position, point, other.Rect, radius) is not null || OrientedRect.Segment(point, goal, other.Rect, radius) is not null))) continue;
            if (length < bestLength) { bestLength = length; best = point; }
        }
        if (best is { } choice) { unit.AvoidanceGoal = choice; unit.AvoidanceLeft = rules.AvoidanceMaxSeconds; return choice; }
        return goal;
    }
    internal static bool InCircleBounds(Vec2 point, double radius, Rules rules) => radius <= point.X && point.X <= rules.Width - radius && radius <= point.Y && point.Y <= rules.Height - radius;
    public static Vec2? TerrainSteer(BattleSimulation battle, Regiment unit, Vec2? destination)
    {
        var terrain = battle.Terrain;
        if (terrain.Empty || destination is null || unit.AvoidanceGoal is not null) { unit.TerrainWaypoint = null; return destination; }
        double aversion = TerrainMap.Profile(unit.Archetype.Category).RouteAversion;
        if (aversion == 0) return destination;
        var goal = destination.Value;
        if (unit.TerrainDestination is null || (goal - unit.TerrainDestination.Value).Length > 30) { unit.TerrainDestination = goal; unit.TerrainRouteUsed = false; unit.TerrainWaypoint = null; }
        if (unit.TerrainWaypoint is { } previous)
        {
            unit.TerrainRouteLeft -= Rules.Dt;
            if (unit.TerrainRouteLeft > 0 && (previous - unit.Position).Length > 5) return previous;
            unit.TerrainWaypoint = null;
        }
        if (unit.TerrainRouteUsed) return goal;
        double distance = (goal - unit.Position).Length;
        if (distance < 80) return goal;
        unit.TerrainRouteUsed = true;
        double Cost(Vec2 a, Vec2 b)
        {
            var delta = b - a; double length = delta.Length, difficulty = 0; int samples = Math.Min(20, Math.Max(3, (int)Math.Ceiling(length / 25)));
            for (int i = 0; i < samples; i++) { var p = a + delta * ((i + .5) / samples); difficulty += terrain.ForestDensity(p) * 2 + terrain.Gradient(p).Length * 5; }
            return length * (1 + aversion * difficulty / samples);
        }
        double direct = Cost(unit.Position, goal), best = double.PositiveInfinity; Vec2? choice = null;
        var forward = (goal - unit.Position).Normalized; var side = new Vec2(-forward.Y, forward.X); double radius = unit.Rect.Radius;
        foreach (int sign in new[] { 1, -1 })
        {
            var p = unit.Position + forward * Math.Min(100, distance / 2) + side * (sign * Math.Min(130, distance * .35));
            double length = (p - unit.Position).Length + (goal - p).Length;
            if (length > distance * 1.4 || length > distance + 100 || !InCircleBounds(p, radius, battle.Rules)) continue;
            if (battle.Units.Any(other => other.Active && other.Army != unit.Army && (OrientedRect.Segment(unit.Position, p, other.Rect, radius) is not null || OrientedRect.Segment(p, goal, other.Rect, radius) is not null))) continue;
            double value = Cost(unit.Position, p) + Cost(p, goal);
            if (value < direct * .85 && value < best) { best = value; choice = p; }
        }
        if (choice is { } selected) { unit.TerrainWaypoint = selected; unit.TerrainRouteLeft = 120; return selected; }
        return goal;
    }
    public static void SeparateEnemies(IReadOnlyList<Regiment> units, Rules rules)
    {
        // Original mutable, stable pair traversal: a new index would go stale.
        for (int pass = 0; pass < 3; pass++)
        {
            for (int i = 0; i < units.Count; i++) for (int j = i + 1; j < units.Count; j++)
            {
                var a = units[i]; var b = units[j];
                if (a.Army == b.Army || OrientedRect.Separation(a.Rect, b.Rect) is not { } delta) continue;
                var correction = delta.Normalized * Math.Min(delta.Length / 2 + .01, .6);
                a.Position += correction; b.Position -= correction; a.EnemyContact = b.EnemyContact = true;
            }
            foreach (var unit in units) ClampToField(unit, rules);
        }
    }
}
