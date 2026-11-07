namespace Quiberon.Simulation;

public enum WeatherType { Clear, Rain, Fog }
public enum CrossingKind { Bridge, Ford }
public enum FordDepth { Shallow, Moderate }
public enum RoadSurface { MainRoad, Track }
public enum DefenceKind { Earthwork, Barricade }
public sealed record WeatherDefinition(WeatherType Type=WeatherType.Clear,double VisibilityLimit=180,
    double InfantryWetSpeed=.90,double CavalryWetSpeed=.88,double ArtilleryWetSpeed=.80,
    double FirearmReload=1.08,double ArtilleryReload=1.03,double WetDisorder=1.12);
public sealed record RiverDefinition(string Id,string Name,IReadOnlyList<Vec2> Points,double Width=50,double WaterHeight=-.4,double Depth=2);
public sealed record CrossingDefinition(string Id,string RiverId,Vec2 Position,double Facing,double Length,double Width,
    CrossingKind Kind=CrossingKind.Bridge,IReadOnlyList<UnitCategory>? Permitted=null,FordDepth FordDepth=FordDepth.Moderate,
    double? Speed=null,double CohesionPerMetre=.10,double? SurfaceHeight=null);
public sealed record RoadDefinition(string Id,string Name,IReadOnlyList<Vec2> Points,double Width=8,RoadSurface Surface=RoadSurface.MainRoad,double Multiplier=1);
public sealed record DefenceDefinition(string Id,Vec2 Position,double Facing,double Width=80,double Depth=3,
    DefenceKind Kind=DefenceKind.Earthwork,double MusketExposure=.70,double ChargeResistance=.65,double ProtectionDepth=24);
public sealed record EnvironmentDefinition(int Version=1,RiverDefinition[]? Rivers=null,CrossingDefinition[]? Crossings=null,
    RoadDefinition[]? Roads=null,DefenceDefinition[]? Defences=null,WeatherDefinition? Weather=null);

public sealed record CrossingGeometry(CrossingDefinition Definition,OrientedRect Rect,Vec2 Entry,Vec2 Exit,double SurfaceHeight)
{
    public bool Permits(UnitCategory category)=>Definition.Permitted?.Contains(category)??(Definition.Kind==CrossingKind.Bridge || category!=UnitCategory.Artillery || Definition.FordDepth==FordDepth.Shallow);
    public Vec2 Direction=>Rect.Forward;
    public double Speed=>Definition.Speed??(Definition.Kind==CrossingKind.Bridge?.85:.45);
}
public sealed record WaterPolygon(string RiverId,IReadOnlyList<Vec2> Points,double Height);
