import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.ui.body_list_panel import BodyListPanel


def test_body_list_panel_category_toggling(qapp):
    """Verify that category controls in BodyListPanel synchronize states and emit signals."""
    b1 = CelestialBody(name="Sun", mass=2.0e30, pos=np.zeros(3), vel=np.zeros(3), radius=10.0, color=(1,0,0), label="star")
    b2 = CelestialBody(name="Earth", mass=6.0e24, pos=np.zeros(3), vel=np.zeros(3), radius=1.0, color=(0,0,1), label="planet")
    b3 = CelestialBody(name="Mars", mass=6.0e23, pos=np.zeros(3), vel=np.zeros(3), radius=0.5, color=(1,0,1), label="planet")
    b4 = CelestialBody(name="Moon", mass=7.0e22, pos=np.zeros(3), vel=np.zeros(3), radius=0.2, color=(0.5,0.5,0.5), label="moon")
    
    panel = BodyListPanel()
    panel.populate([b1, b2, b3, b4])
    
    # 1. Check default category checkbox states
    widgets = panel._category_widgets
    assert widgets["star"]["active"].isChecked() is True
    assert widgets["planet"]["active"].isChecked() is True
    assert widgets["moon"]["active"].isChecked() is True
    
    assert widgets["star"]["trail"].isChecked() is True
    assert widgets["planet"]["trail"].isChecked() is True
    assert widgets["moon"]["trail"].isChecked() is True
    
    assert widgets["star"]["name"].isChecked() is True
    assert widgets["planet"]["name"].isChecked() is True
    assert widgets["moon"]["name"].isChecked() is True

    # 2. Test signal emissions
    active_events = []
    trail_events = []
    name_events = []
    
    panel.category_active_toggled.connect(lambda l, act: active_events.append((l, act)))
    panel.category_trail_toggled.connect(lambda l, trl: trail_events.append((l, trl)))
    panel.category_name_toggled.connect(lambda l, nam: name_events.append((l, nam)))
    
    # Toggle active
    widgets["planet"]["active"].setChecked(False)
    assert ("planet", False) in active_events
    
    # Toggle trail
    widgets["moon"]["trail"].setChecked(False)
    assert ("moon", False) in trail_events
    
    # Toggle name
    widgets["star"]["name"].setChecked(False)
    assert ("star", False) in name_events

    # 3. Test dynamic category checkbox synchronization on populate
    # Set one planet to inactive and populate -> planet active checkbox should be unchecked
    b2.active = False
    panel.populate([b1, b2, b3, b4])
    assert widgets["planet"]["active"].isChecked() is False
    assert widgets["star"]["active"].isChecked() is True
