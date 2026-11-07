"""Immutable campaign records, explicit battle boundaries and atomic JSON saves."""
from dataclasses import dataclass,replace
import json
import math
from pathlib import Path
import random
from simulation.archetypes import ARCHETYPES
from simulation.commanders import Commander,generate,Personality
from simulation import upgrades
from scenarios.battle_config import ArmyConfig,BattleConfig

ENCOUNTERS=(
 ('Border Engagement','Open Field',1000,600,('infantry','infantry','infantry','cavalry')),
 ('Mobile Opposition','Rolling Hills',1200,800,('infantry','infantry','cavalry','commonwealth_uhlans','artillery')),
 ('Difficult Ground','Wooded Battlefield',1200,800,('infantry','infantry','prussian_line','haudenosaunee_skirmishers','cavalry','artillery')),
 ('Veteran Army','Mixed Terrain',1600,1000,('infantry','infantry','prussian_line','prussian_line','royal_grenadiers','commonwealth_uhlans','commonwealth_uhlans','artillery')),
 ('Decisive Engagement','Ridge Defence',1600,1000,('infantry','infantry','infantry','prussian_line','prussian_line','royal_grenadiers','revolutionary_rifles','commonwealth_uhlans','commonwealth_uhlans','artillery','french_horse_artillery')),
)


@dataclass(frozen=True)
class CampaignRules:
    max_army: int = 10
    upgrade_limit: int = 3
    automatic_replenishment: float = .30
    reward_replenishment: float = .65

    def validate(self):
        if type(self.max_army) is not int or not 5<=self.max_army<=20:raise ValueError('Army limit must be 5–20.')
        if type(self.upgrade_limit) is not int or not 1<=self.upgrade_limit<=12:raise ValueError('Upgrade limit must be 1–12.')
        for n in (self.automatic_replenishment,self.reward_replenishment):
            if type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=1:raise ValueError('Invalid replenishment fraction.')
        if self.reward_replenishment==0:raise ValueError('Replenishment rewards must restore a positive fraction.')


@dataclass(frozen=True)
class ArmyRegiment:
    id: int
    archetype_id: str
    name: str
    strength: int
    maximum: int
    commander: Commander

    def validate(self,limit=12):
        if type(self.id) is not int or not 0<=self.id<1000 or self.archetype_id not in ARCHETYPES:raise ValueError('Invalid persistent regiment identity.')
        a=ARCHETYPES[self.archetype_id]
        if type(self.maximum) is not int or self.maximum!=a.stats.strength or type(self.strength) is not int or not 1<=self.strength<=self.maximum:raise ValueError('Invalid persistent strength.')
        if not isinstance(self.name,str) or not self.name.strip() or len(self.name)>100 or not self.name.isprintable():raise ValueError('Invalid regiment name.')
        self.commander.validate(a.stats.kind)
        if len(self.commander.upgrades)>limit or any(not upgrades.eligible(a,k) for k in self.commander.upgrades):raise ValueError('Invalid commander upgrade assignment.')

    def replenish(self,fraction):return replace(self,strength=min(self.maximum,self.strength+math.ceil((self.maximum-self.strength)*fraction)))
    def to_dict(self):return dict(id=self.id,archetype_id=self.archetype_id,name=self.name,strength=self.strength,maximum=self.maximum,commander=self.commander.to_dict())
    @classmethod
    def from_dict(cls,d):return cls(**{**d,'commander':Commander.from_dict(d['commander'])})


@dataclass(frozen=True)
class Reward:
    id: str
    kind: str
    label: str
    recruit: ArmyRegiment | None = None
    choices: tuple = () # (commander id, tuple of upgrade ids)
    fraction: float = 0.
    target_id: int | None = None

    def to_dict(self):return dict(id=self.id,kind=self.kind,label=self.label,recruit=self.recruit.to_dict() if self.recruit else None,
                                 choices=[[c,list(options)] for c,options in self.choices],fraction=self.fraction,target_id=self.target_id)
    @classmethod
    def from_dict(cls,d):return cls(d['id'],d['kind'],d['label'],ArmyRegiment.from_dict(d['recruit']) if d.get('recruit') else None,
                                   tuple((c,tuple(options)) for c,options in d.get('choices',[])),d.get('fraction',0.),d.get('target_id'))


def roster(keys):
    army=ArmyConfig(0,0,0)
    for k in keys:army=army.with_count(k,army.count(k)+1)
    return army


