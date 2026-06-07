import numpy as np
from nbodiesgravity.engine.body import CollisionEvent


def test_collision_event_fields():
    ev = CollisionEvent(absorbed="Moon", survivor="Earth")
    assert ev.absorbed == "Moon"
    assert ev.survivor == "Earth"
    # NamedTuple => positional + immutable
    assert tuple(ev) == ("Moon", "Earth")
