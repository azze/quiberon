import argparse
from dataclasses import replace
from pathlib import Path
from simulation.terrain import TERRAIN_PRESETS


def main():
    parser=argparse.ArgumentParser(description='Quiberon battlefield sandbox')
    parser.add_argument('--campaign-save',type=Path,default=Path('saves/campaign.json'),help='Between-battle campaign save file')
    parser.add_argument('--scenario',choices=['standard','movement','crowded-line','pursuit','reinforcement','charge','flank-charge','cavalry-pursuit','bayonets','woodland'],help='Skip setup for a scripted scenario')
    parser.add_argument('--config',type=Path,help='Load a saved JSON recipe into setup')
    parser.add_argument('--preset',help='Initial setup preset, e.g. "Infantry Clash"')
    parser.add_argument('--terrain',choices=TERRAIN_PRESETS,help='Terrain preset for the setup')
    parser.add_argument('--terrain-seed',type=int,help='Regenerate terrain with this seed')
    parser.add_argument('--quick',action='store_true',help='Start configured battle without setup/deployment')
    parser.add_argument('--seed',type=int,help='Override seed; blank setup generates one')
    parser.add_argument('--spectator',action='store_true',help='AI controls both armies')
    parser.add_argument('--frames',type=int,help='Exit after N frames (graphical smoke test)')
    args=parser.parse_args()
    from scenarios.battle_config import BattleConfig, ConfigError
    from scenarios.presets import PRESETS,load_preset
    try:
        if args.scenario and (args.config or args.preset or args.quick or args.terrain or args.terrain_seed is not None): parser.error('--scenario cannot be combined with custom setup/terrain arguments')
        config=BattleConfig.load(args.config) if args.config else load_preset(args.preset or PRESETS[0])
        if args.seed is not None: config=replace(config,seed=args.seed)
        if args.terrain is not None or args.terrain_seed is not None:
            config=replace(config,terrain_preset=args.terrain or config.terrain_preset,terrain_seed=args.terrain_seed,terrain=None,placements=())
        if args.spectator: config=config.with_ai_armies((0,1))
        config.validate()
        if args.quick: config=config.prepared()
    except (ConfigError,FileNotFoundError) as exc: parser.error(str(exc))
    import pygame
    from viewer.application import Application
    pygame.init()
    screen=pygame.display.set_mode((1280,800),pygame.RESIZABLE)
    pygame.display.set_caption('Quiberon: Battlefield Sandbox')
    legacy_factory=None
    if args.scenario:
        from scenarios import standard_battle,movement_test,traffic_tests,cavalry_tests,terrain_units
        cavalry_scenarios={'charge':'steady-front','flank-charge':'steady-flank','cavalry-pursuit':'uhlans-routing'}
        if args.scenario in ('bayonets','woodland'):
            legacy_factory=lambda seed:terrain_units.create(seed,mode=args.scenario)
        elif args.scenario in cavalry_scenarios:
            legacy_factory=lambda seed:cavalry_tests.create(cavalry_scenarios[args.scenario],seed)
        elif args.scenario in ('crowded-line','pursuit','reinforcement'):
            legacy_factory=lambda seed:traffic_tests.create(seed,mode=args.scenario)
        else:
            module=movement_test if args.scenario=='movement' else standard_battle
            legacy_factory=lambda seed:module.create(seed,spectator=args.spectator)
    app=Application(screen,config,str(args.config or 'battle_config.json'),legacy_factory,args.seed if args.seed is not None else 1)
    if args.quick: app.start(config)
    elif not (args.scenario or args.config or args.preset or args.terrain or args.terrain_seed is not None or args.spectator):
        app.open_menu(args.campaign_save,args.seed)
    clock=pygame.time.Clock(); frames=0
    while app.running:
        elapsed=clock.tick(60)/1000
        for event in pygame.event.get(): app.handle(event)
        app.update(elapsed); app.draw(clock.get_fps())
        frames+=1
        if args.frames and frames>=args.frames: break
    pygame.quit()

if __name__=='__main__': main()