def officer_record(seed,tag,uid,key,existing=()):
    rng=random.Random(f'campaign-officer:{seed}:{tag}')
    used_names={r.commander.name for r in existing};used_ids={r.commander.id for r in existing}
    a=ARCHETYPES[key];c=generate(rng,a.stats.kind,a.faction,used_names,used_ids)
    return ArmyRegiment(uid,key,f'{a.menu_name or a.name} {uid+1}',a.stats.strength,a.stats.strength,c)


@dataclass(frozen=True)
class Campaign:
    seed: int
    army: tuple[ArmyRegiment,...]
    encounter: BattleConfig
    battle_number: int = 1
    wins: int = 0
    status: str = 'ready'
    rewards: tuple[Reward,...] = ()
    next_id: int = 5
    retired: tuple[Commander,...] = ()
    casualties: int = 0
    rules: CampaignRules = CampaignRules()
    version: int = 1

    @classmethod
    def new(cls,seed,rules=CampaignRules()):
        rules.validate()
        records=[]
        for i,k in enumerate(('infantry','infantry','haudenosaunee_skirmishers','cavalry','artillery')):
            records.append(officer_record(seed,f'start:{i}',i,k,records))
        state=cls(seed,tuple(records),BattleConfig(seed=seed),rules=rules)
        state=replace(state,encounter=state.make_encounter());state.validate();return state

    @property
    def title(self):return ENCOUNTERS[self.battle_number-1][0]

    def make_encounter(self):
        name,terrain,width,height,keys=ENCOUNTERS[self.battle_number-1]
        if self.battle_number>=4 and len(self.army)>=8:keys=(*keys,'infantry')
        rng=random.Random(f'encounter:{self.seed}:{self.battle_number}')
        config=BattleConfig(name=name,width=width,height=height,blue=roster(r.archetype_id for r in self.army),red=roster(keys),symmetric=False,
                           seed=rng.getrandbits(63),terrain_seed=rng.getrandbits(63),terrain_preset=terrain,max_total=48,max_per_type=20,ai_armies=(1,)).prepared()
        pending=list(self.army);placements=[]
        for p in config.placements:
            if p.army==0:
                r=next(r for r in pending if r.archetype_id==p.archetype.id);pending.remove(r)
                p=replace(p,id=r.id,name=r.name,strength=r.strength,commander=r.commander)
            else:
                p=replace(p,id=1000+p.id)
                if self.battle_number>=4:
                    choices=upgrades.available(p.archetype,p.commander,self.rules.upgrade_limit)
                    chosen=choices[rng.randrange(len(choices))] if choices else None
                    p=replace(p,commander=replace(p.commander,personality=Personality.METHODICAL if p.kind.value=='infantry' else Personality.OPPORTUNISTIC,
                                               upgrades=(chosen,) if chosen else ()))
            placements.append(p)
        config=replace(config,placements=tuple(placements));config.validate(True);return config

    def validate_battle_recipe(self,config):
        config.validate(True)
        if replace(config,placements=())!=replace(self.encounter,placements=()):raise ValueError('Campaign encounter settings cannot be edited.')
        originals={p.id:p for p in self.encounter.placements}
        if set(originals)!={p.id for p in config.placements}:raise ValueError('Campaign army composition cannot be edited.')
        for p in config.placements:
            old=originals[p.id]
            if (p.army,p.archetype.id,p.commander,p.strength,p.name)!=(old.army,old.archetype.id,old.commander,old.strength,old.name):raise ValueError('Campaign roster or commanders changed during deployment.')
            if p.army==1 and p!=old:raise ValueError('Enemy deployment cannot be edited.')

    def start_battle(self,config=None):
        if self.status!='ready':raise ValueError('Campaign is not ready for battle.')
        config=config or self.encounter;self.validate_battle_recipe(config)
        return replace(self,encounter=config,status='battle')

    def create_battle(self):
        if self.status not in ('ready','battle'):raise ValueError('No battle is available in this phase.')
        return self.encounter.create_battle()

    def finish_battle(self,battle):
        if self.status!='battle' or battle.result not in ('army_0','army_1','draw'):raise ValueError('Only a finished campaign battle can be applied once.')
        expected={r.id:r for r in self.army};actual={u.id:u for u in battle.units if u.army==0}
        if battle.seed!=self.encounter.seed or set(expected)!=set(actual):raise ValueError('Battle does not match this campaign encounter.')
        survivors=[];retired=list(self.retired);losses=0
        for uid,r in expected.items():
            u=actual[uid]
            if u.archetype.id!=r.archetype_id or u.commander!=r.commander or battle.initial_unit_strength[uid]!=r.strength or not 0<=u.strength<=r.strength:raise ValueError('Invalid campaign battle regiment result.')
            losses+=r.strength-u.strength
            if u.strength>0:survivors.append(replace(r,strength=u.strength))
            else:retired.append(r.commander)
        result=replace(self,army=tuple(survivors),retired=tuple(retired),casualties=self.casualties+losses)
        if battle.result!='army_0' or not survivors:return replace(result,status='defeat',rewards=())
        result=replace(result,army=tuple(r.replenish(self.rules.automatic_replenishment) for r in survivors),wins=self.wins+1)
        if self.battle_number==5:return replace(result,status='victory',rewards=())
        result=replace(result,status='reward');return replace(result,rewards=result.make_rewards())

    def make_rewards(self):
        rng=random.Random(f'rewards:{self.seed}:{self.battle_number}');options=[]
        def recruit(slot):
            key=rng.choice(tuple(ARCHETYPES))
            r=officer_record(self.seed,f'recruit:{self.battle_number}:{slot}',self.next_id,key,self.army)
            # Include retired identity history in the collision check.
            if r.commander.id in {c.id for c in self.retired}:raise ValueError('Commander identity collision.')
            return Reward(f'{self.battle_number}:recruit:{slot}','recruit',f'Recruit {ARCHETYPES[key].name}',recruit=r)
        def training(slot):
            choices=[]
            for r in self.army:
                pool=upgrades.available(ARCHETYPES[r.archetype_id],r.commander,self.rules.upgrade_limit)
                if pool:choices.append((r.commander.id,tuple(rng.sample(pool,min(3,len(pool))))))
            return Reward(f'{self.battle_number}:upgrade:{slot}','upgrade','Develop one commander',choices=tuple(choices)) if choices else None
        if len(self.army)<self.rules.max_army:options.append(recruit(0))
        upgrade=training(0)
        if upgrade:options.append(upgrade)
        if any(r.strength<r.maximum for r in self.army):options.append(Reward(f'{self.battle_number}:replenish:0','replenish','Replenish all surviving regiments',fraction=self.rules.reward_replenishment))
        for slot in range(1,4):
            if len(options)>=3:break
            if len(self.army)<self.rules.max_army:options.append(recruit(slot))
            elif upgrade:options.append(training(slot))
            elif any(r.strength<r.maximum for r in self.army):
                target=max(self.army,key=lambda r:r.maximum-r.strength)
                options.append(Reward(f'{self.battle_number}:replenish:{slot}','replenish',f'Fully replenish {target.name}',fraction=1.,target_id=target.id))
        if not options:options=[Reward(f'{self.battle_number}:continue','continue','Army fully prepared — proceed')]
        return tuple(options)

    def claim(self,reward_id,commander_id=None,upgrade_id=None):
        if self.status!='reward':raise ValueError('No unclaimed campaign reward.')
        reward=next((r for r in self.rewards if r.id==reward_id),None)
        if reward is None:raise ValueError('Unknown reward.')
        army=list(self.army);next_id=self.next_id
        if reward.kind=='recruit':
            if len(army)>=self.rules.max_army or reward.recruit is None:raise ValueError('Recruitment unavailable.')
            army.append(reward.recruit);next_id+=1
        elif reward.kind=='upgrade':
            choices=dict(reward.choices)
            if upgrade_id not in choices.get(commander_id,()):raise ValueError('Select a compatible offered upgrade and commander.')
            index=next((i for i,r in enumerate(army) if r.commander.id==commander_id),None)
            if index is None:raise ValueError('Unknown commander.')
            r=army[index]
            if upgrade_id not in upgrades.available(ARCHETYPES[r.archetype_id],r.commander,self.rules.upgrade_limit):raise ValueError('Upgrade unavailable or limit reached.')
            army[index]=replace(r,commander=replace(r.commander,upgrades=(*r.commander.upgrades,upgrade_id)))
        elif reward.kind=='replenish':
            army=[r.replenish(reward.fraction) if reward.target_id in (None,r.id) else r for r in army]
        elif reward.kind!='continue':raise ValueError('Invalid reward category.')
        result=replace(self,army=tuple(army),next_id=next_id,battle_number=self.battle_number+1,status='ready',rewards=())
        result=replace(result,encounter=result.make_encounter());result.validate();return result

    def validate(self):
        self.rules.validate()
        if type(self.seed) is not int or not -(2**63)<=self.seed<2**63 or type(self.version) is not int or self.version!=1:raise ValueError('Invalid campaign seed/version.')
        if type(self.battle_number) is not int or not 1<=self.battle_number<=5 or type(self.wins) is not int:raise ValueError('Invalid campaign progress.')
        if self.status not in ('ready','battle','reward','victory','defeat'):raise ValueError('Invalid campaign status.')
        expected=self.battle_number if self.status in ('reward','victory') else self.battle_number-1
        if self.wins!=expected or (self.status=='victory' and self.battle_number!=5) or (self.status=='reward' and self.battle_number==5):raise ValueError('Inconsistent campaign progress.')
        if not self.army and self.status!='defeat' or len(self.army)>self.rules.max_army:raise ValueError('Invalid army size.')
        for r in self.army:r.validate(self.rules.upgrade_limit)
        if len({r.id for r in self.army})!=len(self.army):raise ValueError('Duplicate regiment identity.')
        for c in self.retired:c.validate()
        ids=[r.commander.id for r in self.army]+[c.id for c in self.retired]
        if len(set(ids))!=len(ids):raise ValueError('Duplicate commander identity.')
        if type(self.next_id) is not int or not 5<=self.next_id<1000 or any(r.id>=self.next_id for r in self.army):raise ValueError('Invalid recruitment identity counter.')
        if type(self.casualties) is not int or self.casualties<0:raise ValueError('Invalid casualty total.')
        self.encounter.validate(True)
        if self.encounter.seed is None or self.encounter.terrain_seed is None or self.encounter.ai_armies!=(1,):raise ValueError('Campaign encounter needs fixed seeds and player-controlled blue.')
        if self.status in ('ready','battle'):
            actual={p.id:p for p in self.encounter.placements if p.army==0}
            if set(actual)!={r.id for r in self.army}:raise ValueError('Encounter roster mismatch.')
            for r in self.army:
                p=actual[r.id]
                if (p.strength,p.name,p.commander,p.archetype.id)!=(r.strength,r.name,r.commander,r.archetype_id):raise ValueError('Encounter regiment mismatch.')
        if (self.status=='reward')!=bool(self.rewards):raise ValueError('Invalid reward phase.')
        if len(self.rewards)>3 or len({r.id for r in self.rewards})!=len(self.rewards):raise ValueError('Invalid reward count.')
        if self.status=='reward' and self.rewards!=self.make_rewards():raise ValueError('Reward offers do not match saved deterministic choices.')

    def to_dict(self):
        from dataclasses import asdict
        return dict(version=self.version,seed=self.seed,battle_number=self.battle_number,wins=self.wins,status=self.status,
                    army=[r.to_dict() for r in self.army],encounter=self.encounter.to_dict(),rewards=[r.to_dict() for r in self.rewards],
                    next_id=self.next_id,retired=[c.to_dict() for c in self.retired],casualties=self.casualties,rules=asdict(self.rules))

    def save(self,path):
        if self.status=='battle':raise ValueError('Mid-battle saving is not supported; resume the pre-battle checkpoint.')
        self.validate();path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name(path.name+'.tmp')
        temporary.write_text(json.dumps(self.to_dict(),ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
        temporary.replace(path)

    @classmethod
    def load(cls,path):
        try:
            path=Path(path)
            if path.stat().st_size>2_000_000:raise ValueError('Campaign save exceeds 2 MB.')
            data=json.loads(path.read_text(encoding='utf-8'))
            if data.get('version')!=1:raise ValueError('Unsupported campaign save version.')
            data['rules']=CampaignRules(**data['rules']);data['army']=tuple(ArmyRegiment.from_dict(r) for r in data['army'])
            data['retired']=tuple(Commander.from_dict(c) for c in data.get('retired',()))
            data['rewards']=tuple(Reward.from_dict(r) for r in data['rewards']);data['encounter']=BattleConfig.from_dict(data['encounter'])
            state=cls(**data);state.validate()
            if state.status=='battle':raise ValueError('Mid-battle campaign saves are not supported.')
            return state
        except (OSError,UnicodeError,ValueError,TypeError,KeyError,AttributeError,RecursionError,OverflowError) as exc:
            raise ValueError(f'Invalid campaign save: {exc}') from exc
