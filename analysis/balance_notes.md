# Initial specialist checks

These measurements predate the sustained-contact melee, gun-crew casualty-floor and army-strategy fixes. They remain historical observations; rerun the commands below for current results.

These are functional probes, not evidence of final balance. The armies are neither budget-matched nor equal in troop count. Both sides use the same rule-based army AI. Seeds 1 and 2 each run twice, with regiment positions/facing/orders mirrored across the battlefield and army IDs exchanged, while preserving the original terrain in each pair. Normal 0.1 s ticks, no rendering.

Commands:

```bash
python -m analysis.matchups --runs 2 --duration 240 --output results-specialists.json
python -m analysis.matchups --preset "Prussian Drill" --preset "Open Ground" --preset "The Royal Guard" --preset "Cavalry Breakthrough" --runs 2 --duration 600 --output results-long.json
```

The first command ran 28 battles. All reached the four-minute limit without an army defeat. Mean losses across four mirrored runs per preset:

| Preset | Specialist-side losses | Opposing losses |
| --- | ---: | ---: |
| Prussian Drill | 272.5 | 446.5 |
| Woodland Encounter | 150.8 | 82.0 |
| Open Ground | 212.3 | 104.5 |
| The Royal Guard | 449.5 | 322.0 |
| Cavalry Breakthrough | 238.3 | 157.5 |
| Rifles and Muskets | 188.8 | 144.3 |
| Mobile Artillery | 233.8 | 253.3 |

The second command ran 16 battles, with a ten-minute limit:

| Preset | Specialist wins | Opposing wins | Timeouts | Mean duration |
| --- | ---: | ---: | ---: | ---: |
| Prussian Drill | 4 | 0 | 0 | 276.4 s |
| Open Ground | 0 | 4 | 0 | 284.7 s |
| The Royal Guard | 0 | 4 | 0 | 351.6 s |
| Cavalry Breakthrough | 0 | 1 | 3 | 562.3 s |

Observations:

- Cohesive Prussians have a strong open-field fire advantage. Disrupted-cohesion unit tests show the drill bonus disappearing; more terrain/flank matchups are needed before tuning the advantage down.
- Woodland specialists are deliberately small and low-volume. They still lose unfavourable conventional firefights, and the open-ground preset's cavalry counter beats them. Woodland Encounter faces infantry only, so its lower losses cannot be attributed solely to trees. Tests separately verify forest mobility, disruption, concealment and clear open-ground visibility.
- Grenadiers provide measurable, non-stacking morale support, but that does not compensate for every numerical disadvantage. Their preset has 1,080 troops versus 1,440, and the supporting army lost all four longer runs. Test defensive placement and reinforcement timing before increasing aura strength.
- Uhlan charges reward broken targets in controlled tests; the stock opposing army does not reliably create or exploit those opportunities. Cavalry Breakthrough remains weak and can stall. Better approach-side selection and combined infantry/cavalry timing are higher priorities than a blanket cavalry damage increase.
- Rifles are sensitive to terrain and deployment side. They gain initial reach but can lose when conventional infantry closes. The current AI does not deliberately seek cover or high ground.
- Horse artillery successfully relocates and fires in integration tests. In the short mixed battle its army inflicted somewhat greater losses on average, but hills and friendly fire introduce substantial variation. This is not a controlled comparison of battery damage or mobility alone.

Next checks should use more seeds, deliberate initial cohesion differences, prepared-front versus flank charges, cornered skirmishers, player-controlled defensive positions and longer terrain battles. Avoid balancing all archetypes toward equal raw win rates.

Metrics have practical limits: `routs_caused` credits the last damaging regiment, not a proven causal chain; `charge_successes` means at least 5% of target baseline strength lost in the charge's resolution; firing/melee seconds count resolution ticks rather than sustained animation or time spent reloading. Cohesion counters sum net tick changes, and trait activations count rate-limited log signals, not every buffed tick. Casualties inflicted include friendly fire. Artillery volley casualties are not musket-volley casualties; cannonball damage instead appears in total inflicted losses.
