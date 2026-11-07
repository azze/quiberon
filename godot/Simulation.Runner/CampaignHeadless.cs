using System.Diagnostics;
using System.Text.Json;
using Quiberon.Simulation;
public static class CampaignHeadless
{
    public static int Run(string[] args)
    {
        string Get(string key,string fallback){int i=Array.IndexOf(args,key);return i>=0 && i+1<args.Length?args[i+1]:fallback;}
        long seed=long.Parse(Get("--seed","1796"));int stage=int.Parse(Get("--campaign-stage","1"));string branch=Get("--branch","rescue");double duration=double.Parse(Get("--duration","900"),System.Globalization.CultureInfo.InvariantCulture);string build=Get("--build","default");
        var c=CampaignSession.New(seed);var reports=new List<object>();bool fixture=args.Contains("--campaign-fixture"),full=args.Contains("--campaign-run")||fixture;
        if(!full){c.State.Stage=stage;c.State.Branch=branch;if(stage>=2)c.State.Flags.Add("haudenosaunee");if(stage>=3)c.State.Flags.Add("british");}
        if(build!="default")
        {
            c.State.Flags.UnionWith(["haudenosaunee","british"]);string[] choices=build switch{"people"=>["commonwealth_militia","commonwealth_scythemen"],"mobile"=>["commonwealth_uhlans","haudenosaunee_skirmishers"],"firepower"=>["revolutionary_rifles","commonwealth_field_artillery"],_=>throw new ArgumentException("Unknown build")};
            int n=0;while(c.State.Roster.Count<10)c.Recruit(choices[n++%choices.Length]);
        }
        while(true)
        {
            var d=c.PrepareBattle(true);var b=d.Create();c.Begin();var timings=new List<double>();long allocations=GC.GetAllocatedBytesForCurrentThread();var watch=Stopwatch.StartNew();
            if(fixture){foreach(var u in b.Units.Where(u=>u.Army==0))u.Strength=Math.Max(1,u.Strength-10);b.FinishMission(0,"controlled campaign integration fixture; not an AI win");}
            else while(b.Result is null && b.Time<Math.Min(duration,d.Mission!.Timeout)){long start=Stopwatch.GetTimestamp();b.Step();timings.Add(Stopwatch.GetElapsedTime(start).TotalMilliseconds);}
            long allocated=GC.GetAllocatedBytesForCurrentThread()-allocations;timings.Sort();
            reports.Add(new{stage=c.State.Stage,id=c.Current.Id,b.Seed,fixture,outcome=b.Result?.Id??"inconclusive-timeout",seconds=b.Time,meanMs=timings.Count>0?timings.Average():0,p95Ms=timings.Count>0?timings[Math.Min(timings.Count-1,(int)(timings.Count*.95))]:0,ticksPerSecond=b.Tick/Math.Max(.0001,watch.Elapsed.TotalSeconds),allocatedBytesPerTick=allocated/(double)Math.Max(1,b.Tick),objectives=b.Mission!.Objectives,report=BattleReport.Capture(b),arrived=(d.Mission!.Directives??[]).Where(p=>p.Arrival>0).Select(p=>new{id=p.UnitId,arrived=b.Mission.Arrived(p.UnitId)})});
            if(b.Result is null)break;c.Complete(b);
            if(!full || c.State.Phase=="ended")break;
            var reward=c.State.Rewards.FirstOrDefault(r=>r.Kind=="unit")??c.State.Rewards.First();c.Claim(reward.Id,reward.Upgrades?.FirstOrDefault()??"");while(c.State.Phase=="event"){var e=CampaignContent.Events.Single(e=>e.Id==c.State.PendingEvent);c.ChooseEvent(e.Id=="dangerous_choice"?branch:e.Choices[0].Id);}c=CampaignSession.Deserialize(c.Serialize());
        }
        string json=JsonSerializer.Serialize(new{seed,build,branch,fixture,reports,phase=c.State.Phase,ending=c.State.Ending,battles=c.State.History.Count},ScenarioJson.Options);string output=Get("--output","");if(output!="")File.WriteAllText(output,json+"\n");Console.WriteLine(json);return 0;
    }
}
