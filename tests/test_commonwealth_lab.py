"""Side-swapped laboratory comparisons must mirror inputs, including scheduled orders."""
from migration_tools.evaluate_commonwealth import swapped


def test_lab_side_swap_mirrors_scheduled_orders_and_headquarters():
    data=dict(width=100,units=[dict(id=0,army=0,position=dict(x=20,y=30),facing=0,
        order=dict(destination=dict(x=40,y=50),facing=0))],
        commands=[dict(tick=10,regimentId=0,order=dict(kind='move',destination=dict(x=70,y=60),facing=0))],
        armyCommanders=[dict(army=0,commanderId='tadeusz_kosciuszko',position=dict(x=10,y=15))],
        aiArmies=[0],aiStrategies={'0':'balanced'},terrain=dict(hills=[dict(x=25)],forests=[dict(x=35)]))
    mirror=swapped(data)
    assert mirror['units'][0]['army']==1 and mirror['units'][0]['position']==dict(x=80,y=30)
    assert mirror['units'][0]['order']['destination']==dict(x=60,y=50)
    assert mirror['commands'][0]['order']['destination']==dict(x=30,y=60)
    assert mirror['armyCommanders'][0]['position']==dict(x=90,y=15)
    assert mirror['terrain']['hills'][0]['x']==75 and mirror['terrain']['forests'][0]['x']==65
    assert mirror['aiArmies']==[1] and mirror['aiStrategies']=={'1':'balanced'}
    assert swapped(mirror)==data


def test_side_swap_keeps_target_ids_times_and_source_unchanged():
    data=dict(width=100,units=[dict(id=0,army=0,position=dict(x=20,y=30),facing=0)],
        commands=[dict(tick=15,regimentId=0,order=dict(kind='charge',targetId=4))],
        aiArmies=[0],aiStrategies={'0':'balanced'})
    result=swapped(data)
    assert result['commands']==data['commands']
    result['commands'][0]['tick']=99
    assert data['commands'][0]['tick']==15 and data['units'][0]['position']['x']==20
