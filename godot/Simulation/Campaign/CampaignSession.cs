using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
namespace Quiberon.Simulation;
/// <summary>Persistent roster boundary, deterministic offers and idempotent between-battle transitions.</summary>
public sealed class CampaignSession
{
    public CampaignState State {get;}
    public CampaignSession(CampaignState state){State=state;Validate();}
    public static long StreamSeed(long seed,string stream)=>System.Buffers.Binary.BinaryPrimitives.ReadInt64LittleEndian(SHA256.HashData(Encoding.UTF8.GetBytes($"commonwealth:{seed}:{stream}")))&long.MaxValue;
    public static CampaignSession New(long seed,CampaignRules? rules=null)
    {
        var session=new CampaignSession(new(){Seed=seed,Rules=rules??CampaignContent.Rules});
        foreach(string type in CampaignContent.StartingUnits)session.Recruit(type);
        foreach(var assignment in CampaignContent.StartingCommanders)session.Assign(session.State.Roster[assignment.Key].Id,session.AddHistorical(assignment.Value).Id);
        return session;
    }
    public CampaignEncounter Current=>CampaignContent.Encounter(State.Stage,State.Branch);
    public void Validate()
    {
        var s=State;
        if(s.Rules is null || s.Roster is null || s.Commanders is null || s.Rewards is null || s.History is null || s.Flags is null)throw new ArgumentException("Campaign collections/rules are missing.");
        if(s.Version!=1 || s.CampaignId!="defence-commonwealth-1796" || s.Stage is <1 or >6 || !new[]{"overview","battle","rewards","event","ended"}.Contains(s.Phase) || s.Rules.Capacity is <5 or >20 || s.Rules.UpgradeLimit is <1 or >3 || !double.IsFinite(s.Rules.AutoReplenish+s.Rules.RewardReplenish+s.Rules.DecisiveSurvival) || s.Rules.AutoReplenish is <0 or >1 || s.Rules.RewardReplenish is <=0 or >1 || s.Rules.DecisiveSurvival is <0 or >1 || s.Roster.Count>s.Rules.Capacity || s.Roster.Select(r=>r.Id).Distinct().Count()!=s.Roster.Count || s.Commanders.Select(c=>c.Id).Distinct().Count()!=s.Commanders.Count || s.Roster.Select(r=>r.CommanderId).Distinct().Count()!=s.Roster.Count || s.History.Select(r=>r.Stage).Distinct().Count()!=s.History.Count)throw new ArgumentException("Invalid campaign save/state.");
        if(s.Branch!="" && s.Branch is not ("rescue" or "intercept"))throw new ArgumentException("Invalid campaign branch.");
        if(s.Commanders.Where(c=>c.DefinitionId!="").Select(c=>c.DefinitionId).Distinct().Count()!=s.Commanders.Count(c=>c.DefinitionId!=""))throw new ArgumentException("Duplicate historical commander.");
        foreach(var c in s.Commanders)
        {
            bool compatible=Archetypes.All.Any(a=>{try{CommanderSystem.Validate(c,a.Category);UpgradeSystem.Validate(c,a);return true;}catch(ArgumentException){return false;}});
            if(!compatible || (c.Upgrades?.Count??0)>s.Rules.UpgradeLimit)throw new ArgumentException("Invalid reserve commander.");
        }
        if(s.NextRegiment<1 || s.Roster.Any(r=>r.Id<1 || r.Id>=800 || r.Id>=s.NextRegiment) || s.Phase=="overview" && s.History.Any(h=>h.Stage==s.Stage))throw new ArgumentException("Invalid persistent regiment/stage identity.");
        foreach(var r in s.Roster){var a=Archetypes.Get(r.Archetype);if(r.Strength<1 || r.Strength>r.Maximum || r.Maximum!=a.Strength || r.Faction!=a.Faction)throw new ArgumentException("Invalid persistent regiment.");var c=s.Commanders.Single(c=>c.Id==r.CommanderId);CommanderSystem.Validate(c,a.Category);UpgradeSystem.Validate(c,a);if((c.Upgrades?.Count??0)>s.Rules.UpgradeLimit)throw new ArgumentException("Campaign upgrade limit exceeded.");}
        if(s.Rewards.Select(r=>r.Id).Distinct().Count()!=s.Rewards.Count || s.Phase=="rewards" && s.Rewards.Count!=3)throw new ArgumentException("Invalid pending rewards.");
    }
    public CommanderIdentity AddHistorical(string id)
    {
        if(State.Commanders.Any(c=>c.DefinitionId==id))throw new ArgumentException("Historical commander already recruited.");
        var d=HistoricalCommanders.Get(id);if(d.ArmyLevel)throw new ArgumentException("Army commander cannot take a regiment slot.");var c=d.Create();State.Commanders.Add(c);return c;
    }
    public void Recruit(string type,string? historical=null)
    {
        if(State.Roster.Count>=State.Rules.Capacity)throw new ArgumentException("Army capacity reached.");
        var a=Archetypes.Get(type);if(!AvailableUnits().Contains(type))throw new ArgumentException("Unit is not available to this coalition.");
        int id=State.NextRegiment;
        var c=historical is null?CommanderSystem.Generate(new SimulationRandom(StreamSeed(State.Seed,$"officer-{id}")),a.Category,a.Faction,State.Commanders.Select(c=>c.Name).Concat(HistoricalCommanders.All.SelectMany(d=>d.AlternativeNames.Append(d.Name))).ToHashSet(),State.Commanders.Select(c=>c.Id).ToHashSet()):HistoricalCommanders.Get(historical).Create();
        CommanderSystem.Validate(c,a.Category);UpgradeSystem.Validate(c,a);
        if(State.Commanders.Any(old=>old.Id==c.Id || c.DefinitionId!="" && old.DefinitionId==c.DefinitionId))throw new ArgumentException("Commander already recruited.");
        State.NextRegiment++;State.Commanders.Add(c);
        State.Roster.Add(new(id,$"{a.DisplayName} {id}",type,a.Faction,a.Strength,a.Strength,c.Id));
    }
    public string[] AvailableUnits()=>new[]{"commonwealth_regulars","commonwealth_militia","commonwealth_scythemen","commonwealth_national_cavalry","commonwealth_uhlans","commonwealth_field_artillery"}.Concat(State.Flags.Contains("haudenosaunee")?new[]{"haudenosaunee_skirmishers"}:[]).Concat(State.Flags.Contains("british")?new[]{"revolutionary_line","revolutionary_rifles"}:[]).ToArray();
    public void Assign(int regimentId,string commanderId)
    {
        if(State.Phase!="overview")throw new ArgumentException("Assignments lock during encounters and choices.");
        int i=State.Roster.FindIndex(r=>r.Id==regimentId);if(i<0)throw new ArgumentException("Unknown regiment.");var r=State.Roster[i];var c=State.Commanders.Single(c=>c.Id==commanderId);
        CommanderSystem.Validate(c,Archetypes.Get(r.Archetype).Category);UpgradeSystem.Validate(c,Archetypes.Get(r.Archetype));
        int j=State.Roster.FindIndex(r=>r.CommanderId==commanderId);
        if(j>=0 && j!=i){var old=State.Commanders.Single(c=>c.Id==r.CommanderId);var other=State.Roster[j];CommanderSystem.Validate(old,Archetypes.Get(other.Archetype).Category);UpgradeSystem.Validate(old,Archetypes.Get(other.Archetype));State.Roster[j]=other with{CommanderId=r.CommanderId};}
        State.Roster[i]=r with{CommanderId=commanderId};State.Encounter=null;
    }
    public ScenarioDefinition PrepareBattle(bool autoPlayer=false)
    {
        if(State.Phase!="overview" || State.Roster.Count==0)throw new ArgumentException("Campaign is not ready for battle.");
        var authored=Current;var def=authored.Scenario;var units=def.Units.ToList();
        for(int i=0;i<State.Roster.Count;i++)
        {
            var r=State.Roster[i];var p=authored.Deployment[i];units.Add(new(){Id=r.Id,Army=0,Name=r.Name,Archetype=r.Archetype,Position=p,Facing=State.Stage==3?Math.PI:0,Strength=r.Strength,Commander=State.Commanders.Single(c=>c.Id==r.CommanderId)});
        }
        var directives=(def.Mission!.Directives??[]).ToList();
        if(autoPlayer)
        {
            var assigned=new HashSet<int>();
            foreach(var slot in authored.DefensiveSlots??[])
            {
                var guard=units.Where(u=>u.Army==0 && !assigned.Contains(u.Id) && Archetypes.Get(u.Archetype).Category==UnitCategory.Infantry && !Archetypes.Get(u.Archetype).Skirmisher && Archetypes.Get(u.Archetype).Weapon is not null).OrderBy(u=>(u.Position-slot).LengthSquared).ThenBy(u=>u.Id).FirstOrDefault();
                if(guard is not null){assigned.Add(guard.Id);directives.Add(new(guard.Id,[slot],Formation:Formation.Line,After:"hold"));}
            }
        }
        // Persistent British reinforcement is predeclared, not duplicated at spawn.
        foreach(var u in units.Where(u=>u.Army==0 && State.Roster.Any(r=>r.Id==u.Id && r.ArrivalStage==State.Stage)))
        {int existing=directives.FindIndex(p=>p.UnitId==u.Id);if(existing>=0)directives[existing]=directives[existing] with{Arrival=60};else directives.Add(new(u.Id,[],Arrival:60));}
        if(State.Stage==5 && State.Flags.Contains("supplies_cut"))
        {var weakened=units.FirstOrDefault(u=>u.Army==1 && u.Archetype=="russian_grenadiers");if(weakened is not null)units.Remove(weakened);directives.RemoveAll(p=>p.UnitId==weakened?.Id);}
        if(State.Stage==5 && State.Flags.Contains("allies_saved"))units.Add(new(){Id=850,Army=0,Name="Rescued allied support",Archetype="commonwealth_regulars",Position=new(180,750),Autonomy=AutonomyMode.Autonomous});
        directives=directives.Select(p=>p.Arrival>0 && units.Any(u=>u.Id==p.UnitId && u.Army==1)?p with{Arrival=p.Arrival+(State.Stage==5 && State.Flags.Contains("enemy_delay")?45:0)+StreamSeed(State.Seed,$"arrival-{State.Stage}-{p.UnitId}")%21-10}:p).ToList();
        def=def with{Units=units.ToArray(),Seed=StreamSeed(State.Seed,$"combat-{State.Stage}-{(State.Stage>=4?State.Branch:"")}"),CommanderSeed=StreamSeed(State.Seed,$"commanders-{State.Stage}"),AiArmies=autoPlayer?[0,1]:[1],Mission=def.Mission with{Directives=directives.ToArray()}};
        State.Encounter=def;return def;
    }
    public void Begin(){if(State.Phase!="overview" || State.Encounter is null)throw new ArgumentException("No prepared encounter.");State.Phase="battle";}
    public void Complete(BattleSimulation battle)
    {
        if(State.Phase!="battle" || State.Encounter is null || battle.Seed!=State.Encounter.Seed || battle.Result is null || State.History.Any(h=>h.Stage==State.Stage))throw new ArgumentException("Finished battle does not match pending campaign stage.");
        var expected=State.Roster.Select(r=>r.Id).Order();var actual=battle.Units.Where(u=>u.Army==0 && u.Id<800).Select(u=>u.Id).Order();if(!expected.SequenceEqual(actual))throw new ArgumentException("Battle roster mismatch.");
        int enteringMaximum=State.Roster.Sum(r=>r.Maximum);int lost=0;var survivors=new List<PersistentRegiment>();foreach(var r in State.Roster){var u=battle.Unit(r.Id)!;if(u.Archetype.Id!=r.Archetype || u.Commander.Id!=r.CommanderId || u.Strength>r.Strength)throw new ArgumentException("Invalid persistent battle result.");lost+=r.Strength-u.Strength;if(u.Strength>0)survivors.Add(r with{Strength=u.Strength,Battles=r.Battles+1,Inflicted=r.Inflicted+u.DamageInflicted});}
        State.Roster=survivors;bool win=battle.Result.WinnerArmy==0;
        State.History.Add(new(State.Stage,Current.Id,battle.Result.WinnerArmy??-1,battle.Time,lost,survivors.Sum(r=>r.Strength),battle.Mission?.Objectives.Where(o=>o.Status=="success").Select(o=>o.Id).ToArray()??[]));
        if(!win){State.Ending="defeat";State.Phase="ended";return;}
        if(State.Stage==4)State.Flags.Add(State.Branch=="rescue"?"allies_saved":"supplies_cut");
        double survival=State.Roster.Sum(r=>r.Strength)/(double)Math.Max(1,enteringMaximum);
        if(State.Stage==6){State.Ending=survival>=State.Rules.DecisiveSurvival && State.History.All(h=>h.Winner==0)?"decisive":"negotiated";State.Phase="ended";return;}
        Replenish(State.Rules.AutoReplenish);State.Phase="rewards";GenerateRewards();
    }
    void Replenish(double fraction)=>State.Roster=State.Roster.Select(r=>r with{Strength=Math.Min(r.Maximum,r.Strength+(int)Math.Ceiling((r.Maximum-r.Strength)*fraction))}).ToList();
    void GenerateRewards()
    {
        var candidates=new List<CampaignReward>();int stage=State.Stage;
        if(State.Roster.Count<State.Rules.Capacity)foreach(var type in AvailableUnits())candidates.Add(new($"{stage}-unit-{type}","unit","Recruit "+Archetypes.Get(type).DisplayName,type));
        if(State.Roster.Any(r=>r.Strength<r.Maximum))candidates.Add(new($"{stage}-replace","replenish",$"Replace {State.Rules.RewardReplenish:P0} of missing soldiers"));
        foreach(var r in State.Roster)
        {var c=State.Commanders.Single(c=>c.Id==r.CommanderId);if((c.Upgrades?.Count??0)>=State.Rules.UpgradeLimit)continue;var choices=UpgradeSystem.Available(Archetypes.Get(r.Archetype),c).Where(d=>d.Id!="rolling_volley" || Archetypes.Get(r.Archetype).Weapon is not null).OrderBy(d=>StreamSeed(State.Seed,$"upgrade-{stage}-{c.Id}-{d.Id}")).Take(3).Select(d=>d.Id).ToArray();if(choices.Length>0)candidates.Add(new($"{stage}-upgrade-{c.Id}","upgrade","Train "+c.Name,CommanderId:c.Id,Upgrades:choices));}
        foreach(var id in new[]{"jan_henryk_dabrowski","antoni_madalinski","jakub_jasinski","franciszek_ksawery_lazninski"}.Concat(State.Flags.Contains("british")?new[]{"lord_edward_fitzgerald"}:[]).Concat(State.Flags.Contains("haudenosaunee")?new[]{"joseph_louis_cook"}:[]))
            if(State.Roster.Any(r=>HistoricalCommanders.Get(id).Categories.Contains(Archetypes.Get(r.Archetype).Category.ToString().ToLowerInvariant())) && !State.Commanders.Any(c=>c.DefinitionId==id))candidates.Add(new($"{stage}-officer-{id}","commander","Recruit "+HistoricalCommanders.Get(id).Name,id));
        State.Rewards=candidates.OrderBy(r=>StreamSeed(State.Seed,$"reward-{stage}-{r.Id}")).Take(3).ToList();
        if(State.Rewards.Count!=3)throw new ArgumentException("No meaningful rewards remain.");
    }
    public void Claim(string id,string upgrade="")
    {
        if(State.Phase!="rewards")throw new ArgumentException("Reward already claimed or unavailable.");var reward=State.Rewards.SingleOrDefault(r=>r.Id==id)??throw new ArgumentException("Unknown reward.");
        if(reward.Kind=="upgrade")
        {if(reward.Upgrades?.Contains(upgrade)!=true)throw new ArgumentException("Choose a stored compatible upgrade.");int i=State.Commanders.FindIndex(c=>c.Id==reward.CommanderId);var c=State.Commanders[i];State.Commanders[i]=c with{Upgrades=(c.Upgrades??[]).Append(upgrade).ToArray()};}
        else if(reward.Kind=="unit")Recruit(reward.Value);
        else if(reward.Kind=="commander")AddHistorical(reward.Value);
        else if(reward.Kind=="replenish")Replenish(State.Rules.RewardReplenish);
        State.Rewards.Clear();State.Stage++;State.Encounter=null;
        State.PendingEvent=State.Stage switch{2=>"haudenosaunee",3=>"british",4=>"dangerous_choice",5=>"politics",_=>"volunteers"};State.Phase="event";
    }
    public void ChooseEvent(string choice)
    {
        if(State.Phase!="event")throw new ArgumentException("No pending event.");var e=CampaignContent.Events.Single(e=>e.Id==State.PendingEvent);var c=e.Choices.SingleOrDefault(c=>c.Id==choice)??throw new ArgumentException("Unknown event choice.");
        if(State.Flags.Contains("event-"+e.Id))throw new ArgumentException("Event already applied.");
        int priorCount=State.Roster.Count;
        foreach(string flag in c.Flags)State.Flags.Add(flag);
        if(e.Id=="dangerous_choice")State.Branch=c.Id;
        if(c.Commander is { } commander && !State.Commanders.Any(c=>c.DefinitionId==commander))
        {if(c.Unit is { } unit && State.Roster.Count<State.Rules.Capacity)Recruit(unit,commander);else {AddHistorical(commander);if(c.Unit is not null)Replenish(.35);}}
        else if(c.Unit is { } type && State.Roster.Count<State.Rules.Capacity)Recruit(type);
        else if(c.Unit is not null)Replenish(.35); // capacity fallback is displayed in the event UI.
        if(e.Id=="british" && State.Roster.Count>priorCount)State.Roster[^1]=State.Roster[^1] with{ArrivalStage=3};
        State.Flags.Add("event-"+e.Id);State.PendingEvent=e.Id=="politics"?"disagreement":"";State.Phase=e.Id=="politics"?"event":"overview";if(c.Flags.Contains("strategic_rest"))Replenish(.35);
    }
    public string Serialize(){Validate();return JsonSerializer.Serialize(State,ScenarioJson.Options);}
    public static CampaignSession Deserialize(string json)
    {using var d=JsonDocument.Parse(json);if(!d.RootElement.TryGetProperty("campaignId",out var id) || id.GetString()!="defence-commonwealth-1796" || !d.RootElement.TryGetProperty("version",out var version) || version.GetInt32()!=1)throw new ArgumentException("Unsupported or foreign campaign save.");return new(JsonSerializer.Deserialize<CampaignState>(json,ScenarioJson.Options)??throw new ArgumentException("Empty campaign save."));}
    public void Save(string path)
    {if(State.Phase=="battle")throw new ArgumentException("Save between battles; mid-battle saving is unavailable.");string json=Serialize();Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);string temp=path+".tmp";File.WriteAllText(temp,json);File.Move(temp,path,true);}
}
