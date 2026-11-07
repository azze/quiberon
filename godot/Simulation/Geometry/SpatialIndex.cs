namespace Quiberon.Simulation;

/// <summary>Conservative 100 m cells. Results retain original list order.</summary>
public sealed class SpatialIndex
{
    private readonly IReadOnlyList<Regiment> units;
    private readonly Dictionary<(int X, int Y), List<int>> cells = new();
    private const double Size = 100;
    public SpatialIndex(IReadOnlyList<Regiment> units, double padding = 0)
    {
        this.units = units;
        for (int i = 0; i < units.Count; i++)
        {
            var p = units[i].Position; double r = units[i].Rect.Radius + padding + 1e-8;
            foreach (var key in Cells(p.X - r, p.Y - r, p.X + r, p.Y + r))
            { if (!cells.TryGetValue(key, out var items)) cells[key] = items = new(); items.Add(i); }
        }
    }
    private static IEnumerable<(int, int)> Cells(double left, double top, double right, double bottom)
    {
        for (int x = (int)Math.Floor(left / Size); x <= (int)Math.Floor(right / Size); x++)
            for (int y = (int)Math.Floor(top / Size); y <= (int)Math.Floor(bottom / Size); y++) yield return (x, y);
    }
    public IEnumerable<(Regiment A, Regiment B)> Pairs()
    {
        var found = new HashSet<long>();
        foreach (var items in cells.Values)
            for (int i = 0; i < items.Count; i++) for (int j = i + 1; j < items.Count; j++) found.Add(((long)items[i] << 32) | (uint)items[j]);
        var ordered = found.ToArray(); Array.Sort(ordered);
        foreach (long key in ordered) yield return (units[(int)(key >> 32)], units[(int)(key & uint.MaxValue)]);
    }
    public IEnumerable<Regiment> Segment(Vec2 start, Vec2 end, double padding = 0)
    {
        var found = new HashSet<int>();
        foreach (var key in Cells(Math.Min(start.X, end.X) - padding, Math.Min(start.Y, end.Y) - padding, Math.Max(start.X, end.X) + padding, Math.Max(start.Y, end.Y) + padding))
            if (cells.TryGetValue(key, out var items)) foreach (int i in items) found.Add(i);
        var ordered = found.ToArray(); Array.Sort(ordered);
        foreach (int i in ordered) yield return units[i];
    }
    public static IEnumerable<(Regiment A, Regiment B)> Candidates(IReadOnlyList<Regiment> units, double padding = 0)
    {
        if (units.Count >= 12) return new SpatialIndex(units,padding).Pairs();
        return AllPairs(units);
    }
    private static IEnumerable<(Regiment, Regiment)> AllPairs(IReadOnlyList<Regiment> units)
    { for (int i = 0; i < units.Count; i++) for (int j = i + 1; j < units.Count; j++) yield return (units[i], units[j]); }
}
