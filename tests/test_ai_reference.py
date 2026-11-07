import json
from dataclasses import asdict
from migration_tools.ai_reference import FIXTURES,probes
from simulation import commanders as c
from migration_tools.movement_reference import ROOT

def test_current_python_commander_and_decision_oracle():
    assert json.loads((FIXTURES/'probes.json').read_text()) == probes()

def test_shared_commander_pools_policies_and_tuning_match_python():
    data=json.loads((ROOT/'simulation_data/commander_definitions.json').read_text())
    assert data['names']=={k:[list(v[0]),list(v[1])] for k,v in c.NAME_POOLS.items()}
    assert data['tuning']==asdict(c.TUNING)
    for personality,definition in data['personalities'].items():assert definition['policy']==asdict(c.POLICIES[c.P(personality)])
    for spec,definition in data['specializations'].items():assert definition['categories']==[k.value for k in c.SPECIALIZATIONS[c.S(spec)][1]]
