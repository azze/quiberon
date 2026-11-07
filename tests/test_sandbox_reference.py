"""Native sandbox data is derived from the unchanged Python gameplay rules."""
import json
from dataclasses import asdict
from pathlib import Path
from simulation import upgrades
from migration_tools.sandbox_reference import probes

ROOT=Path(__file__).resolve().parents[1]

def test_native_upgrade_registry_uses_current_python_definitions_and_parameters():
    data=json.loads((ROOT/'simulation_data/commander_upgrades.json').read_text())
    assert data['limit']==3 and data['tuning']==asdict(upgrades.TUNING)
    assert len(data['definitions'])==12
    for native,original in zip(data['definitions'],upgrades.DEFINITIONS):
        assert (native['id'],native['description'],native['categories'],native['roles'],native['maxRank'])==(original.id,original.description,[k.value for k in original.kinds],list(original.roles),original.max_rank)

def test_native_charge_and_upgrade_oracles_are_reproducible_from_current_python():
    expected=json.loads((ROOT/'migration_tools/sandbox_fixtures/probes.json').read_text())
    assert len(expected)==45
    assert probes()==expected
