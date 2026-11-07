namespace Quiberon.Simulation;

public readonly record struct Visibility(bool Visible, double Transmission, double Vegetation, string Reason, int Samples = 0)
{
    public static Visibility Clear => new(true,1,0,"clear");
    public string State => !Visible ? "hidden" : Transmission<.9 ? "obscured" : "clear";
}

/// <summary>Exact-endpoint cache shared by orders, targeting, fire and inspection.</summary>
public sealed class VisibilityService(TerrainMap terrain, CombatMetrics metrics)
{
    private readonly Dictionary<(Vec2 From,Vec2 To,double Opacity),Visibility> cache=new();
    public int CachedCount => cache.Count;
    public Visibility Query(Vec2 from, Vec2 to,double opacity=1)
    {
        metrics.VisibilityQueries++;
        if(!terrain.Environment.InVisibility(from,to))return new(false,0,0,"fog"); // Range reject before cache allocation or terrain sampling.
        if(cache.TryGetValue((from,to,opacity),out var sight)) return sight;
        sight=terrain.Visibility(from,to,opacity); metrics.VisibilityCalculations++;metrics.VisibilitySamples+=sight.Samples;
        if(cache.Count>=32768)cache.Clear();
        cache[(from,to,opacity)]=sight;return sight;
    }
}
