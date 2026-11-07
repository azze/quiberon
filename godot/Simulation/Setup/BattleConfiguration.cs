using System.Text.Json;
namespace Quiberon.Simulation;

/// <summary>Version-1 Python-compatible battle recipes, independent of campaign and Godot.</summary>
public sealed record BattleConfiguration
{
    public string Name { get; init; } = "Custom battle";
    public double Width { get; init; } = 1000;
    public double Height { get; init; } = 600;
    public long Seed { get; init; } = 17;
    public long CommanderSeed { get; init; } = 1729;
    public int CommanderRoll { get; init; }
    public bool Symmetric { get; init; } = true;
    public int MaxPerType { get; init; } = 12;
    public int MaxTotal { get; init; } = 48;
    public Dictionary<string,int> Blue { get; init; } = new() { ["infantry"]=4,["cavalry"]=1,["artillery"]=1 };
    public Dictionary<string,int> Red { get; init; } = new() { ["infantry"]=4,["cavalry"]=1,["artillery"]=1 };
    public int[] AiArmies { get; init; } = [1];
    public string[] AiStrategies { get; init; } = ["balanced","balanced"];
    public string TerrainPreset { get; init; } = "Open Field";
    public long TerrainSeed { get; init; } = 17;
    public TerrainDefinition? Terrain { get; init; }
    public UnitDefinition[] Placements { get; init; } = [];
    public ArmyCommanderAssignment[] ArmyCommanders { get; init; } = [];
    public static readonly string[] TerrainPresets = ["Open Field","Central Hill","Rolling Hills","Ridge Defence","Wooded Battlefield","Mixed Terrain"];
    public IReadOnlyDictionary<string,int> Army(int army) => army == 0 ? Blue : Red;
    public static BattleConfiguration FromScenario(ScenarioDefinition s) => new BattleConfiguration {
        Name=s.Name,Width=s.Width,Height=s.Height,Seed=s.Seed,CommanderSeed=s.CommanderSeed,Symmetric=false,MaxTotal=256,MaxPerType=64,
        Blue=s.Units.Where(u=>u.Army==0).GroupBy(u=>u.Archetype).ToDictionary(g=>g.Key,g=>g.Count()),
        Red=s.Units.Where(u=>u.Army==1).GroupBy(u=>u.Archetype).ToDictionary(g=>g.Key,g=>g.Count()),
        Placements=s.Units,ArmyCommanders=s.ArmyCommanders,Terrain=s.Terrain,AiArmies=s.AiArmies,AiStrategies=[s.AiStrategies.GetValueOrDefault(0,"balanced"),s.AiStrategies.GetValueOrDefault(1,"balanced")]
    };
    public ScenarioDefinition Scenario() => new() {
        Name=Name,Width=Width,Height=Height,Seed=Seed,CommanderSeed=CommanderSeed,Units=Placements,ArmyCommanders=ArmyCommanders,Terrain=Terrain??GenerateTerrain(TerrainPreset,Width,Height,TerrainSeed),
        CombatEnabled=true,MoraleEnabled=true,CavalryEnabled=true,ArtilleryEnabled=true,SpecialistsEnabled=true,CommandersEnabled=true,AiEnabled=true,
        AiArmies=AiArmies,AiStrategies=new(){[0]=AiStrategies[0],[1]=AiStrategies[1]}
    };
    public void Validate(bool deployment=true)
    {
        if(string.IsNullOrWhiteSpace(Name) || Name.Length>100 || Name.Any(char.IsControl))throw new ArgumentException("Battle name must contain 1–100 printable characters.");
        if(!double.IsFinite(Width+Height) || Width<300 || Width>5000 || Height<240 || Height>3000)throw new ArgumentException("Battlefield dimensions must be 300–5000 × 240–3000 metres.");
        if(MaxTotal<2 || MaxTotal>256 || MaxPerType<1 || MaxPerType>64)throw new ArgumentException("Invalid regiment limits.");
        if(AiArmies.Distinct().Count()!=AiArmies.Length || AiArmies.Any(a=>a is <0 or >1) || AiStrategies.Length!=2 || AiStrategies.Any(s=>!TacticalAi.Strategies.Contains(s)))throw new ArgumentException("Invalid AI army or strategy.");
        foreach(var army in new[]{Blue,Red}) {
            if(army.Values.Sum()<1)throw new ArgumentException("Each army needs at least one regiment.");
            foreach(var (key,count) in army) { _=Archetypes.Get(key);if(count<0 || count>MaxPerType)throw new ArgumentException($"{key}: count must be 0–{MaxPerType}."); }
        }
        if(Blue.Values.Sum()+Red.Values.Sum()>MaxTotal)throw new ArgumentException($"Total regiment limit is {MaxTotal}.");
        if(Symmetric && Archetypes.All.Any(a=>Blue.GetValueOrDefault(a.Id)!=Red.GetValueOrDefault(a.Id)))throw new ArgumentException("Symmetric armies must have matching counts.");
        if(!TerrainPresets.Contains(TerrainPreset) && Terrain is null)throw new ArgumentException("Unknown terrain preset.");
        if(Terrain is { } t) {
            _=new BattleEnvironment(t.Environment);
            if(t.Hills.Length>256 || t.Forests.Length>256)throw new ArgumentException("At most 256 hills and 256 forests are supported.");
            foreach(var h in t.Hills)ValidateFeature(h.X,h.Y,h.RadiusX,h.RadiusY,h.Height,false);
            foreach(var f in t.Forests)ValidateFeature(f.X,f.Y,f.RadiusX,f.RadiusY,f.Density,true);
        }
        HistoricalCommanders.ValidateAssignments(Placements.Where(p=>p.Commander is not null).Select(p=>p.Commander!),ArmyCommanders,new[]{0,1});
        foreach(var a in ArmyCommanders)if(a.Position is { } hq && (hq.X<0 || hq.X>Width || hq.Y<0 || hq.Y>Height))throw new ArgumentException("Headquarters must be inside the battlefield.");
        if(!deployment && Placements.Length==0)return;
        if(Placements.Length!=Blue.Values.Sum()+Red.Values.Sum() || Placements.Select(p=>p.Id).Distinct().Count()!=Placements.Length)throw new ArgumentException("Deployment does not match the roster or repeats regiment IDs.");
        var officers=new HashSet<string>();var rectangles=new List<OrientedRect>();
        foreach(var p in Placements) {
            var a=Archetypes.Get(p.Archetype);
            if(p.Id<0 || p.Army is <0 or >1 || !p.Position.Finite || !double.IsFinite(p.Facing+p.Cohesion+p.Fatigue+(p.Morale??0)) || p.Cohesion is <0 or >100 || p.Fatigue is <0 or >100 || p.Morale is <0 or >100 || p.State!=MoraleState.Steady || p.SafeTime!=0)throw new ArgumentException("Invalid deployment state.");
            if(p.Strength is { } strength && (strength<1 || strength>a.Strength))throw new ArgumentException("Starting strength must be positive and no greater than maximum.");
            if(string.IsNullOrWhiteSpace(p.Name) || p.Name.Length>100 || p.Name.Any(char.IsControl))throw new ArgumentException("Regiment names must contain 1–100 printable characters.");
            if(p.Commander is { } c){CommanderSystem.Validate(c,a.Category);UpgradeSystem.Validate(c,a);if(!officers.Add(c.Id))throw new ArgumentException("Commander identities cannot be assigned twice.");}
            var u=new Regiment(p.Id,p.Army,p.Name,a,p.Position,p.Facing,p.Formation);var rect=u.Rect;
            if(!new BattleEnvironment(Terrain?.Environment).Passable(rect,a.Category))throw new ArgumentException($"{p.Name}: deployment footprint overlaps impassable water.");
            for(int i=0;i<4;i++){var corner=rect.Corner(i);if(corner.X<ZoneLeft(p.Army)-1e-7 || corner.X>ZoneRight(p.Army)+1e-7 || corner.Y<20-1e-7 || corner.Y>Height-20+1e-7)throw new ArgumentException($"{p.Name}: footprint must stay inside its deployment zone.");}
            if(rectangles.Any(r=>OrientedRect.Separation(rect,r)is not null))throw new ArgumentException($"{p.Name}: starting formations overlap.");
            rectangles.Add(rect);
            if(p.Order is { } order) {
                if(order.Destination is { } goal && (!goal.Finite || goal.X<0 || goal.X>Width || goal.Y<0 || goal.Y>Height))throw new ArgumentException("Order destination must be inside the battlefield.");
                if(order.Kind is OrderKind.Move or OrderKind.Defend && order.Destination is null)throw new ArgumentException("Move/defend needs a destination.");
                if(order.Facing is { } angle && (!double.IsFinite(angle) || order.Destination is null || order.Kind is not (OrderKind.Move or OrderKind.Advance)))throw new ArgumentException("Arrival facing needs a movement destination.");
                if(order.Kind is OrderKind.Charge or OrderKind.Pursue && a.Category==UnitCategory.Artillery || order.Kind==OrderKind.Pursue && a.Category!=UnitCategory.Cavalry || order.Kind==OrderKind.Skirmish && !a.Formations.Contains(Formation.Skirmish))throw new ArgumentException("Order is incompatible with this regiment.");
                if(order.ViaCrossing is { } via && Terrain?.Environment?.Crossings?.Any(c=>c.Id==via)!=true)throw new ArgumentException("Unknown movement crossing.");
                if(order.TargetId is { } id && !Placements.Any(q=>q.Id==id && q.Army!=p.Army))throw new ArgumentException("Order target must identify an enemy regiment.");
            }
        }
        foreach(int side in new[]{0,1})foreach(var a in Archetypes.All)
            if(Placements.Count(p=>p.Army==side && p.Archetype==a.Id)!=Army(side).GetValueOrDefault(a.Id))throw new ArgumentException("Deployment does not match army composition.");
        void ValidateFeature(double x,double y,double rx,double ry,double value,bool forest) {
            if(!double.IsFinite(x+y+rx+ry+value) || x<0 || x>Width || y<0 || y>Height || rx<1 || rx>Width*2 || ry<1 || ry>Height*2 || (forest?value<0 || value>1:Math.Abs(value)>200))throw new ArgumentException("Invalid terrain feature.");
        }
    }
    public double ZoneLeft(int army)=>army==0?20:Width*.68;
    public double ZoneRight(int army)=>army==0?Width*.32:Width-20;
    public BattleConfiguration Prepare()
    {
        Validate(false);
        var ready=this with {Terrain=Terrain??GenerateTerrain(TerrainPreset,Width,Height,TerrainSeed)};
        if(ready.Placements.Length==0)ready=ready with {Placements=ready.AutomaticDeployment()};
        ready.Validate();
        var battle=ready.Scenario().Create();
        return ready with {Placements=ready.Placements.Select(p=>p with{Commander=battle.Unit(p.Id)!.Commander}).ToArray()};
    }
    public UnitDefinition[] AutomaticDeployment()
    {
        var placements=new List<UnitDefinition>();var terrain=new TerrainMap(Terrain?.Hills,Terrain?.Forests);
        foreach(int army in new[]{0,1}) {
            var ys=new List<double>();for(double y=59;y<=Height-59;y+=90)ys.Add(y);
            var xs=new List<double>();for(double x=army==0?ZoneRight(army)-18:ZoneLeft(army)+18;x>=ZoneLeft(army)+18 && x<=ZoneRight(army)-18;x+=army==0?-56:56)xs.Add(x);
            var cells=(from x in Enumerable.Range(0,xs.Count) from y in Enumerable.Range(0,ys.Count) select (X:x,Y:y)).ToList();
            if(Army(army).Values.Sum()>cells.Count)throw new ArgumentException($"{(army==0?"Blue":"Red")} army cannot fit its deployment zone. Reduce counts or enlarge the battlefield.");
            var infantryRows=new HashSet<int>();
            foreach(var a in Archetypes.All.Where(a=>Army(army).GetValueOrDefault(a.Id)>0).OrderBy(a=>a.Category).ThenBy(a=>UpgradeSystem.Role(a) is "skirmisher" or "rifles"))
            for(int n=0;n<Army(army).GetValueOrDefault(a.Id);n++) {
                var cell=cells.OrderBy(c=>a.Category==UnitCategory.Artillery?terrain.ForestDensity(new(xs[c.X],ys[c.Y]))*5+terrain.Gradient(new(xs[c.X],ys[c.Y])).Length*8:0)
                    .ThenBy(c=>a.Category==UnitCategory.Artillery?Math.Abs(c.X-(infantryRows.Count>0?1:0)):c.X)
                    .ThenBy(c=>a.Category==UnitCategory.Artillery && infantryRows.Contains(c.Y)?1:0)
                    .ThenBy(c=>a.Category==UnitCategory.Cavalry || UpgradeSystem.Role(a) is "skirmisher" or "rifles"?-Math.Abs(ys[c.Y]-Height/2):Math.Abs(ys[c.Y]-Height/2)).ThenBy(c=>c.Y).First();
                cells.Remove(cell);if(a.Category==UnitCategory.Infantry)infantryRows.Add(cell.Y);
                placements.Add(new(){Id=placements.Count,Army=army,Archetype=a.Id,Name=$"{(army==0?"Blue":"Red")} {a.DisplayName} {n+1}",Position=new(xs[cell.X],ys[cell.Y]),Facing=army==0?0:Math.PI,Formation=a.DefaultFormation});
            }
        }
        return placements.ToArray();
    }
    public BattleConfiguration EditPlacement(int id, Vec2? position=null, double? facing=null, Formation? formation=null)
    {
        if(!Placements.Any(p=>p.Id==id))throw new ArgumentException("Unknown regiment.");
        var next=this with {Placements=Placements.Select(p=>p.Id!=id?p:p with{Position=position??p.Position,Facing=facing??p.Facing,Formation=formation??p.Formation}).ToArray()};
        next.Validate();return next;
    }
    public BattleConfiguration ResetDeployment()
    {
        var old=Placements.GroupBy(p=>(p.Army,p.Archetype)).ToDictionary(g=>g.Key,g=>new Queue<UnitDefinition>(g.OrderBy(p=>p.Id)));
        var next=this with {Placements=AutomaticDeployment().Select(p=>{var o=old[(p.Army,p.Archetype)].Dequeue();return p with{Id=o.Id,Commander=o.Commander,Strength=o.Strength,Name=o.Name};}).OrderBy(p=>p.Id).ToArray()};
        next.Validate();return next;
    }
    public static TerrainDefinition GenerateTerrain(string preset,double width,double height,long seed)
    {
        if(!TerrainPresets.Contains(preset))throw new ArgumentException("Unknown terrain preset.");
        var rng=new PythonTerrainRandom(seed);var hills=new List<Hill>();var forests=new List<Forest>();
        double Range(double lo,double hi)=>lo+(hi-lo)*rng.NextDouble();
        int columns=(int)Math.Ceiling(width/1000),rows=(int)Math.Ceiling(height/600);double cw=width/columns,ch=height/rows,density=cw*ch/600000;
        (double X,double Y,double Rx,double Ry,double D)[] shapes=[(.3,.3,120,108,.5),(.65,.65,140,120,1),(.5,.18,100,78,.75),(.8,.32,90,84,.6)];
        for(int col=0;col<columns;col++)for(int row=0;row<rows;row++) {
            double ox=col*cw,oy=row*ch;
            if(preset=="Central Hill")hills.Add(new(ox+cw*.5,oy+ch*.5,120,150,25,true));
            else if(preset is "Rolling Hills" or "Mixed Terrain")for(int i=0;i<Math.Max(1,(int)Math.Round(5*density));i++)hills.Add(new(ox+cw*Range(.2,.8),oy+ch*Range(.18,.82),Range(70,130),Range(72,132),Range(12,26)*(hills.Count%5==4?-.5:1),true));
            else if(preset=="Ridge Defence")hills.Add(new(width*(.55+(col+.5)*.26/columns),oy+ch*.5,55,252,32,true));
            if(preset is "Wooded Battlefield" or "Mixed Terrain")for(int i=0;i<Math.Max(1,(int)Math.Round(4*density));i++){var s=shapes[i%4];forests.Add(new(Math.Clamp(ox+cw*s.X+Range(-25,25),0,width),Math.Clamp(oy+ch*s.Y+Range(-15,15),0,height),s.Rx,s.Ry,s.D));}
        }
        return new(hills.ToArray(),forests.ToArray());
    }
    public string ToJson()
    {
        object Counts(Dictionary<string,int> c)=>new {infantry=c.GetValueOrDefault("infantry"),cavalry=c.GetValueOrDefault("cavalry"),artillery=c.GetValueOrDefault("artillery"),specialists=c.Where(p=>p.Key is not ("infantry" or "cavalry" or "artillery")).ToDictionary(p=>p.Key,p=>p.Value)};
        object? Point(Vec2? p)=>p is { } v?new[]{v.X,v.Y}:null;
        var t=Terrain;
        return JsonSerializer.Serialize(new { version=1,name=Name,width=Width,height=Height,seed=Seed,blue=Counts(Blue),red=Counts(Red),symmetric=Symmetric,max_per_type=MaxPerType,max_total=MaxTotal,
            army_commanders=ArmyCommanders,ai_armies=AiArmies,ai_strategies=AiStrategies,commander_seed=CommanderSeed,commander_roll=CommanderRoll,terrain_preset=TerrainPreset,terrain_seed=TerrainSeed,
            terrain=t is null?null:new {width=Width,height=Height,preset=TerrainPreset,seed=TerrainSeed,hills=t.Hills.Select(h=>new{x=h.X,y=h.Y,radius_x=h.RadiusX,radius_y=h.RadiusY,height=h.Height,compact=h.Compact}),forests=t.Forests.Select(f=>new{x=f.X,y=f.Y,radius_x=f.RadiusX,radius_y=f.RadiusY,density=f.Density}),environment=t.Environment},
            placements=Placements.Select(p=>new {id=p.Id,army=p.Army,kind=Archetypes.Get(p.Archetype).Category.ToString().ToLowerInvariant(),position=Point(p.Position),facing=p.Facing,formation=(p.Formation??Archetypes.Get(p.Archetype).DefaultFormation).ToString().ToLowerInvariant(),archetype_id=p.Archetype,strength=p.Strength,name=p.Name,
                commander=p.Commander is not { } c?null:new {id=c.Id,name=c.Name,rank=c.Rank,background=c.Background,personality=c.Personality,specialization=c.Specialization,biography=c.Biography,upgrades=c.Upgrades??[],definition_id=c.DefinitionId,nation=c.Nation},
                commander_nation=p.Commander?.Nation,autonomy=p.Autonomy?.ToString().ToLowerInvariant(),
                order=new {kind=(p.Order?.Kind??OrderKind.Hold).ToString().ToLowerInvariant(),destination=Point(p.Order?.Destination),facing=p.Order?.Facing,target_id=p.Order?.TargetId,via_crossing=p.Order?.ViaCrossing}})
        },ScenarioJson.Options);
    }
    public static BattleConfiguration Parse(string json)
    {
        if(json.Length>1_000_000)throw new ArgumentException("Configuration exceeds 1 MB.");
        try {
            using var doc=JsonDocument.Parse(json,new(){MaxDepth=32});var root=doc.RootElement;
            JsonElement Get(JsonElement e,string key)=>e.TryGetProperty(key,out var value)?value:default;
            bool Present(JsonElement e)=>e.ValueKind is not (JsonValueKind.Undefined or JsonValueKind.Null);
            string Text(JsonElement e,string fallback="")=>Present(e)?e.GetString()??fallback:fallback;
            double Number(JsonElement e,double fallback=0)=>Present(e)?e.GetDouble():fallback;
            long Long(JsonElement e,long fallback=0) {
                if(!Present(e))return fallback;
                if(e.ValueKind==JsonValueKind.String)return long.Parse(e.GetString()!,System.Globalization.CultureInfo.InvariantCulture);
                if(e.TryGetInt64(out long value))return value;
                decimal number=e.GetDecimal();if(number!=decimal.Truncate(number))throw new ArgumentException("Expected an integer.");return checked((long)number);
            }
            T EnumValue<T>(JsonElement e,T fallback) where T:struct,Enum {var value=Present(e)?Enum.Parse<T>(e.GetString()!.Replace("_",""),true):fallback;if(!Enum.IsDefined(value))throw new ArgumentException("Unknown formation or order.");return value;}
            Vec2? Point(JsonElement e)=>Present(e)?new(e[0].GetDouble(),e[1].GetDouble()):null;
            Dictionary<string,int> Counts(JsonElement e) {var counts=new Dictionary<string,int>();foreach(var k in new[]{"infantry","cavalry","artillery"})counts[k]=checked((int)Long(Get(e,k),k=="infantry"?4:1));if(Present(Get(e,"specialists")))foreach(var p in e.GetProperty("specialists").EnumerateObject())counts.Add(p.Name,checked((int)Long(p.Value)));return counts;}
            if(root.ValueKind!=JsonValueKind.Object || Long(Get(root,"version"),1)!=1)throw new ArgumentException("Unsupported battle configuration version.");
            var result=new BattleConfiguration {Name=Text(Get(root,"name"),"Custom battle"),Width=Number(Get(root,"width"),1000),Height=Number(Get(root,"height"),600),Seed=Long(Get(root,"seed"),17),CommanderSeed=Long(Get(root,"commander_seed"),Long(Get(root,"seed"),17)),CommanderRoll=checked((int)Long(Get(root,"commander_roll"))),
                Blue=Counts(root.GetProperty("blue")),Red=Counts(root.GetProperty("red")),Symmetric=Present(Get(root,"symmetric"))?root.GetProperty("symmetric").GetBoolean():true,MaxPerType=checked((int)Long(Get(root,"max_per_type"),12)),MaxTotal=checked((int)Long(Get(root,"max_total"),48)),
                TerrainPreset=Text(Get(root,"terrain_preset"),"Open Field"),TerrainSeed=Long(Get(root,"terrain_seed"),Long(Get(root,"seed"),17)),AiArmies=Present(Get(root,"ai_armies"))?root.GetProperty("ai_armies").EnumerateArray().Select(e=>checked((int)Long(e))).ToArray():[1],AiStrategies=Present(Get(root,"ai_strategies"))?root.GetProperty("ai_strategies").EnumerateArray().Select(e=>e.GetString()!).ToArray():["balanced","balanced"]};
            if(Present(Get(root,"army_commanders")))result=result with{ArmyCommanders=root.GetProperty("army_commanders").Deserialize<ArmyCommanderAssignment[]>(ScenarioJson.Options)??[]};
            var terrain=Get(root,"terrain");
            if(Present(terrain)) {
                if(Number(Get(terrain,"width"),result.Width)!=result.Width || Number(Get(terrain,"height"),result.Height)!=result.Height)throw new ArgumentException("Terrain dimensions do not match battlefield.");
                result=result with {Terrain=new((Present(Get(terrain,"hills"))?Get(terrain,"hills").EnumerateArray().ToArray():[]).Select(h=>new Hill(Number(h.GetProperty("x")),Number(h.GetProperty("y")),Number(h.GetProperty("radius_x")),Number(h.GetProperty("radius_y")),Number(h.GetProperty("height")),Present(Get(h,"compact"))&&h.GetProperty("compact").GetBoolean())).ToArray(),(Present(Get(terrain,"forests"))?Get(terrain,"forests").EnumerateArray().ToArray():[]).Select(f=>new Forest(Number(f.GetProperty("x")),Number(f.GetProperty("y")),Number(f.GetProperty("radius_x")),Number(f.GetProperty("radius_y")),Number(f.GetProperty("density")))).ToArray())};
            }
            if(result.Terrain is { } parsedTerrain && Present(Get(terrain,"environment")))result=result with{Terrain=parsedTerrain with{Environment=Get(terrain,"environment").Deserialize<EnvironmentDefinition>(ScenarioJson.Options)}};
            var placements=new List<UnitDefinition>();var raw=Get(root,"placements");
            if(Present(raw))foreach(var p in raw.EnumerateArray()) {
                var c=Get(p,"commander");CommanderIdentity? commander=null;
                if(Present(c))commander=new(Text(c.GetProperty("id")),Text(c.GetProperty("name")),Text(Get(c,"rank")),Text(Get(c,"background"),"Generic"),Text(Get(c,"personality"),"methodical"),Text(Get(c,"specialization"),"inspirer"),Text(Get(c,"biography")),Text(Get(c,"nation"),Text(Get(p,"commander_nation"))),Present(Get(c,"upgrades"))?c.GetProperty("upgrades").EnumerateArray().Select(e=>e.GetString()!).ToArray():null,Text(Get(c,"definition_id")));
                var o=Get(p,"order");var order=Present(o)?new Order(EnumValue(Get(o,"kind"),OrderKind.Hold),Point(Get(o,"destination")),Present(Get(o,"facing"))?Number(o.GetProperty("facing")):null,Present(Get(o,"target_id"))?checked((int)Long(o.GetProperty("target_id"))):null,Present(Get(o,"via_crossing"))?Text(o.GetProperty("via_crossing")):null):new();
                string archetype=Text(Get(p,"archetype_id"),Text(Get(p,"kind"),"infantry"));var a=Archetypes.Get(archetype);
                if(Text(Get(p,"kind"),a.Category.ToString().ToLowerInvariant())!=a.Category.ToString().ToLowerInvariant())throw new ArgumentException("Archetype category does not match placement.");
                placements.Add(new(){Id=checked((int)Long(p.GetProperty("id"))),Army=checked((int)Long(p.GetProperty("army"))),Name=Text(Get(p,"name"),$"{a.Name} {placements.Count+1}"),Archetype=archetype,Position=Point(p.GetProperty("position"))??throw new ArgumentException("Missing position"),Facing=Number(Get(p,"facing")),Formation=EnumValue(Get(p,"formation"),a.DefaultFormation),Strength=Present(Get(p,"strength"))?checked((int)Long(p.GetProperty("strength"))):null,Commander=commander,Order=order,Autonomy=Present(Get(p,"autonomy"))?EnumValue(Get(p,"autonomy"),AutonomyMode.Ordered):null});
            }
            result=result with {Placements=placements.ToArray()};result.Validate(false);return result;
        }
        catch(Exception e) when(e is JsonException or InvalidOperationException or KeyNotFoundException or FormatException or OverflowException or IndexOutOfRangeException or NullReferenceException) {throw new ArgumentException("Invalid battle configuration: "+e.Message,e);}
    }
    public static BattleConfiguration Load(string path)
    {if(new FileInfo(path).Length>1_000_000)throw new ArgumentException("Configuration exceeds 1 MB.");return Parse(File.ReadAllText(path)).Prepare();}
    public void Save(string path)
    {Validate();string temp=path+".tmp";try{File.WriteAllText(temp,ToJson()+"\n");File.Move(temp,path,true);}finally{if(File.Exists(temp))File.Delete(temp);}}
}
