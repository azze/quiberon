using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Quiberon.Simulation;

try
{
    if(args.Any(a=>a.StartsWith("--campaign",StringComparison.Ordinal)))return CampaignHeadless.Run(args);
    string scenarioPath = "migration_tools/movement_fixtures/straight.json", output = "";
    string? battleConfig=null, reportPath=null;
    double? duration = null; long? seed = null; bool benchmark = false, combat = false, allocationProfile = false; int warmup = 100;
    for (int i = 0; i < args.Length; i++)
    {
        string Next() => ++i < args.Length ? args[i] : throw new ArgumentException("Missing option value");
        switch (args[i])
        {
            case "--scenario": scenarioPath = Next(); break;
            case "--battle-config": battleConfig=Next();break;
            case "--report": reportPath=Next();break;
            case "--combat-scenario": scenarioPath = Next(); combat = true; break;
            case "--output": output = Next(); break;
            case "--duration": duration = double.Parse(Next(), System.Globalization.CultureInfo.InvariantCulture); break;
            case "--seed": seed = long.Parse(Next()); break;
            case "--warmup": warmup = int.Parse(Next()); break;
            case "--benchmark": benchmark = true; break;
            case "--allocation-profile": allocationProfile = true; break;
            case "--help": Console.WriteLine("Simulation.Runner (--scenario PATH|MOVEMENT_NAME | --combat-scenario NAME | --battle-config PATH) [--duration SECONDS] [--seed N] [--output PATH] [--report PATH] [--benchmark] [--warmup TICKS] [--allocation-profile]"); return 0;
            default: throw new ArgumentException($"Unknown option {args[i]}");
        }
    }
    if (!combat && !File.Exists(scenarioPath)) scenarioPath = Path.Combine("migration_tools/movement_fixtures", scenarioPath + ".json");
    var definition = battleConfig is not null?BattleConfiguration.Load(battleConfig).Scenario():combat ? CombatScenarios.Get(scenarioPath) : ScenarioDefinition.Load(scenarioPath);
    if (warmup < 0) throw new ArgumentException("Warmup ticks cannot be negative");
    if (duration is { } d) definition = definition with { Duration = d };
    if (seed is { } s) definition = definition with { Seed = s };
    var battle = definition.Create(allocationProfile);
    int ticks = (int)Math.Round(definition.Duration / Rules.Dt);
    var sampleTicks = definition.SampleTicks.ToHashSet(); sampleTicks.Add(0); sampleTicks.Add(ticks);
    var snapshots = new List<BattleSnapshot>(); var timings = new List<double>();
    long allocationStart = 0; var watch = Stopwatch.StartNew(); long measuredStart = 0;
    while (true)
    {
        if (!benchmark && sampleTicks.Contains(battle.Tick)) snapshots.Add(battle.Snapshot());
        if (battle.Tick >= ticks || battle.Result is not null) break;
        if (battle.Tick == warmup) { allocationStart = GC.GetAllocatedBytesForCurrentThread(); measuredStart = Stopwatch.GetTimestamp(); }
        long start = Stopwatch.GetTimestamp(); definition.IssueScheduled(battle); battle.Step();
        if (battle.Tick > warmup) timings.Add(Stopwatch.GetElapsedTime(start).TotalMilliseconds);
    }
    long allocations = allocationStart == 0 ? 0 : GC.GetAllocatedBytesForCurrentThread() - allocationStart;
    double measuredWall = measuredStart == 0 ? 0 : Stopwatch.GetElapsedTime(measuredStart).TotalSeconds;
    if(!benchmark && (snapshots.Count==0 || snapshots[^1].Tick!=battle.Tick))snapshots.Add(battle.Snapshot());
    object report;
    if(reportPath is not null)File.WriteAllText(reportPath,JsonSerializer.Serialize(BattleReport.Capture(battle),ScenarioJson.Options)+"\n");
    if (benchmark)
    {
        if (timings.Count == 0) throw new ArgumentException("Duration must exceed warmup for benchmark");
        timings.Sort(); double average = timings.Average();
        string fingerprint = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(battle.Snapshot(), ScenarioJson.Options))));
        report = new { name = definition.Name, language = "csharp", units = battle.Units.Count, definition.Seed, warmupTicks = warmup, measuredTicks = timings.Count, simulatedSeconds = timings.Count * Rules.Dt, meanMs = average, medianMs = timings[timings.Count / 2], p95Ms = timings[Math.Min(timings.Count - 1, (int)(timings.Count * .95))], ticksPerSecond = timings.Count / measuredWall, measuredWallSeconds = measuredWall, totalWallSeconds = watch.Elapsed.TotalSeconds, allocatedBytesPerTick = allocations / (double)timings.Count, checksum = fingerprint,
            environment=new{queries=battle.Terrain.Environment.GeometryQueries,routePlans=battle.Navigation.Plans,weather=battle.Terrain.Environment.Weather.Type,crossingOwners=battle.Navigation.Owners},
            combat = definition.CombatEnabled, metrics = battle.Metrics, randomDraws = battle.Random.Draws, result = battle.Result, finalTick = battle.Tick,
            finalStrengths=battle.Units.Select(u=>u.Strength).ToArray(),morale=definition.MoraleEnabled,cavalry=definition.CavalryEnabled,
            finalStates=battle.Units.Select(u=>new{id=u.Id,position=u.Position,strength=u.Strength,morale=u.Morale,cohesion=u.Cohesion,state=u.State.ToString().ToLowerInvariant(),withdrawn=u.Withdrawn}).ToArray() };
    }
    else report = new { definition.Name, snapshots, battle.Result, events=battle.Events, metrics=battle.Metrics, randomDraws=battle.Random.Draws,timedOut=battle.Result is null && battle.Tick>=ticks,participation=battle.Units.Select(u=>new{id=u.Id,army=u.Army,category=u.Archetype.Category,commander=u.Commander,decisions=u.Decisions,targetChanges=u.TargetChanges,formationChanges=u.FormationChanges,shots=u.ShotsFired,inflicted=u.DamageInflicted,movingSeconds=u.MovingSeconds,firingSeconds=u.FiringSeconds}).ToArray() };
    string json = JsonSerializer.Serialize(report, ScenarioJson.Options);
    if (output.Length > 0) { Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output))!); File.WriteAllText(output, json + "\n"); }
    Console.WriteLine(json);
    return 0;
}
catch (Exception error) when (error is ArgumentException or IOException or JsonException or InvalidOperationException)
{ Console.Error.WriteLine(error.Message); return 1; }
