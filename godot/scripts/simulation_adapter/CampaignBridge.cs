using Godot;
using Quiberon.Simulation;
using System;
using System.IO;
using System.Linq;
using System.Text.Json;
public partial class CampaignBridge:Node
{
    public static bool Laboratory {get;private set;}
    public bool PrepareLaboratory(int stage,string seed,string branch) => Run(()=>{Laboratory=true;Current=CampaignSession.New(long.Parse(seed));Current.State.Stage=stage;Current.State.Branch=branch;Current.State.Flags.UnionWith(["british","haudenosaunee"]);if(stage==3){Current.Recruit("revolutionary_line","edward_marcus_despard");Current.State.Roster[^1]=Current.State.Roster[^1] with{ArrivalStage=3};}string[] types=["commonwealth_regulars","commonwealth_uhlans","revolutionary_rifles","haudenosaunee_skirmishers"];int i=0;while(Current.State.Roster.Count<10)Current.Recruit(types[i++%types.Length]);Current.PrepareBattle(true);});
    public static CampaignSession? Current {get;private set;}
    public string Error {get;private set;}="";
    static string SavePath=>ProjectSettings.GlobalizePath("user://commonwealth-campaign-v1.json");
    public bool HasSave()=>File.Exists(SavePath);
    bool Run(Action action){try{action();Error="";return true;}catch(Exception e) when(e is ArgumentException or InvalidOperationException or IOException or JsonException){Error=e.Message;return false;}}
    public bool NewCampaign(string seed)=>Run(()=>{if(!long.TryParse(seed,out long value))throw new ArgumentException("Seed must be a signed integer.");Laboratory=false;Current=CampaignSession.New(value);Current.Save(SavePath);});
    public bool LoadCampaign()=>Run(()=>{Current=CampaignSession.Deserialize(File.ReadAllText(SavePath));Laboratory=false;});
    public bool SaveCampaign()=>Run(()=>Current!.Save(SavePath));
    public bool HasCampaign()=>Current is not null;
    public string GetView()
    {
        if(Current is null)return "{}";var s=Current.State;var encounter=CampaignContent.Encounters.First(e=>e.Stage==s.Stage && (s.Stage!=4 || s.Branch=="" || e.Id.EndsWith(s.Branch,StringComparison.Ordinal)));
        return JsonSerializer.Serialize(new{state=s,weather=encounter.Scenario.Terrain?.Environment?.Weather?.Type.ToString()??"Clear",terrain=new{hills=encounter.Scenario.Terrain?.Hills.Length??0,forests=encounter.Scenario.Terrain?.Forests.Length??0,rivers=encounter.Scenario.Terrain?.Environment?.Rivers?.Length??0,crossings=encounter.Scenario.Terrain?.Environment?.Crossings?.Length??0,roads=encounter.Scenario.Terrain?.Environment?.Roads?.Length??0},seedText=s.Seed.ToString(System.Globalization.CultureInfo.InvariantCulture),title=encounter.Title,date=encounter.Date,briefing=s.Stage==3 && !s.Roster.Any(r=>r.ArrivalStage==3)?encounter.Briefing.Replace("Despard’s expedition arrives after one minute.","No expeditionary regiment is attached at current army capacity; British recruitment remains unlocked."):encounter.Briefing,knownEnemy=encounter.KnownEnemy,objective=encounter.Scenario.Mission!.Objectives[0].Description,events=CampaignContent.Events,units=Archetypes.All.Select(a=>new{a.Id,name=a.DisplayName}),upgrades=UpgradeSystem.Definitions,historical=HistoricalCommanders.All},ScenarioJson.Options);
    }
    public string CompatibleCommanders(int regiment)
    {var s=Current!.State;var a=Archetypes.Get(s.Roster.Single(r=>r.Id==regiment).Archetype);return JsonSerializer.Serialize(s.Commanders.Where(c=>{try{CommanderSystem.Validate(c,a.Category);UpgradeSystem.Validate(c,a);return true;}catch(ArgumentException){return false;}}),ScenarioJson.Options);}
    public bool Assign(int regiment,string commander)=>Run(()=>{Current!.Assign(regiment,commander);Current.Save(SavePath);});
    public bool Claim(string reward,string upgrade)=>Run(()=>{Current!.Claim(reward,upgrade);Current.Save(SavePath);});
    public bool ChooseEvent(string choice)=>Run(()=>{Current!.ChooseEvent(choice);Current.Save(SavePath);});
    public bool Prepare(bool aiPlayer)=>Run(()=>{Current!.PrepareBattle(aiPlayer);Current.Save(SavePath);});
    public bool Complete(BattleSimulation battle)=>Run(()=>{Current!.Complete(battle);Current.Save(SavePath);});
}
