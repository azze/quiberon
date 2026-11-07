"""Keep the migration oracle tied to current Python mechanics, not handwritten expectations."""
import json
from migration_tools.artillery_reference import FIXTURES,physics_case,ground,hill,forest,probes

def test_current_python_specialist_oracle():
    assert json.loads((FIXTURES/'specialists.json').read_text()) == probes()

def test_current_python_ballistics_oracle():
    actual=[physics_case('flat'),physics_case('hill',ground([hill(445,300,12,60,20,True)],[])),physics_case('forest',ground([],[forest(470,300,100,70,.7)])),physics_case('overflight',init=dict(height=30,vertical_speed=0)),physics_case('ricochet',init=dict(height=.5,vertical_speed=-5),steps=60)]
    assert json.loads((FIXTURES/'physics.json').read_text()) == actual


def test_current_python_complete_battle_traces():
    from migration_tools.artillery_reference import scenarios,trace
    for name in ['open-shot','prussian-drill','rifle-engagement','woodland-specialists','grenadier-support']:
        expected=json.loads((FIXTURES/(name+'-trace.json')).read_text())
        assert trace(expected['input']) == expected
