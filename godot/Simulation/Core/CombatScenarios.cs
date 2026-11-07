using System.Text.Json;
namespace Quiberon.Simulation;

public static class CombatScenarios
{
    private static readonly IReadOnlyDictionary<string,ScenarioDefinition> definitions=Load();
    public static IEnumerable<(string Id,string Name)> Available=>definitions.Where(p=>!p.Key.StartsWith("benchmark-",StringComparison.Ordinal)).OrderBy(p=>p.Key,StringComparer.Ordinal).Select(p=>(p.Key,p.Value.Name));
    public static ScenarioDefinition Get(string id)=>definitions.TryGetValue(id,out var scenario)?scenario:throw new ArgumentException($"Unknown combat scenario: {id}");
    private static IReadOnlyDictionary<string,ScenarioDefinition> Load()
    {
        var assembly=typeof(CombatScenarios).Assembly;var result=new Dictionary<string,ScenarioDefinition>(StringComparer.Ordinal);
        foreach(var name in assembly.GetManifestResourceNames().Where(n=>n.StartsWith("combat_scenarios.",StringComparison.Ordinal)))
        {
            using var stream=assembly.GetManifestResourceStream(name)!;
            var scenario=JsonSerializer.Deserialize<ScenarioDefinition>(stream,ScenarioJson.Options)??throw new InvalidDataException(name);
            result.Add(name["combat_scenarios.".Length..^5],scenario);
        }
        return result;
    }
}
