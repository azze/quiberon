namespace Quiberon.Simulation;

public readonly record struct Overlap(Regiment A, Regiment B, double FractionA, double FractionB);
public static class CongestionSystem
{
    public static void Update(IReadOnlyList<Regiment> units, Rules rules, List<Overlap> overlaps, double dt = 0)
    {
        overlaps.Clear();
        foreach (var u in units) { u.Congestion = 0; u.Impedance = 0; u.Disruption = 0; }
        foreach (var (a, b) in SpatialIndex.Candidates(units))
        {
            if (a.Army != b.Army || (a.Position - b.Position).Length >= a.Rect.Radius + b.Rect.Radius) continue;
            double area = OrientedRect.IntersectionArea(a.Rect, b.Rect);
            if (area <= 1e-8) continue;
            var va = a.Velocity ?? Vec2.Direction(a.Facing) * a.Speed; var vb = b.Velocity ?? Vec2.Direction(b.Facing) * b.Speed;
            double sa = va.Length, sb = vb.Length; bool ma = sa > .1, mb = sb > .1; double alignment = 1;
            if (ma && mb)
            {
                double cosine = Math.Clamp(va.Dot(vb) / (sa * sb), -1, 1), same = (1 + cosine) / 2;
                double low = a.Archetype.Category == UnitCategory.Cavalry && b.Archetype.Category == UnitCategory.Cavalry ? rules.CongestionCavalrySameDirection : rules.CongestionSameDirection;
                if(a.Archetype.Category==UnitCategory.Cavalry && b.Archetype.Category==UnitCategory.Cavalry && a.PursuitId is not null && a.PursuitId==b.PursuitId && cosine>.8)low=rules.CongestionSharedPursuit;
                alignment = Math.Clamp(1 - same * (1 - low) + rules.CongestionOvertaking * same * Math.Abs(sa - sb) / Math.Max(sa, sb), 0, 1);
            }
            double fa = Math.Min(1, area / (a.Width * a.Depth)), fb = Math.Min(1, area / (b.Width * b.Depth));
            overlaps.Add(new(a, b, fa, fb));
            Apply(a, fa, ma); Apply(b, fb, mb);
            void Apply(Regiment u, double fraction, bool moving)
            {
                u.Congestion = Math.Max(u.Congestion, fraction); u.Impedance = Math.Max(u.Impedance, fraction * alignment);
                double loss = !ma && !mb ? 0 : fraction * alignment * (moving ? 1 : rules.CongestionStationaryLoss);
                u.Disruption = Math.Max(u.Disruption, loss);
            }
        }
        foreach (var u in units)
        {
            var profile = Formations.Get(u.Formation);
            u.CongestionSpeed = Math.Max(rules.CongestionMinSpeed, 1 - profile.CongestionSpeed * u.Impedance);
            u.CongestionLoss = profile.CongestionLoss * u.Disruption * (u.CommandersEnabled?SpecialistSystem.Manoeuvre(u)*CommanderSystem.PursuitLoss(u):1);
            u.Cohesion = Math.Max(0, u.Cohesion - u.CongestionLoss * dt);
        }
    }
}
