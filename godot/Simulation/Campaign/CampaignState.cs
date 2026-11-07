using System.Text.Json;
namespace Quiberon.Simulation;
public sealed record CampaignRules(int Capacity=10,int UpgradeLimit=3,double AutoReplenish=.20,double RewardReplenish=.60,double DecisiveSurvival=.55);
public sealed record PersistentRegiment(int Id,string Name,string Archetype,string Faction,int Strength,int Maximum,string CommanderId,int Battles=0,int Inflicted=0,int ArrivalStage=0);
public sealed record CampaignReward(string Id,string Kind,string Label,string Value="",string? CommanderId=null,string[]? Upgrades=null);
public sealed record CampaignBattleRecord(int Stage,string Encounter,int Winner,double Duration,int Lost,int Remaining,string[] Objectives);
public sealed record CampaignState
{
    public int Version {get;init;}=1;
    public string CampaignId {get;init;}="defence-commonwealth-1796";
    public long Seed {get;init;}
    public CampaignRules Rules {get;init;}=new();
    public int Stage {get;set;}=1;
    public string Phase {get;set;}="overview";
    public string Branch {get;set;}="";
    public string Ending {get;set;}="";
    public int NextRegiment {get;set;}=1;
    public List<PersistentRegiment> Roster {get;set;}=new();
    public List<CommanderIdentity> Commanders {get;set;}=new();
    public List<CampaignReward> Rewards {get;set;}=new();
    public List<CampaignBattleRecord> History {get;set;}=new();
    public HashSet<string> Flags {get;set;}=new();
    public string PendingEvent {get;set;}="";
    public ScenarioDefinition? Encounter {get;set;}
}
public sealed record CampaignEventChoice(string Id,string Label,string Description,string[] Flags,string? Unit=null,string? Commander=null);
public sealed record CampaignEvent(string Id,string Title,string Text,CampaignEventChoice[] Choices);
public sealed record CampaignEncounter(string Id,int Stage,string Title,string Date,string Briefing,string KnownEnemy,string[] StartingUnits,Vec2[] Deployment,ScenarioDefinition Scenario,Vec2[]? DefensiveSlots=null);
public static class CampaignContent
{
    static readonly JsonDocument data=JsonDocument.Parse(typeof(CampaignContent).Assembly.GetManifestResourceStream("campaign.json")!);
    public static readonly CampaignRules Rules=data.RootElement.GetProperty("rules").Deserialize<CampaignRules>(ScenarioJson.Options)!;
    public static readonly Dictionary<int,string> StartingCommanders=data.RootElement.GetProperty("startingCommanders").Deserialize<Dictionary<int,string>>(ScenarioJson.Options)!;
    public static readonly string[] StartingUnits=data.RootElement.GetProperty("startingUnits").Deserialize<string[]>()!;
    public static readonly CampaignEvent[] Events=data.RootElement.GetProperty("events").Deserialize<CampaignEvent[]>(ScenarioJson.Options)!;
    public static readonly CampaignEncounter[] Encounters=data.RootElement.GetProperty("encounters").Deserialize<CampaignEncounter[]>(ScenarioJson.Options)!;
    public static CampaignEncounter Encounter(int stage,string branch)=>Encounters.Single(e=>e.Stage==stage && (stage!=4 || e.Id.EndsWith(branch,StringComparison.Ordinal)));
}
