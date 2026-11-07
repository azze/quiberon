import pytest
from simulation.regiment import CavalryState
from simulation.geometry import direction


@pytest.fixture
def charging():
    """An already accelerated charge for focused impact-geometry tests.

    Movement/acceleration are exercised through actual ticks in test_cavalry.py.
    """
    def arm(unit,momentum=.6):
        unit.cavalry_state=CavalryState.CHARGING
        unit.charge_sequence+=1
        unit.charge_distance=30.
        unit.charge_momentum=momentum
        unit.velocity=direction(unit.facing)*unit.speed
    return arm
