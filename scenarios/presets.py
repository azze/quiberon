from importlib.resources import files
from .battle_config import BattleConfig, ConfigError
from .commander_comparisons import COMMANDER_PRESETS

PRESETS = ['Balanced Engagement', 'Infantry Clash', 'Cavalry Assault', 'Artillery Duel', 'Outnumbered']
SPECIALIST_PRESETS = ['Prussian Drill','Woodland Encounter','Open Ground','The Royal Guard',
                      'Cavalry Breakthrough','Rifles and Muskets','Mobile Artillery']
PRESETS += SPECIALIST_PRESETS
PRESETS += COMMANDER_PRESETS

def load_preset(name):
    if name not in PRESETS: raise ConfigError('Unknown preset. Choose: '+', '.join(PRESETS))
    if name in COMMANDER_PRESETS:
        from .commander_comparisons import create
        return create(name)
    import json
    resource = files('scenarios').joinpath('presets', name.lower().replace(' ','_')+'.json')
    return BattleConfig.from_dict(json.loads(resource.read_text(encoding='utf-8')))
