# Borderlens item schema — first proposal

**Draft 1 · 27 October 2026 · design only**

This proposes a replacement data shape, not a change to the running app. Current
JSON, captures and game records have not been changed. `proposal-1` below is a
placeholder version, not a released schema number.

Quick links: [decisions](#important-decisions) · [JSON examples](#json-examples) ·
[TypeScript types](#typescript-types) · [review points](#decisions-to-review-before-implementation) ·
[source inventory](#source-inventory)

## Recommendation

Use **one item document format, with a common base and a discriminated union for
item types**. `kind` selects the relevant `weapon`, `shield`, `grenadeMod`,
`classMod`, `artifact`, `upgrade` or `other` block. We get one database/export
contract without filling a shield with irrelevant weapon fields.

Keep the information deep. Make the default presentation selective:

| Data                                                     | Where it belongs                    | Who prepares it                                 | Default presentation                                          |
| -------------------------------------------------------- | ----------------------------------- | ----------------------------------------------- | ------------------------------------------------------------- |
| Identity, origin, obtainable tiers, card stats           | Common item fields                  | App from accepted evidence/game definitions     | Overview and stat panel                                       |
| Each part and its numerical modifiers                    | `partGroups[].options[]`            | App assembles; interpretation only where needed | Separate part rows/tables                                     |
| Special behavior and interactions                        | `mechanics`, `interactions`         | Structured facts plus original AI explanation   | Useful gameplay explanations                                  |
| Skill bonuses, artifact ranks, upgrade tracks            | Relevant typed item block           | App assembles scoped evidence                   | Dedicated type-specific panels                                |
| Where an item comes from                                 | `acquisition`                       | App consolidates sources and conditional cases  | Farming/reward panel                                          |
| Reusable skills and elemental rules                      | `knowledge`                         | Selected shared definitions                     | Expandable relevant background                                |
| Player explanations, practical advice, trivia            | `prose`                             | Original AI wording                             | Normal reading view                                           |
| Exact quotes, disagreements, native attribute operations | Optional private `research` sidecar | Workshop                                        | Research/technical view; omitted from ordinary website export |

**More structured information, fewer paragraphs reciting tables.** A magazine
should have its own row. Its four figures should not become a paragraph merged
with the next magazine.

## What I reviewed

The current local snapshot contains **37 saved web captures attached to 16 item
families**, about **204,214 stored text characters**, plus **21,671 imported raw
record rows**. I reviewed the saved item text, relevant general-page sections,
parts/tables and representative defining game records. A full inventory appears
at the end of this file. No live web fetching or app AI runs were used.

The item set covers:

- Weapons: HellFire, Bone Shredder, Ogre, Ajax's Spear, Havoc, Repeater, Hive Mind,
  Volcano and Whitting's Elephant Gun.
- Shields: Grounded Shield, Omega and Wee Wee's Super Booster.
- Grenade mods: Bouncing Bettie.
- Class mods: Support Gunner, with Bombardier captured as related evidence.
- Artifacts: Brick's Corrosive Artifact.
- Other equipment: Ammo Storage Upgrade.
- General/related material: artifact rules, corrosion, shield construction,
  elemental shields, class-mod construction, Stockpile, grenade categories,
  repeater/launcher parts, weapon titles, vendors, SDUs and loot-source pages.

**Current snapshot limitation:** `sharedScopes` is empty and none of these 37
sources is a manual-text entry. General pages are currently attached to individual
items. They still provide useful examples of shared information; the proposed
private source model also supports parent scopes and manual entries. I am not
claiming those populated shared/manual examples were present in this snapshot.

Full captures also contain later-game sections, recommendation lists, navigation,
example rolls and generic farming guidance. The Support Gunner capture, for
example, contains unrelated armor recommendations; the Artifact/SDU pages span
multiple games. Some shield captures contain additional augment modules whose
applicability needs establishing. **Being present in captured HTML is not proof
that a field belongs to the BL1 item.** Preserve uncertain material privately.

Some Lootlemon fields have labels such as Elements, Listed Projectiles and Shot
Cost without usable text values in the saved capture. Icons or unloaded data may
not survive text capture. This design allows unknown values; it does not invent
values from those labels or assume the whole-page button captured every field.

## Important decisions

### 1. Separate finished stats, modifiers and examples

A card damage range is not a list of part bonuses. A component coefficient is not
the finished item's damage. A table showing one sampled roll is not an obtainable
minimum/maximum for the family.

- `stats`: measured/reported card or gameplay values, with their level, selection
  and condition context.
- `modifiers`: item-level bonuses or penalties.
- `partGroups`: part-specific bonuses and selection constraints.
- `knowledge.skills`: related skill baselines and scaling, not the item's bonuses.
- `research`: raw values, unresolved mappings and illustrative source examples.

Independent min/max stats do **not** assert that one legal roll achieves all those
extrema simultaneously. A maximum-roll bonus does **not** become the guaranteed
bonus on every copy. Do not derive final item ranges merely by adding every
possible part together.

### 2. Use uniform modifier records

Prefer this structure over arbitrary keys such as `{ "reload": 20 }`:

```json
{
  "id": "mag-3-reload",
  "stat": "reload_speed",
  "operation": "reported",
  "value": { "kind": "fixed", "value": 20 },
  "unit": "percent"
}
```

The UI can render **+20% Reload speed** using its stat registry. `reported` means
the source reports that modifier, but its native mathematical operation has not
been established. It is displayable/searchable; it must not silently become an
input to a precise build calculator.

When the operation is established, use `add`, `add_percent`, `multiply` or `set`.
For example, +8 magazine rounds is `add` with `unit: "rounds"`. A factor of 1.2
is `multiply` with `unit: "multiplier"`. A value in percentage points is not a
relative percentage increase. `stage`, `basis` and `stacking` are optional because
we must not guess them.

**Observed reason for caution:** the saved SMG magazine definition contains a
reload-related coefficient near **-0.2**, while Lootlemon labels the magazine
**+20% Reload Speed**. Time, speed and native coefficients are not interchangeable;
negating a value alone does not prove an exact conversion. Native operations stay
in `research.nativeModifiers` until the mapping is understood.

Similarly, the raw magazine has `TechLevelIncrease: 2`. I would store that as
**+2 tech levels**, not claim that the displayed elemental multiplier rises by two.
The raw tech pool, displayed elemental level and artifact effect rank are distinct.

Large signed component coefficients such as -130% spread or -200% fire-rate
modifiers may be legitimate source representations. Do not clamp all percentage
modifiers to ±100, or interpret them as negative finished firing rates.

### 3. Express different numerical meanings explicitly

`NumericValue` distinguishes fixed values, ranges, discrete choices, one-sided
bounds, fractions, formulas and unknowns.

- `[98.3, 98.5]` accuracy choices are not every possible value between them.
- Minimum recharge delay 3.3 seconds is a lower bound, not a fixed delay on every roll.
- “Up to 7.5 rounds/s” must not become “7.5 rounds/s” without qualification.
- Wee Wee's regeneration uses **item/shield level**, not character level.
- An unknown value is not zero; a blank table cell is not automatically +0.
- `int` is a numeric constraint, not a unit. Use rounds, slots, counts, etc.
- A probability can use an exact fraction or an approximate displayed percentage.

Formula expressions are a small data AST, not JavaScript strings to `eval`.
Formula support is for preserving/evaluating established relationships, not
promising a complete game simulation. Do not infer allowable item levels from a
formula, or turn the shield page's speculative delay discussion into a verified
formula.

### 4. Keep one acquisition entity with conditional cases

A mission should appear once with separate reward cases for each playthrough.
An enemy should appear once with separate player-count/edition cases for its drop
rates. Keep requirements, probabilities, reward details and descriptive notes
separate.

Examples from these captures:

- Corrosive Crystal Harvest: rank 2 in the first playthrough; rank 4 in the second.
- Omega from Crawmerax: different listed solo and four-player probabilities.
- Whitting's Elephant Gun: a quest reward and a conditional enemy drop are
  different acquisition routes.
- Hive Mind: new-character selection, chest rewards and an expired code are not
  all ordinary enemy drops.
- General artifact drops can randomise element and class; a mission reward can
  match the recipient's class.

A loot-pool weighting is **not** automatically a per-kill probability. If the
probability denominator is unclear, record `per: "unknown"`; do not imply a
per-kill guarantee. Unknown drop chance means omit `chance`, not zero or 100%.

Aliases need confirmed equivalence. Similar spellings alone do not establish the
same enemy. The new whole Artifact capture again contains both Scar and Skar;
that source disagreement belongs in research, not an automatic spelling guess.

### 5. Model rules without turning them all into prose

Class-mod materials 2 and 3 are mutually exclusive. Elephant Gun's fixed parts
and optional accessory are different rules. A hybrid weapon is a meaningful
variant; ordinary upgrade progression is not six variants.

- `PartGroup.selection` describes how many parts are chosen, when established.
- `coverage: "partial"` says our listed options are not exhaustive; missing
  options are not forbidden.
- A `presence: "none"` option represents an established no-part choice.
- `PartRule` supports required/forbidden combinations.
- `Variant` handles hybrids and their specific changes/selected parts.
- `Condition` supports AND/OR/NOT, playthroughs, editions, levels, materials, aiming,
  skill investment and other real requirements.
- `Condition.kind: "text"` preserves useful unstructured conditions as original AI
  wording. It is display-only; a calculator must not pretend to understand it.

Comparison figures need a baseline. Ajax Ogre's “+55% damage compared with a
normal explosive accessory” must not be added as a +55% intrinsic bonus on top of
the Ogre accessory's own modifier. Use a variant comparison with its baseline,
and preserve whether a difference is percentage points or a relative change.

### 6. Separate content pack, edition and naming

The game/series is implied; there is **no public `game` or `series` field**.

- `origin.contentPack`: base game or expansion, `null` when unknown.
- `origin.introducedEdition`: optional original/enhanced distinction.
- `availability.editions`: where the item can be obtained, independently of DLC.
- `Acquisition.contentPack`: where that source is, not where the item originated.
- Hive Mind is an Enhanced-edition item; Enhanced is not a fifth DLC.
- Unique/named status is not itself a rarity tier. Wee Wee's Super Booster can
  be a unique item with multiple obtainable rarity tiers.
- Prefixes and title rules are not automatically alternate family names.
- Keep immutable item IDs when names/types are corrected. Confirmed aliases and
  optional old slugs can preserve links; manual name locks remain workshop state.

Use `KnownSet` to distinguish a complete property list from a partial list.
Lootlemon displaying Epic on a maximum-roll class-mod page does not establish
that Epic is the only obtainable tier. An unknown manufacturer list is omitted,
not filled from descriptive words such as “Eridian artifact.”

### 7. Preserve shared knowledge without giving it the wrong owner

The database can normalise skills, shared mechanics, parts and acquisition
entities into reusable records. A self-contained item export embeds only the
relevant referenced knowledge/part definitions, once per document. It must not
include every page under Everything simply because the item inherits it.

`knowledge.skills` can contain Stockpile's rank-by-rank ammunition rates.
`classMod.skillBonuses` contains the Support Gunner's bonus skill points. Those
are different things; Stockpile's rates are not direct COM stat bonuses.

Likewise, the corrosive profile can explain damage against armor without putting
+100% armor damage in the artifact's card-stat table. Shared-rule applicability
selects useful background; it is not proof of ownership or an extra bonus to add
again. Parent inheritance and Auto/Always/Never remain evidence-selection policy,
not fields determining gameplay compatibility.

Do not duplicate the same effect as independently additive item and part
modifiers. A defining part may explain the source of an item-level behavior
without creating a second copy of the bonus. At implementation time, derived
views need stable IDs/dependency links, not two unlabelled numerical copies.

## Proposed layout at a glance

| Block                                    | Meaning                                                              |
| ---------------------------------------- | -------------------------------------------------------------------- |
| `kind` + one typed block                 | The equipment type and its specific properties                       |
| `origin`, `availability`, `requirements` | Introduction, obtainability, and use/equip requirements              |
| `manufacturers`, `rarities`, `elements`  | Accepted property sets and completeness                              |
| `prose`                                  | Original explanation, advice, notes and trivia                       |
| `stats`                                  | Card/gameplay observations, levels and measurement context           |
| `modifiers`                              | Item bonuses, conditions, recipients and mathematical interpretation |
| `mechanics`, `interactions`              | Triggered behaviors, quirks, bugs and synergies                      |
| `partGroups`                             | Individual parts, options, modifiers and combination rules           |
| `variants`                               | Meaningful hybrids/alternatives, not ordinary rank progression       |
| `acquisition`                            | Source entities with scoped cases, probabilities and rewards         |
| `knowledge`                              | Relevant shared skill/mechanic definitions                           |
| `tables`, `economy`, `naming`            | Other useful structured tables, prices and naming rules              |
| `references`                             | Evidence sources, distinct from acquisition sources                  |
| `research`                               | Optional private audit trail; not player-facing prose                |

An item can omit unused optional fields. Unknowns do not need a forest of nulls.
`origin.contentPack: null`, `image: null` and `NumericValue.kind: "unknown"` are
explicit unknowns when useful. An empty **complete** set asserts there are no
members; an omitted set means not established/not supplied. Do not fill arrays
merely to satisfy a schema.

## JSON examples

These are **design examples using the saved evidence**, not replacements for
current item JSON and not independently verified game reference entries. They
show deliberately selected fields. Most part lists and acquisitions are shorter
than a complete production entry; partial lists are marked accordingly.

The prose below is original. Proper names, labels and exact red text are retained
where appropriate. Stable public IDs are illustrative except existing item IDs,
which are preserved. Missing optional fields are intentional.


### Hypothetical examples showing all fields and values

```json

```


### A. Weapon: HellFire, with separate magazines

The two magazines are independent rows. The full capture contains other magazines and many other part groups; this example is partial. The +2 tech modifier comes from the captured native magazine definition. Reload/equip percentages use `reported` until their native interpretation is mapped. The Wiki fire-rate range has no explicit unit in the captured stat table, so the example does not silently supply rounds/second. The two magazine rows are not prose paragraphs.

```json
{
  "schemaVersion": "proposal-1",
  "revision": 1,
  "id": "smgs-hellfire-559b69",
  "slug": "hellfire",
  "name": "HellFire",
  "kind": "weapon",
  "origin": {
    "contentPack": "base_game"
  },
  "prose": {
    "summary": "An incendiary SMG whose repeated hits build sustained burning damage.",
    "overview": [
      "HellFire combines rapid attacks with an extra incendiary explosion, making sustained fire its defining strength."
    ]
  },
  "weapon": {
    "type": "smg",
    "ammoPool": "smg"
  },
  "image": "weapons/hellfire.png",
  "manufacturers": {
    "values": ["Maliwan"],
    "coverage": "complete"
  },
  "rarities": {
    "values": ["legendary"],
    "coverage": "complete"
  },
  "elements": {
    "values": ["incendiary"],
    "coverage": "complete"
  },
  "redText": "We don't need no water...",
  "naming": {
    "prefixes": {
      "values": ["Combustion"],
      "coverage": "complete"
    }
  },
  "stats": [
    {
      "id": "card-damage",
      "stat": "damage",
      "value": {
        "kind": "range",
        "min": 20,
        "max": 359
      },
      "unit": "damage",
      "context": {
        "surface": "card",
        "selection": "reported_range"
      },
      "referenceIds": ["hellfire-wiki"]
    },
    {
      "id": "card-accuracy",
      "stat": "accuracy",
      "value": {
        "kind": "range",
        "min": 78.7,
        "max": 93.5
      },
      "unit": "rating",
      "context": {
        "surface": "card",
        "selection": "reported_range"
      },
      "referenceIds": ["hellfire-wiki"]
    },
    {
      "id": "card-fire-rate",
      "stat": "fire_rate",
      "value": {
        "kind": "range",
        "min": 2.5,
        "max": 12.5
      },
      "unit": "unknown",
      "context": {
        "surface": "card",
        "selection": "reported_range"
      },
      "referenceIds": ["hellfire-wiki"]
    }
  ],
  "mechanics": [
    {
      "id": "extra-fire-explosion",
      "name": "Extra incendiary explosion",
      "trigger": "on_shot",
      "description": "Each shot adds a fiery explosion that can keep a target burning.",
      "parameters": [
        {
          "id": "explosion-damage",
          "stat": "splash_damage",
          "value": {
            "kind": "fixed",
            "value": 60
          },
          "unit": "percent",
          "context": {
            "surface": "gameplay",
            "selection": "fixed_rule"
          },
          "referenceIds": ["hellfire-lootlemon"]
        },
        {
          "id": "explosion-ignite",
          "stat": "ignite_chance",
          "value": {
            "kind": "fixed",
            "value": 100
          },
          "unit": "percent",
          "context": {
            "surface": "gameplay",
            "selection": "fixed_rule"
          },
          "referenceIds": ["hellfire-lootlemon"]
        }
      ],
      "referenceIds": ["hellfire-lootlemon"]
    }
  ],
  "partGroups": [
    {
      "id": "magazine",
      "slot": "magazine",
      "name": "Magazines",
      "coverage": "partial",
      "options": [
        {
          "id": "smg-mag-2",
          "name": "Magazine 2",
          "sourceNames": ["Mag_2"],
          "modifiers": [
            {
              "id": "mag-2-reload",
              "stat": "reload_speed",
              "operation": "reported",
              "value": {
                "kind": "fixed",
                "value": 15
              },
              "unit": "percent"
            }
          ],
          "referenceIds": ["hellfire-lootlemon"]
        },
        {
          "id": "smg-mag-3",
          "name": "Magazine 3",
          "sourceNames": ["Mag_3"],
          "modifiers": [
            {
              "id": "mag-3-capacity",
              "stat": "magazine_capacity",
              "operation": "add",
              "value": {
                "kind": "fixed",
                "value": 8
              },
              "unit": "rounds"
            },
            {
              "id": "mag-3-reload",
              "stat": "reload_speed",
              "operation": "reported",
              "value": {
                "kind": "fixed",
                "value": 20
              },
              "unit": "percent"
            },
            {
              "id": "mag-3-tech",
              "stat": "tech_level",
              "operation": "add",
              "value": {
                "kind": "fixed",
                "value": 2
              },
              "unit": "tech_levels"
            },
            {
              "id": "mag-3-equip",
              "stat": "equip_speed",
              "operation": "reported",
              "value": {
                "kind": "fixed",
                "value": -10
              },
              "unit": "percent"
            }
          ],
          "referenceIds": ["hellfire-lootlemon", "game-smg-mag-3"]
        }
      ]
    },
    {
      "id": "accessory",
      "slot": "accessory",
      "name": "Defining accessory",
      "coverage": "complete",
      "selection": {
        "min": 1,
        "max": 1
      },
      "options": [
        {
          "id": "hellfire-accessory",
          "name": "HellFire accessory",
          "role": "defining",
          "modifiers": [
            {
              "id": "hellfire-tech",
              "stat": "tech_level",
              "operation": "add",
              "value": {
                "kind": "fixed",
                "value": 14
              },
              "unit": "tech_levels"
            }
          ],
          "referenceIds": ["hellfire-wiki"]
        }
      ]
    }
  ],
  "acquisition": [
    {
      "id": "smg-world-pool",
      "method": "drop",
      "source": {
        "id": "smg-world-pool-pool",
        "name": "SMG pool",
        "kind": "loot_pool"
      },
      "cases": [
        {
          "id": "world-drop"
        }
      ],
      "referenceIds": ["hellfire-lootlemon"]
    }
  ],
  "references": [
    {
      "id": "hellfire-wiki",
      "kind": "web",
      "title": "Hellfire (Borderlands)",
      "url": "https://borderlands.fandom.com/wiki/Hellfire_(Borderlands)"
    },
    {
      "id": "hellfire-lootlemon",
      "kind": "web",
      "title": "Borderlands 1Hellfire",
      "url": "https://www.lootlemon.com/weapon/hellfire-bl1"
    },
    {
      "id": "game-smg-mag-3",
      "kind": "game_data",
      "title": "Captured SMG Magazine 3 definition"
    }
  ]
}
```

### B. Shield: Wee Wee's Super Booster

The health formula and max-health effect are structured. They are not also repeated as additive material modifiers. The minimum delay is a bound; it is not a fabricated whole shield capacity/recharge range. No resistance element is inferred simply because this is a shield.

```json
{
  "schemaVersion": "proposal-1",
  "revision": 1,
  "id": "shields-wee-wee-s-super-booster-8c22d5",
  "slug": "wee-wees-super-booster",
  "name": "Wee Wee's Super Booster",
  "kind": "shield",
  "origin": {
    "contentPack": "base_game"
  },
  "prose": {
    "summary": "A shield that adds maximum health and restores health while equipped.",
    "overview": [
      "This shield supports steady health recovery alongside its normal shielding, offering an alternative to relying entirely on shield recharge."
    ]
  },
  "shield": {},
  "manufacturers": {
    "values": ["Pangolin"],
    "coverage": "complete"
  },
  "rarities": {
    "values": ["uncommon", "rare", "epic"],
    "coverage": "complete"
  },
  "tags": ["unique"],
  "stats": [
    {
      "id": "minimum-delay",
      "stat": "shield_recharge_delay",
      "value": {
        "kind": "bound",
        "side": "minimum",
        "value": 4.375
      },
      "unit": "seconds",
      "context": {
        "surface": "gameplay",
        "selection": "fixed_rule"
      },
      "referenceIds": ["wee-lootlemon"]
    }
  ],
  "modifiers": [
    {
      "id": "maximum-health",
      "stat": "max_health",
      "operation": "add_percent",
      "value": {
        "kind": "fixed",
        "value": 15
      },
      "unit": "percent",
      "target": {
        "recipient": "owner"
      },
      "referenceIds": ["wee-wiki", "wee-lootlemon"]
    },
    {
      "id": "health-restoration",
      "stat": "health_regeneration",
      "operation": "add",
      "value": {
        "kind": "formula",
        "expression": {
          "op": "multiply",
          "args": [
            {
              "op": "constant",
              "value": 0.2
            },
            {
              "op": "add",
              "args": [
                {
                  "op": "variable",
                  "name": "item_level"
                },
                {
                  "op": "constant",
                  "value": 9
                }
              ]
            }
          ]
        }
      },
      "unit": "health_per_second",
      "target": {
        "recipient": "owner"
      },
      "referenceIds": ["wee-lootlemon"]
    }
  ],
  "partGroups": [
    {
      "id": "body",
      "slot": "body",
      "name": "Body",
      "coverage": "complete",
      "selection": {
        "min": 1,
        "max": 1
      },
      "options": [
        {
          "id": "shield-body-2",
          "name": "Body 2",
          "role": "required",
          "referenceIds": ["wee-wiki"]
        }
      ]
    },
    {
      "id": "material",
      "slot": "material",
      "name": "Defining material",
      "coverage": "complete",
      "selection": {
        "min": 1,
        "max": 1
      },
      "options": [
        {
          "id": "wee-material",
          "name": "Super Booster material",
          "role": "defining",
          "referenceIds": ["wee-wiki"]
        }
      ]
    }
  ],
  "acquisition": [
    {
      "id": "king-wee-wee",
      "method": "drop",
      "source": {
        "id": "king-wee-wee",
        "name": "King Wee Wee",
        "kind": "enemy",
        "locations": [
          {
            "id": "tetanus-warren",
            "name": "Tetanus Warren"
          }
        ]
      },
      "cases": [
        {
          "id": "guaranteed-drop",
          "chance": {
            "value": {
              "kind": "fixed",
              "value": 100
            },
            "unit": "percent",
            "per": "kill"
          }
        }
      ],
      "referenceIds": ["wee-lootlemon", "king-wee-lootlemon"]
    }
  ],
  "interactions": [
    {
      "id": "respawn-difference",
      "kind": "behavior",
      "when": {
        "kind": "edition",
        "values": ["enhanced"]
      },
      "description": "King Wee Wee can respawn in Enhanced, allowing repeat farming.",
      "referenceIds": ["wee-wiki"]
    }
  ],
  "references": [
    {
      "id": "wee-wiki",
      "kind": "web",
      "title": "Wee Wee's Super Booster",
      "url": "https://borderlands.fandom.com/wiki/Wee_Wee%27s_Super_Booster"
    },
    {
      "id": "wee-lootlemon",
      "kind": "web",
      "title": "Borderlands 1Wee Wee's Super Booster",
      "url": "https://www.lootlemon.com/shield/wee-wees-super-booster-bl1"
    },
    {
      "id": "king-wee-lootlemon",
      "kind": "web",
      "title": "Borderlands 1King Wee Wee",
      "url": "https://www.lootlemon.com/loot-source/king-wee-wee"
    }
  ]
}
```

### C. Grenade mod: Bouncing Bettie

The saved Wiki describes two seconds and twelve children; Lootlemon describes 2.5 seconds and eleven. This draft example selects the direct Lootlemon numbers, not a false 2–2.5-second or 11–12-child roll range. That disagreement should stay in a private decision record. Rarity/elements are intentionally not claimed as complete from ambiguous labels/icons.

```json
{
  "schemaVersion": "proposal-1",
  "revision": 1,
  "id": "grenade-mods-bouncing-bettie-2c1ca5",
  "slug": "bouncing-bettie",
  "name": "Bouncing Bettie",
  "kind": "grenade_mod",
  "origin": {
    "contentPack": "base_game"
  },
  "prose": {
    "summary": "A rising grenade that scatters child grenades across a horizontal area.",
    "overview": [
      "Bouncing Bettie rewards careful placement against groups. It needs room to rise before distributing its damaging child grenades."
    ]
  },
  "grenadeMod": {
    "behavior": "bouncing_bettie",
    "activation": "fuse",
    "fuse": {
      "value": {
        "kind": "fixed",
        "value": 2.5
      },
      "unit": "seconds",
      "referenceIds": ["bettie-lootlemon"]
    },
    "childCount": {
      "value": {
        "kind": "fixed",
        "value": 11
      },
      "unit": "projectiles",
      "referenceIds": ["bettie-lootlemon"]
    },
    "initialBlastDealsDamage": false
  },
  "manufacturers": {
    "values": ["Dahl"],
    "coverage": "complete"
  },
  "mechanics": [
    {
      "id": "airborne-dispersal",
      "name": "Airborne dispersal",
      "trigger": "on_detonation",
      "description": "The launch itself deals no damage; the scattered children deliver the damaging blasts.",
      "referenceIds": ["bettie-wiki"]
    }
  ],
  "acquisition": [
    {
      "id": "grenade-world-pool",
      "method": "drop",
      "source": {
        "id": "grenade-world-pool-pool",
        "name": "Grenade pool",
        "kind": "loot_pool"
      },
      "cases": [
        {
          "id": "world-drop"
        }
      ],
      "referenceIds": ["bettie-lootlemon"]
    }
  ],
  "interactions": [
    {
      "id": "mid-flight-element-change",
      "kind": "behavior",
      "when": {
        "kind": "mode",
        "value": "single_player"
      },
      "description": "Changing to another Bouncing Bettie mod before detonation can change the thrown grenade's element.",
      "referenceIds": ["bettie-wiki"]
    }
  ],
  "references": [
    {
      "id": "bettie-wiki",
      "kind": "web",
      "title": "Bouncing Bettie Grenade",
      "url": "https://borderlands.fandom.com/wiki/Bouncing_Bettie_Grenade"
    },
    {
      "id": "bettie-lootlemon",
      "kind": "web",
      "title": "Borderlands 1Bouncing Bettie",
      "url": "https://www.lootlemon.com/grenade-mod/bouncing-bettie-bl1"
    }
  ]
}
```

### D. Class mod: Support Gunner

The Wiki card bonus has an unspecified unit, separate from the per-ammo-pool regeneration rates. Those rates are maximum-roll values, not guaranteed minima. Material selection prevents both secondary bonuses from applying. The skill-point patterns constrain the possible allocations; they do not mean every boosted skill independently receives four points. The Stockpile table is a partial sample of a related skill, not another item bonus.

```json
{
  "schemaVersion": "proposal-1",
  "revision": 1,
  "id": "class-mods-roland-support-gunner-098e68",
  "slug": "support-gunner",
  "name": "Support Gunner",
  "kind": "class_mod",
  "origin": {
    "contentPack": "base_game"
  },
  "prose": {
    "summary": "A Roland class mod focused on team ammunition regeneration.",
    "overview": [
      "Support Gunner helps sustain ammunition supplies and boosts three skills. Its optional secondary bonus depends on the selected material."
    ]
  },
  "classMod": {
    "character": "roland",
    "skillBonuses": [
      {
        "skill": {
          "id": "roland-stockpile",
          "name": "Stockpile"
        },
        "points": {
          "kind": "choices",
          "values": [2, 3, 4]
        },
        "when": {
          "kind": "skill_rank",
          "skill": {
            "id": "roland-stockpile",
            "name": "Stockpile"
          },
          "minimumInvested": 1
        }
      },
      {
        "skill": {
          "id": "roland-impact",
          "name": "Impact"
        },
        "points": {
          "kind": "choices",
          "values": [2, 3, 4]
        },
        "when": {
          "kind": "skill_rank",
          "skill": {
            "id": "roland-impact",
            "name": "Impact"
          },
          "minimumInvested": 1
        }
      },
      {
        "skill": {
          "id": "roland-barrage",
          "name": "Barrage"
        },
        "points": {
          "kind": "choices",
          "values": [2, 3, 4]
        },
        "when": {
          "kind": "skill_rank",
          "skill": {
            "id": "roland-barrage",
            "name": "Barrage"
          },
          "minimumInvested": 1
        }
      }
    ],
    "maxBoostedSkills": 3,
    "bonusPatterns": [
      {
        "points": [4, 3, 3],
        "assignment": "any_permutation"
      },
      {
        "points": [3, 2, 2],
        "assignment": "any_permutation"
      },
      {
        "points": [4, 3],
        "assignment": "any_permutation"
      },
      {
        "points": [3, 3],
        "assignment": "any_permutation"
      },
      {
        "points": [3],
        "assignment": "any_permutation"
      },
      {
        "points": [2],
        "assignment": "any_permutation"
      }
    ]
  },
  "manufacturers": {
    "values": ["S&S Munitions", "Vladof"],
    "coverage": "complete"
  },
  "rarities": {
    "values": ["uncommon", "rare", "epic"],
    "coverage": "complete"
  },
  "stats": [
    {
      "id": "ammo-card-bonus",
      "stat": "ammo_regeneration",
      "value": {
        "kind": "range",
        "min": 2,
        "max": 25
      },
      "unit": "unknown",
      "context": {
        "surface": "card",
        "selection": "reported_range"
      },
      "referenceIds": ["class-mods-wiki"]
    }
  ],
  "modifiers": [
    {
      "id": "combat_rifle-regen",
      "stat": "ammo_regeneration",
      "operation": "add",
      "value": {
        "kind": "bound",
        "side": "maximum",
        "value": 5
      },
      "unit": "rounds_per_second",
      "target": {
        "recipient": "team",
        "includesOwner": true,
        "ammoPools": ["combat_rifle"]
      },
      "context": {
        "selection": "maximum_roll",
        "surface": "gameplay"
      },
      "referenceIds": ["support-lootlemon"]
    },
    {
      "id": "launcher-regen",
      "stat": "ammo_regeneration",
      "operation": "add",
      "value": {
        "kind": "bound",
        "side": "maximum",
        "value": 1.5
      },
      "unit": "rounds_per_second",
      "target": {
        "recipient": "team",
        "includesOwner": true,
        "ammoPools": ["launcher"]
      },
      "context": {
        "selection": "maximum_roll",
        "surface": "gameplay"
      },
      "referenceIds": ["support-lootlemon"]
    },
    {
      "id": "pistol-regen",
      "stat": "ammo_regeneration",
      "operation": "add",
      "value": {
        "kind": "bound",
        "side": "maximum",
        "value": 10
      },
      "unit": "rounds_per_second",
      "target": {
        "recipient": "team",
        "includesOwner": true,
        "ammoPools": ["pistol"]
      },
      "context": {
        "selection": "maximum_roll",
        "surface": "gameplay"
      },
      "referenceIds": ["support-lootlemon"]
    },
    {
      "id": "revolver-regen",
      "stat": "ammo_regeneration",
      "operation": "add",
      "value": {
        "kind": "bound",
        "side": "maximum",
        "value": 2.5
      },
      "unit": "rounds_per_second",
      "target": {
        "recipient": "team",
        "includesOwner": true,
        "ammoPools": ["revolver"]
      },
      "context": {
        "selection": "maximum_roll",
        "surface": "gameplay"
      },
      "referenceIds": ["support-lootlemon"]
    },
    {
      "id": "shotgun-regen",
      "stat": "ammo_regeneration",
      "operation": "add",
      "value": {
        "kind": "bound",
        "side": "maximum",
        "value": 2.5
      },
      "unit": "rounds_per_second",
      "target": {
        "recipient": "team",
        "includesOwner": true,
        "ammoPools": ["shotgun"]
      },
      "context": {
        "selection": "maximum_roll",
        "surface": "gameplay"
      },
      "referenceIds": ["support-lootlemon"]
    },
    {
      "id": "smg-regen",
      "stat": "ammo_regeneration",
      "operation": "add",
      "value": {
        "kind": "bound",
        "side": "maximum",
        "value": 7.5
      },
      "unit": "rounds_per_second",
      "target": {
        "recipient": "team",
        "includesOwner": true,
        "ammoPools": ["smg"]
      },
      "context": {
        "selection": "maximum_roll",
        "surface": "gameplay"
      },
      "referenceIds": ["support-lootlemon"]
    },
    {
      "id": "sniper-regen",
      "stat": "ammo_regeneration",
      "operation": "add",
      "value": {
        "kind": "bound",
        "side": "maximum",
        "value": 2
      },
      "unit": "rounds_per_second",
      "target": {
        "recipient": "team",
        "includesOwner": true,
        "ammoPools": ["sniper"]
      },
      "context": {
        "selection": "maximum_roll",
        "surface": "gameplay"
      },
      "referenceIds": ["support-lootlemon"]
    },
    {
      "id": "secondary-magazine",
      "stat": "magazine_capacity",
      "operation": "reported",
      "value": {
        "kind": "fixed",
        "value": 42
      },
      "unit": "percent",
      "target": {
        "recipient": "team",
        "includesOwner": true
      },
      "when": {
        "kind": "part_selected",
        "groupId": "material",
        "optionId": "material-2"
      },
      "context": {
        "selection": "maximum_roll"
      },
      "referenceIds": ["support-lootlemon"]
    },
    {
      "id": "secondary-accuracy",
      "stat": "accuracy",
      "operation": "reported",
      "value": {
        "kind": "fixed",
        "value": 56
      },
      "unit": "percent",
      "target": {
        "recipient": "team",
        "includesOwner": true
      },
      "when": {
        "kind": "part_selected",
        "groupId": "material",
        "optionId": "material-3"
      },
      "context": {
        "selection": "maximum_roll"
      },
      "referenceIds": ["support-lootlemon"]
    }
  ],
  "partGroups": [
    {
      "id": "material",
      "slot": "material",
      "name": "Material",
      "coverage": "complete",
      "selection": {
        "min": 1,
        "max": 1
      },
      "options": [
        {
          "id": "material-1",
          "name": "Material 1"
        },
        {
          "id": "material-2",
          "name": "Material 2"
        },
        {
          "id": "material-3",
          "name": "Material 3"
        }
      ],
      "referenceIds": ["class-mods-wiki"]
    }
  ],
  "knowledge": {
    "skills": [
      {
        "id": "roland-stockpile",
        "name": "Stockpile",
        "character": "roland",
        "baseMaxRank": 5,
        "boostedMaxRank": 9,
        "description": "Stockpile supplies ammunition to the team near Roland's turret.",
        "scaling": [
          {
            "id": "stockpile-selected-ranks",
            "title": "Stockpile ammunition regeneration at selected effective ranks",
            "coverage": "partial",
            "columns": [
              {
                "id": "rank",
                "label": "Effective rank",
                "unit": "skill_points"
              },
              {
                "id": "smg",
                "label": "SMG regeneration",
                "stat": "ammo_regeneration",
                "unit": "rounds_per_second"
              },
              {
                "id": "launcher",
                "label": "Launcher regeneration",
                "stat": "ammo_regeneration",
                "unit": "rounds_per_second"
              }
            ],
            "rows": [
              {
                "rank": 1,
                "smg": 0.9,
                "launcher": 0.3
              },
              {
                "rank": 5,
                "smg": 4.5,
                "launcher": 1.5
              },
              {
                "rank": 9,
                "smg": 8.1,
                "launcher": 2.7
              }
            ],
            "referenceIds": ["stockpile-lootlemon"]
          }
        ],
        "referenceIds": ["stockpile-lootlemon"]
      }
    ]
  },
  "acquisition": [
    {
      "id": "roland-world-pool",
      "method": "drop",
      "source": {
        "id": "roland-world-pool-pool",
        "name": "Roland class-mod pool",
        "kind": "loot_pool"
      },
      "cases": [
        {
          "id": "world-drop"
        }
      ],
      "referenceIds": ["support-lootlemon"]
    }
  ],
  "references": [
    {
      "id": "support-lootlemon",
      "kind": "web",
      "title": "Borderlands 1Support Gunner",
      "url": "https://www.lootlemon.com/class-mod/support-gunner-roland-bl1"
    },
    {
      "id": "class-mods-wiki",
      "kind": "web",
      "title": "Class Mod (Borderlands)",
      "url": "https://borderlands.fandom.com/wiki/Class_Mod_(Borderlands)"
    },
    {
      "id": "stockpile-lootlemon",
      "kind": "web",
      "title": "Roland SkillStockpile",
      "url": "https://www.lootlemon.com/skill/stockpile-roland"
    }
  ]
}
```

### E. Artifact: Brick's Corrosive Artifact

One mission has two scoped reward cases. Rank progression stays in the artifact block, not variants. Rank 6’s documented requirement is separate from example item levels/prices in the comparison table. The shared corrosion rule is contextual knowledge, not an extra intrinsic +15% Berserk damage stat.

```json
{
  "schemaVersion": "proposal-1",
  "revision": 1,
  "id": "artifacts-brick-corrosive-artifact-e23b6e",
  "slug": "corrosive-artifact",
  "name": "Corrosive Artifact",
  "kind": "artifact",
  "origin": {
    "contentPack": "base_game"
  },
  "prose": {
    "summary": "A permanent corrosive upgrade for Brick's Berserk attacks.",
    "overview": [
      "Using this artifact unlocks a corrosive option for Berserk. Stronger ranks replace weaker learned ranks of the same element."
    ]
  },
  "artifact": {
    "character": "brick",
    "actionSkill": {
      "id": "brick-berserk",
      "name": "Berserk"
    },
    "use": "consumed_permanent_unlock",
    "maximumEffectRank": 6,
    "higherRankReplacesLower": true,
    "exclusiveGroup": "action-skill-artifact",
    "canDisable": true,
    "rankRequirements": [
      {
        "rank": 6,
        "when": {
          "kind": "level",
          "subject": "character",
          "min": 44
        },
        "basis": "rule",
        "referenceIds": ["artifact-wiki"]
      }
    ],
    "shape": "cube"
  },
  "elements": {
    "values": ["corrosive"],
    "coverage": "complete"
  },
  "acquisition": [
    {
      "id": "corrosive-crystal-harvest",
      "method": "mission_reward",
      "source": {
        "id": "corrosive-crystal-harvest",
        "name": "Corrosive Crystal Harvest",
        "kind": "mission",
        "locations": [
          {
            "id": "tetanus-warren",
            "name": "Tetanus Warren"
          }
        ]
      },
      "cases": [
        {
          "id": "first-playthrough",
          "when": {
            "kind": "all",
            "conditions": [
              {
                "kind": "playthrough",
                "values": ["first"]
              },
              {
                "kind": "mission",
                "mission": {
                  "id": "power-to-the-people",
                  "name": "Power To The People"
                },
                "state": "completed"
              },
              {
                "kind": "objective",
                "name": "Collect Corrosive Crystals",
                "quantity": 50
              }
            ]
          },
          "rewards": [
            {
              "kind": "item",
              "effectRank": {
                "kind": "fixed",
                "value": 2
              },
              "elementSelection": "fixed",
              "element": "corrosive",
              "classSelection": "recipient"
            }
          ]
        },
        {
          "id": "second-playthrough",
          "when": {
            "kind": "all",
            "conditions": [
              {
                "kind": "playthrough",
                "values": ["second"]
              },
              {
                "kind": "mission",
                "mission": {
                  "id": "power-to-the-people",
                  "name": "Power To The People"
                },
                "state": "completed"
              },
              {
                "kind": "objective",
                "name": "Collect Corrosive Crystals",
                "quantity": 50
              }
            ]
          },
          "rewards": [
            {
              "kind": "item",
              "effectRank": {
                "kind": "fixed",
                "value": 4
              },
              "elementSelection": "fixed",
              "element": "corrosive",
              "classSelection": "recipient"
            }
          ]
        }
      ],
      "referenceIds": ["artifact-wiki", "crystal-quest-wiki"]
    }
  ],
  "knowledge": {
    "sharedMechanics": [
      {
        "id": "corrode-followup-damage",
        "name": "Corroding targets",
        "description": "Subsequent attacks gain damage against an enemy affected by corrosion.",
        "appliesTo": {
          "elements": ["corrosive"]
        },
        "modifiers": [
          {
            "id": "corroding-target-bonus",
            "stat": "damage",
            "operation": "reported",
            "value": {
              "kind": "fixed",
              "value": 15
            },
            "unit": "percent",
            "target": {
              "recipient": "hit_target"
            },
            "when": {
              "kind": "state",
              "value": "target_corroding"
            }
          }
        ],
        "referenceIds": ["corrosive-wiki"]
      }
    ]
  },
  "references": [
    {
      "id": "artifact-wiki",
      "kind": "web",
      "title": "Artifact",
      "url": "https://borderlands.fandom.com/wiki/Artifact"
    },
    {
      "id": "crystal-quest-wiki",
      "kind": "web",
      "title": "Corrosive Crystal Harvest",
      "url": "https://borderlands.fandom.com/wiki/Corrosive_Crystal_Harvest"
    },
    {
      "id": "corrosive-wiki",
      "kind": "web",
      "title": "Corrosive",
      "url": "https://borderlands.fandom.com/wiki/Corrosive"
    }
  ]
}
```

### F. Other equipment as a typed upgrade: Ammo Storage Upgrade

Only two ammo tracks and two purchased tiers per track are shown; intermediate tiers and the other pools remain possible. The highest tier’s increase is not inferred as the difference from the last displayed example tier. Prices are omitted here rather than turning a source-table price into a universally guaranteed price.

```json
{
  "schemaVersion": "proposal-1",
  "revision": 1,
  "id": "other-equipment-ammo-storage-upgrade-acb410",
  "slug": "ammo-storage-upgrade",
  "name": "Ammo Storage Upgrade",
  "kind": "upgrade",
  "origin": {
    "contentPack": "base_game"
  },
  "prose": {
    "summary": "Permanent upgrades that raise ammunition reserve capacities.",
    "overview": [
      "Ammo upgrades increase the capacity of individual ammunition pools. Higher tiers can be purchased without buying every lower tier first."
    ]
  },
  "upgrade": {
    "type": "ammo_capacity",
    "use": "permanent_on_purchase",
    "purchaseOrder": "can_skip_tiers",
    "tracks": [
      {
        "id": "smg-capacity",
        "target": "smg",
        "unit": "rounds",
        "initial": {
          "kind": "fixed",
          "value": 360
        },
        "coverage": "partial",
        "tiers": [
          {
            "id": "smg-tier-1",
            "tier": 1,
            "label": "White",
            "capacity": {
              "kind": "fixed",
              "value": 540
            },
            "increase": {
              "kind": "fixed",
              "value": 180
            }
          },
          {
            "id": "smg-tier-6",
            "tier": 6,
            "label": "Dark orange",
            "capacity": {
              "kind": "fixed",
              "value": 1440
            }
          }
        ],
        "referenceIds": ["sdu-wiki"]
      },
      {
        "id": "pistol-capacity",
        "target": "pistol",
        "unit": "rounds",
        "initial": {
          "kind": "fixed",
          "value": 200
        },
        "coverage": "partial",
        "tiers": [
          {
            "id": "pistol-tier-1",
            "tier": 1,
            "label": "White",
            "capacity": {
              "kind": "fixed",
              "value": 300
            },
            "increase": {
              "kind": "fixed",
              "value": 100
            }
          },
          {
            "id": "pistol-tier-6",
            "tier": 6,
            "label": "Dark orange",
            "capacity": {
              "kind": "fixed",
              "value": 800
            }
          }
        ],
        "referenceIds": ["sdu-wiki"]
      }
    ]
  },
  "acquisition": [
    {
      "id": "ammo-vendor",
      "method": "purchase",
      "source": {
        "id": "ammo-vendor",
        "name": "Ammunition vending machine",
        "kind": "vendor"
      },
      "cases": [
        {
          "id": "vendor-stock",
          "notes": "The available upgrade tier depends on the vendor and game progression."
        }
      ],
      "referenceIds": ["sdu-wiki", "vendors-wiki"]
    }
  ],
  "references": [
    {
      "id": "sdu-wiki",
      "kind": "web",
      "title": "Storage Deck Upgrade",
      "url": "https://borderlands.fandom.com/wiki/Storage_Deck_Upgrade"
    },
    {
      "id": "vendors-wiki",
      "kind": "web",
      "title": "Vending machine",
      "url": "https://borderlands.fandom.com/wiki/Vending_machine"
    }
  ]
}
```

### G. Focused fragment: Omega's conditional acquisition rates

This is an `Acquisition`, not a complete item. Keep solo and four-player rates separate. The capture lists the percentages but does not explicitly establish their probabilistic denominator, so it remains unknown. An eventual evidence decision can establish per-kill interpretation without changing the schema.

```json
{
  "id": "crawmerax-omega",
  "method": "drop",
  "source": {
    "id": "crawmerax",
    "name": "Crawmerax",
    "kind": "raid_boss",
    "locations": [
      {
        "id": "crawmerax-lair",
        "name": "Crawmerax's Lair"
      }
    ]
  },
  "contentPack": "general_knoxx",
  "cases": [
    {
      "id": "solo",
      "when": {
        "kind": "players",
        "count": 1
      },
      "chance": {
        "value": {
          "kind": "fixed",
          "value": 0.157
        },
        "unit": "percent",
        "per": "unknown"
      }
    },
    {
      "id": "four-players",
      "when": {
        "kind": "players",
        "count": 4
      },
      "chance": {
        "value": {
          "kind": "fixed",
          "value": 0.178
        },
        "unit": "percent",
        "per": "unknown"
      }
    }
  ]
}
```

### H. Focused fragment: a scoped interaction, not a blanket class-mod ban

This is an `Interaction`. The Wiki makes a broader class-mod claim for Hive Mind; Lootlemon names a narrower Bombardier regeneration bug. Preserve the narrow supported statement and the alternative privately, rather than declaring all class-mod effects disabled.

```json
{
  "id": "hive-mind-launcher-regen",
  "kind": "bug",
  "with": [
    {
      "id": "class-mods-brick-bombardier",
      "name": "Bombardier"
    }
  ],
  "description": "Holding Hive Mind prevents Bombardier's launcher ammunition regeneration; this does not establish that every regeneration effect is disabled."
}
```

## TypeScript types

The common base keeps every item consistent. The `kind` discriminator selects its
specific block. These types are intentionally a draft; they are not Zod and are
not imported by the app. All JSON examples above are checked against these types.

`stat` keys belong to an extensible registry. A `custom:` key needs a useful
`label` and unit before the UI can display it; new legitimate facts should not
be discarded simply because they do not match the first registry list.

```ts
/** DESIGN ONLY. Not the app's current schema or a new runtime dependency. */
type Id = string;
type Character = "brick" | "lilith" | "mordecai" | "roland";
type Edition = "original" | "enhanced";
type ItemKind =
  | "weapon"
  | "shield"
  | "grenade_mod"
  | "class_mod"
  | "artifact"
  | "upgrade"
  | "other";
type ContentPack =
  | "base_game"
  | "zombie_island"
  | "underdome"
  | "general_knoxx"
  | "robot_revolution";
type Element =
  "non_elemental" | "incendiary" | "shock" | "corrosive" | "explosive";
type Rarity =
  "common" | "uncommon" | "rare" | "epic" | "legendary" | "pearlescent";
type WeaponType =
  | "combat_rifle"
  | "machine_gun"
  | "repeater_pistol"
  | "machine_pistol"
  | "revolver"
  | "smg"
  | "shotgun"
  | "sniper_rifle"
  | "rocket_launcher"
  | "grenade_launcher"
  | "eridian_weapon";
type AmmoPool =
  | "combat_rifle"
  | "pistol"
  | "revolver"
  | "smg"
  | "shotgun"
  | "sniper"
  | "launcher"
  | "grenade";
type KnownSet<T> = { values: T[]; coverage: "complete" | "partial" };
type Traceable = { referenceIds?: Id[] };
type NamedRef = { id: Id; name: string };

type Unit =
  | "damage"
  | "damage_per_second"
  | "percent"
  | "percentage_points"
  | "ratio"
  | "multiplier"
  | "rating"
  | "count"
  | "rounds"
  | "rounds_per_second"
  | "projectiles"
  | "seconds"
  | "milliseconds"
  | "meters"
  | "feet"
  | "unreal_units"
  | "health"
  | "health_per_second"
  | "shield_points"
  | "shield_points_per_second"
  | "skill_points"
  | "effect_levels"
  | "tech_levels"
  | "slots"
  | "money"
  | "experience"
  | "unknown"
  | `custom:${string}`;
type Variable =
  | "item_level"
  | "character_level"
  | "skill_rank"
  | "effect_rank"
  | "players"
  | "max_health"
  | "shield_capacity";
type Expression =
  | { op: "constant"; value: number }
  | { op: "variable"; name: Variable }
  | { op: "add" | "multiply" | "min" | "max"; args: Expression[] }
  | { op: "subtract" | "divide"; left: Expression; right: Expression };
type NumericValue =
  | { kind: "fixed"; value: number; approximate?: boolean }
  | { kind: "range"; min: number; max: number; approximate?: boolean }
  | { kind: "choices"; values: number[] }
  | { kind: "bound"; side: "minimum" | "maximum"; value: number }
  | { kind: "fraction"; numerator: number; denominator: number }
  | {
      kind: "formula";
      expression: Expression;
      inputs?: Partial<Record<Variable, { min?: number; max?: number }>>;
    }
  | { kind: "unknown" };
type Measurement = Traceable & { value: NumericValue; unit: Unit };
type StatKey =
  | "damage"
  | "damage_over_time"
  | "splash_damage"
  | "splash_radius"
  | "accuracy"
  | "min_inaccuracy"
  | "max_inaccuracy"
  | "spread"
  | "accuracy_recovery"
  | "fire_rate"
  | "fire_interval"
  | "reload_speed"
  | "reload_duration"
  | "magazine_capacity"
  | "ammo_regeneration"
  | "ammo_cost"
  | "ammo_capacity"
  | "projectile_count"
  | "burst_count"
  | "projectile_speed"
  | "zoom"
  | "recoil"
  | "recoil_recovery"
  | "equip_speed"
  | "equip_duration"
  | "swap_speed"
  | "move_speed"
  | "critical_hit_damage"
  | "melee_damage"
  | "melee_speed"
  | "knockback"
  | "element_level"
  | "ignite_chance"
  | "elemental_chance"
  | "tech_level"
  | "tech_cost"
  | "tech_capacity"
  | "tech_regeneration"
  | "shield_capacity"
  | "shield_recharge_rate"
  | "shield_recharge_delay"
  | "damage_received"
  | "max_health"
  | "health_regeneration"
  | "cooldown_rate"
  | "cooldown_duration"
  | "skill_points"
  | "effect_rank"
  | "fuse_time"
  | "jump_height"
  | "child_count"
  | "inventory_slots"
  | "equip_slots"
  | "experience_gain"
  | "loot_quality"
  | "rarity_score"
  | "cost_multiplier"
  | `custom:${string}`;
type ValueContext = {
  surface?: "card" | "gameplay" | "technical";
  selection?:
    | "fixed_rule"
    | "reported_range"
    | "example_roll"
    | "maximum_roll"
    | "minimum_roll"
    | "calculated";
  atItemLevel?: number;
  atCharacterLevel?: number;
  atEffectRank?: number;
  when?: Condition;
  notes?: string; // Original AI prose; not a container for unparsed stat tables.
};
type ItemStat = Measurement & {
  id: Id;
  stat: StatKey;
  label?: string;
  context?: ValueContext;
};
type Target = {
  recipient: "owner" | "team" | "hit_target" | "nearby_enemies";
  includesOwner?: boolean; // Explicit for team effects.
  weaponTypes?: WeaponType[];
  ammoPools?: AmmoPool[];
  manufacturers?: string[];
  damageElements?: Element[];
  skill?: NamedRef;
};
type Condition =
  | { kind: "all" | "any"; conditions: Condition[] }
  | { kind: "not"; condition: Condition }
  | { kind: "edition"; values: Edition[] }
  | { kind: "content_pack"; values: ContentPack[] }
  | { kind: "playthrough"; values: ("first" | "second" | "post_second")[] }
  | { kind: "players"; count: number }
  | { kind: "mode"; value: "single_player" | "multiplayer" }
  | { kind: "character"; values: Character[] }
  | {
      kind: "level";
      subject: "item" | "character" | "enemy";
      min?: number;
      max?: number;
    }
  | {
      kind: "mission";
      mission: NamedRef;
      state: "available" | "accepted" | "completed" | "turned_in";
    }
  | { kind: "objective"; name: string; quantity?: number }
  | { kind: "part_selected"; groupId: Id; optionId: Id }
  | { kind: "variant_selected"; variantId: Id }
  | {
      kind: "skill_rank";
      skill: NamedRef;
      minimumInvested?: number;
      minimumEffective?: number;
    }
  | {
      kind: "state";
      value:
        | "aiming"
        | "shield_full"
        | "shield_depleted"
        | "shield_recharging"
        | "action_skill_active"
        | "target_corroding";
    }
  | {
      kind: "health_type";
      value: "flesh" | "shield" | "armor";
      shielded?: boolean;
    }
  | { kind: "text"; text: string }; // Original AI wording, display-only, not executable.
type Modifier = Measurement & {
  id: Id;
  stat: StatKey;
  label?: string;
  operation: "add" | "add_percent" | "multiply" | "set" | "reported";
  stage?: "pre_add" | "post_add" | "unknown";
  stacking?: "additive" | "multiplicative" | "unknown";
  basis?:
    | "base_stat"
    | "current_stat"
    | "weapon_damage"
    | "max_health"
    | "shield_capacity"
    | "unknown";
  target?: Target;
  when?: Condition;
  context?: ValueContext;
};
type Mechanic = Traceable & {
  id: Id;
  name: string;
  description: string;
  trigger?:
    | "on_shot"
    | "on_hit"
    | "on_kill"
    | "on_throw"
    | "on_detonation"
    | "on_shield_break"
    | "on_use"
    | "passive"
    | "other";
  when?: Condition;
  parameters?: ItemStat[];
  modifiers?: Modifier[];
};
type PartSlot =
  | "body"
  | "barrel"
  | "magazine"
  | "stock"
  | "sight"
  | "grip"
  | "action"
  | "accessory"
  | "material"
  | "left_side"
  | "right_side"
  | "prefix"
  | "title"
  | "other";
type PartOption = Traceable & {
  id: Id;
  name: string;
  sourceNames?: string[];
  image?: string | null;
  presence?: "part" | "none";
  role?: "defining" | "required" | "possible";
  manufacturers?: KnownSet<string>;
  modifiers?: Modifier[];
  mechanics?: Mechanic[];
  weights?: (Traceable & { value: NumericValue; when?: Condition })[];
  notes?: string[];
  when?: Condition;
};
type PartRule = Traceable & {
  id: Id;
  when: Condition;
  requires?: Condition;
  forbids?: Condition;
  description?: string;
};
type PartGroup = Traceable & {
  id: Id;
  slot: PartSlot;
  name: string;
  coverage: "complete" | "partial" | "unknown";
  selection?: { min: number; max: number }; // Omit if the selection count is unknown.
  options: PartOption[];
  rules?: PartRule[];
};
type Variant = Traceable & {
  id: Id;
  name: string;
  kind: "hybrid" | "material" | "elemental" | "firing_mode" | "other";
  description?: string;
  when?: Condition;
  selectedParts?: { groupId: Id; optionId: Id }[];
  modifiers?: Modifier[];
  mechanics?: Mechanic[];
  rarities?: KnownSet<Rarity>;
  elements?: KnownSet<Element>;
  relatedItems?: NamedRef[];
  comparisons?: {
    baseline: NamedRef;
    description?: string;
    differences?: Modifier[];
  }[];
};
type Probability = {
  value: NumericValue; // Fixed/rounded percentages or a rational count; see the rules below.
  unit: "percent" | "ratio";
  per:
    | "kill"
    | "chest_open"
    | "mission_completion"
    | "new_character"
    | "loot_roll"
    | "unknown";
};
type Cost = Traceable & {
  currency: "money";
  value: NumericValue;
  basis?: "fixed" | "reported_table" | "example" | "calculated";
  when?: Condition;
};
type Reward =
  | {
      kind: "item";
      item?: NamedRef;
      quantity?: NumericValue;
      effectRank?: NumericValue;
      elementSelection?: "fixed" | "random";
      element?: Element;
      classSelection?: "recipient" | "random" | "fixed";
      character?: Character;
    }
  | { kind: "money" | "experience"; value: NumericValue };
type AcquisitionCase = Traceable & {
  id: Id;
  when?: Condition;
  chance?: Probability;
  cost?: Cost;
  rewards?: Reward[];
  status?: "current" | "historical" | "expired";
  notes?: string;
};
type Acquisition = Traceable & {
  id: Id;
  method:
    "drop" | "mission_reward" | "purchase" | "starting_gear" | "code" | "other";
  source: NamedRef & {
    kind:
      | "enemy"
      | "raid_boss"
      | "chest"
      | "loot_pool"
      | "mission"
      | "vendor"
      | "character_creation"
      | "code"
      | "other";
    locations?: NamedRef[];
  };
  contentPack?: ContentPack; // Where this acquisition occurs, not where the item originated.
  cases: AcquisitionCase[];
  notes?: string;
};
type Interaction = Traceable & {
  id: Id;
  kind: "synergy" | "bug" | "limitation" | "behavior";
  with?: NamedRef[];
  when?: Condition;
  description: string;
};
type Narrative = {
  summary: string;
  overview: string[];
  gameplay?: { heading: string; paragraphs: string[] }[];
  notes?: string[];
  trivia?: string[];
};
type Reference =
  | { id: Id; kind: "web"; title: string; url: string }
  | { id: Id; kind: "manual"; title: string }
  | { id: Id; kind: "game_data"; title: string };
type DataTable = Traceable & {
  id: Id;
  title: string;
  coverage?: "complete" | "partial";
  columns: { id: Id; label: string; stat?: StatKey; unit?: Unit }[];
  rows: Record<Id, string | number | boolean | null | NumericValue>[];
};
type SkillDefinition = Traceable & {
  id: Id;
  name: string;
  character: Character;
  baseMaxRank?: number;
  boostedMaxRank?: number;
  description?: string;
  scaling?: DataTable[];
};
type SharedMechanic = Mechanic & {
  appliesTo?: {
    kinds?: ItemKind[];
    itemIds?: Id[];
    weaponTypes?: WeaponType[];
    characters?: Character[];
    elements?: Element[];
    skills?: Id[];
  };
};
type BaseItem = {
  schemaVersion: "proposal-1";
  compilerVersion?: string;
  revision: number;
  id: Id;
  slug: string;
  name: string;
  aliases?: string[];
  legacySlugs?: string[];
  origin: { contentPack: ContentPack | null; introducedEdition?: Edition };
  availability?: {
    status?: "obtainable" | "historical" | "cut" | "unknown";
    editions?: Edition[];
    when?: Condition;
  };
  image?: string | null;
  tags?: string[];
  manufacturers?: KnownSet<string>;
  rarities?: KnownSet<Rarity>;
  elements?: KnownSet<Element>;
  redText?: string;
  requirements?: Condition;
  prose: Narrative;
  stats?: ItemStat[];
  modifiers?: Modifier[];
  mechanics?: Mechanic[];
  partGroups?: PartGroup[];
  variants?: Variant[];
  acquisition?: Acquisition[];
  interactions?: Interaction[];
  knowledge?: {
    skills?: SkillDefinition[];
    sharedMechanics?: SharedMechanic[];
  };
  tables?: DataTable[];
  references?: Reference[];
  economy?: { buy?: Cost[]; sell?: Cost[]; tradeable?: boolean };
  naming?: {
    prefixes?: KnownSet<string>;
    rules?: (Traceable & {
      id: Id;
      kind: "prefix" | "title";
      name: string;
      when?: Condition;
      modifiers?: Modifier[];
      mechanics?: Mechanic[];
    })[];
  };
  gallery?: {
    id: Id;
    path: string;
    role: "card" | "world" | "inventory" | "other";
    caption?: string;
  }[];
};
type WeaponItem = BaseItem & {
  kind: "weapon";
  weapon: {
    type: WeaponType;
    ammoPool?: AmmoPool;
    firingModes?: {
      id: Id;
      mode: "single" | "semi_auto" | "full_auto" | "burst" | "other";
      shotsPerBurst?: Measurement;
      projectilesPerShot?: Measurement;
      ammoPerShot?: Measurement;
      when?: Condition;
    }[];
  };
};
type ShieldItem = BaseItem & {
  kind: "shield";
  shield: {
    resistances?: (Traceable & {
      element: Element;
      meaning: "damage_reduction" | "damage_received" | "immunity";
      value?: Measurement;
      when?: Condition;
    })[];
  };
};
type GrenadeModItem = BaseItem & {
  kind: "grenade_mod";
  grenadeMod: {
    behavior:
      | "bouncing_bettie"
      | "contact"
      | "longbow"
      | "mirv"
      | "proximity"
      | "rain"
      | "rubberized"
      | "sticky"
      | "transfusion"
      | "other";
    activation?: "fuse" | "contact" | "proximity" | "other";
    fuse?: Measurement;
    childCount?: Measurement;
    jumpHeight?: Measurement;
    spreadRadius?: Measurement;
    initialBlastDealsDamage?: boolean;
  };
};
type ClassModItem = BaseItem & {
  kind: "class_mod";
  classMod: {
    character: Character;
    skillBonuses?: (Traceable & {
      skill: NamedRef;
      points: NumericValue;
      when?: Condition;
    })[];
    maxBoostedSkills?: number;
    bonusPatterns?: {
      points: number[];
      assignment: "any_permutation" | "ordered";
      skillIds?: Id[];
      when?: Condition;
    }[];
    loyaltyManufacturers?: string[];
  };
};
type ArtifactItem = BaseItem & {
  kind: "artifact";
  artifact: {
    character: Character;
    actionSkill: NamedRef;
    use: "consumed_permanent_unlock";
    maximumEffectRank?: number;
    higherRankReplacesLower?: boolean;
    exclusiveGroup?: string;
    canDisable?: boolean;
    rankRequirements?: (Traceable & {
      rank: number;
      when: Condition;
      basis: "rule" | "example";
    })[];
    shape?: string;
  };
};
type UpgradeTier = Traceable & {
  id: Id;
  tier: number;
  label?: string;
  capacity?: NumericValue;
  increase?: NumericValue;
  grants?: Modifier[];
  cost?: Cost;
  when?: Condition;
  contentPack?: ContentPack;
};
type UpgradeItem = BaseItem & {
  kind: "upgrade";
  upgrade: {
    type:
      | "ammo_capacity"
      | "backpack_capacity"
      | "equip_slots"
      | "skill_point"
      | "other";
    use?:
      | "permanent_on_purchase"
      | "consumed_permanent_upgrade"
      | "automatic_reward";
    tracks: (Traceable & {
      id: Id;
      target: AmmoPool | "backpack" | "equip_slots" | "skill_points";
      unit: Unit;
      initial?: NumericValue;
      coverage: "complete" | "partial";
      tiers: UpgradeTier[];
    })[];
    purchaseOrder?: "sequential" | "can_skip_tiers" | "unknown";
  };
};
type OtherItem = BaseItem & {
  kind: "other";
  other: { subtype: string }; // Use the common typed stats/modifiers/mechanics/tables, not an untyped dump.
};
export type CatalogueItem =
  | WeaponItem
  | ShieldItem
  | GrenadeModItem
  | ClassModItem
  | ArtifactItem
  | UpgradeItem
  | OtherItem;

/** Optional private workshop sidecar. Ordinary website exports omit this block. */
type ResearchSource = {
  id: Id;
  referenceId: Id;
  captureId: Id;
  contentHash?: string;
  kind: "page" | "manual" | "game_record";
  captureMode?: "full_page" | "selection" | "manual_text" | "game_extract";
  capturedAt?: string;
  characters?: number;
  bytes?: number;
  fromScope?: { id: Id; path: string[] };
  selectedForBuild?: "auto" | "always" | "never";
  capturedSections?: string[];
};
type Assertion = {
  id: Id;
  subject: NamedRef;
  role:
    | "item_property"
    | "component_property"
    | "shared_rule"
    | "skill_baseline"
    | "example"
    | "comparison";
  sourceIds: Id[];
  locator?: {
    section?: string;
    table?: number;
    row?: number;
    quote?: string;
    recordPath?: string;
  };
  outputPaths?: string[];
  scope?: {
    kinds?: ItemKind[];
    characters?: Character[];
    elements?: Element[];
    itemIds?: Id[];
    editions?: Edition[];
    games?: (
      | "borderlands"
      | "borderlands_2"
      | "pre_sequel"
      | "borderlands_3"
      | "borderlands_4"
      | "wonderlands"
      | "unknown"
    )[];
  };
  status: "accepted" | "alternative" | "omitted" | "unresolved";
  reason?: string;
  originalValue?: unknown; // Private capture only, never silently treated as normalized gameplay data.
};
type ResearchAudit = {
  sources: ResearchSource[];
  assertions: Assertion[];
  decisions?: {
    field: string;
    selectedAssertion?: Id;
    alternatives: Id[];
    reason: string;
  }[];
  warnings?: string[];
  nativeModifiers?: {
    assertionId: Id;
    attributePath: string;
    modifierType: number | string;
    rawValue: unknown;
  }[];
};
export type CatalogueDocument = CatalogueItem & { research?: ResearchAudit };
```

## How the captured items exercise this design

| Captured item              | Schema concern it exposes                                                                                                          |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| HellFire                   | A part-defined effect, separate magazine rows, reported card ranges and guaranteed extra ignition                                  |
| Bone Shredder              | Fixed versus optional parts; two projectiles are not automatically a two-shot burst; hybrid body; a material-generation bug        |
| Ogre / Ajax's Spear        | Hybrid part combinations, title changes and comparison bonuses with different baselines                                            |
| Havoc                      | A generic title with qualifying requirements, not a unique weapon whose name alone grants all related effects                      |
| Repeater                   | Multi-manufacturer generic family; example infobox numbers are not fixed family stats; class-specific magazine/action choices      |
| Hive Mind                  | Enhanced-specific availability, three-shot burst versus ammo cost, several acquisition methods and a narrowly scoped class-mod bug |
| Volcano                    | Special accessory, large incendiary effect, visibility drawbacks and a shared sniper critical-damage rule                          |
| Whitting's Elephant Gun    | Explicit lack of a scope, fixed barrel/magazine/stock, optional accessory, discrete accuracy choices and conditional drops         |
| Grounded Shield            | Shock resistance is not outgoing Shock damage; received-damage percentage is not the same as damage-reduction percentage           |
| Omega                      | Defining shield body, minimum recharge delay, resistance, and source-specific player-count probabilities                           |
| Wee Wee's Super Booster    | Level-based regeneration, multiple rarities, fixed body, known drop and edition-dependent farming behavior                         |
| Bouncing Bettie            | Trigger/fuse timing, child count, damage-free launch and conflicting numerical descriptions                                        |
| Support Gunner / Stockpile | Owner class versus team beneficiaries, per-ammo rates, skill ranks versus bonus points, maximum rolls and exclusive materials      |
| Corrosive Artifact         | Consumable permanent unlock, effect rank versus item/character level, scoped rewards and shared elemental context                  |
| Ammo Storage Upgrade       | Multiple ammunition tracks, initial capacity versus tier capacity, optional prices and the ability to skip tiers                   |

## Rules for later implementation

This is not a proposal to bring back perfection-based build blocking.

1. **Preserve evidence.** Never rewrite the captured originals to fit the new schema.
   Keep unfamiliar useful facts in private assertions or an appropriate typed table
   until their mapping is understood.
2. **Prefer supported data; tolerate ordinary uncertainty.** Use a best supported
   value where reasonable, keep alternatives privately, or omit optional specifics.
   Ambiguous names, minor numerical disagreements and incomplete optional fields
   should remain non-blocking notes.
3. **Keep genuine structural safeguards.** Check document shape, finite numbers,
   sensible bounds, probability units, unique IDs and local references. Avoid the
   wrong item/game, impossible part links and invented native operations. Missing
   optional detail must not cause repeated AI rewrites.
4. **Do not call source conflicts roll ranges.** A disagreement between 11 and 12
   child grenades is different from a grenade genuinely rolling 11–12 children.
5. **Keep source priority scoped.** An exact defining game relationship is useful
   for compatibility; a website can be better for a documented player-facing
   behavior. Neither “all game data wins” nor “all Lootlemon fields win” is a safe
   universal rule. Decisions need the same subject, edition, conditions and units.
6. **Do not treat every possible part as legal for every family.** Shared catalogs
   supply candidate definitions; actual family/grade/manufacturer constraints
   determine the possible selections. Unknown constraints remain unknown.
7. **Do not evaluate `reported` operations or text conditions in a calculator.**
   Their usefulness for display does not establish exact engine math. Part weights
   also remain weights until a complete, conditioned selection pool is known.
8. **Separate shared applicability from ownership.** A related skill's values are
   not COM bonuses; a general corrosion rule is not an item card stat; a
   manufacturer named in a shield paragraph is not the artifact's maker.
9. **Respect user controls.** Manual names/types and manual evidence remain
   authoritative within their established scope. Never-include content stays out
   of normal model inputs. Choosing a schema must not silently change inheritance
   modes or trigger builds.
10. **All explanatory sentences are original AI wording.** That includes source
    notes, part notes, mechanics, interactions, skill descriptions and trivia.
    The UI formats numbers and canonical labels; proper names and exact red text
    are preserved. Raw source quotations belong in private research.
11. **Normalise for storage, close references for export.** Reuse stable part,
    skill and source IDs internally. A standalone item export embeds the selected
    part definitions and detailed knowledge it actually needs. Named links to
    other items can remain links with a display name; a mandatory local part
    reference must resolve within the document.
12. **Do not invent missing assets.** Primary and part images are optional local
    paths. No filename is fabricated merely to fill a field.

A later Zod implementation can enforce shapes and cross-reference constraints.
It should not require every possible field, perfect prose, a resolved unit for
every historical observation, or a complete game simulation before saving an item.

## Suggested reading views

The same document can serve three depths without losing data:

- **Overview:** image, summary, core stats, what makes the item useful and where
  to obtain it. Show conditions such as max-roll bonuses and edition restrictions.
- **Parts & numbers:** individual part options and modifier tables, skill-point
  patterns, rank tables, formulas and conditional rates. A row is one option;
  do not combine Magazine 2 and Magazine 3 into a single sentence.
- **Research & technical:** provenance, native attribute coefficients, alternative
  claims and selected shared knowledge. Keep this available without forcing it
  into normal player prose or every AI writing request.

These are possible UI uses of the schema, not UI changes implemented by this file.

## Decisions to review before implementation

My starting preferences are included so we have concrete choices to discuss:

1. **Base plus typed blocks:** recommend the discriminated union shown here,
   rather than a giant object in which any type can contain any other type's fields.
2. **Structured modifiers:** recommend `stat / operation / value / unit`, with
   `reported` for useful modifiers whose exact native mathematics is unresolved.
   Decide whether the default UI hides those mathematical qualifiers or shows a
   small technical indicator.
3. **Shared export data:** recommend self-contained item exports with only relevant
   embedded definitions. A future database-wide bundle may reference shared IDs
   instead; that should be an explicit packaging choice, not broken standalone JSON.
4. **Numeric detail:** recommend retaining it all when relevant, with formulas and
   structured tables available on demand. Keep card ranges, component coefficients
   and illustrative rolls visibly separate.
5. **Stat names:** the registry is a first pass. Raw `WeaponReloadSpeed` versus
   public reload speed/duration, accuracy minima/maxima and tech/displayed elemental
   levels need documented mappings before any exact calculator is attempted.
6. **Evidence citations:** recommend compact source-level references in the public
   item and optional assertion-level detail in the private audit sidecar. We can
   strip all audit data from player exports without losing it in the workshop.
7. **Examples as style fixtures:** approve/revise these shapes and prose before
   turning them into runtime schemas or prompts. Once approved, build one complete
   reference entry per kind and a few exceptions such as hybrids and edition-only
   gear. The examples here intentionally do not claim exhaustive part/source lists.

Still worth adding to a later test set: a dedicated nova shield, another grenade
behavior, a loyalty class mod and an Eridian weapon. The general pages/raw records
help reserve space for these, but this capture set does not establish every detail
of every subtype. We do not need to capture the entire catalogue before agreeing
on this first contract.

## Source inventory

All rows below refer to the local captured snapshot reviewed for this proposal.
The links identify the original sites; the proposal was based on saved content,
not a new fetch. Character counts describe stored plain text, not an AI payload
or a guarantee of complete website data. General-page navigation, comparisons and
later-game sections were not promoted into item properties merely because they
were captured.

| Item / owner            | Saved page                                                                                               | Site      | Characters |
| ----------------------- | -------------------------------------------------------------------------------------------------------- | --------- | ---------: |
| Corrosive Artifact      | [Artifact](https://borderlands.fandom.com/wiki/Artifact)                                                 | Wiki      |     11,144 |
| Corrosive Artifact      | [Corrosive](https://borderlands.fandom.com/wiki/Corrosive)                                               | Wiki      |      3,637 |
| Corrosive Artifact      | [Corrosive Crystal Harvest](https://borderlands.fandom.com/wiki/Corrosive_Crystal_Harvest)               | Wiki      |      8,394 |
| Support Gunner          | [Class Mod (Borderlands)](<https://borderlands.fandom.com/wiki/Class_Mod_(Borderlands)>)                 | Wiki      |     29,765 |
| Support Gunner          | [Borderlands 1Support Gunner](https://www.lootlemon.com/class-mod/support-gunner-roland-bl1)             | Lootlemon |      3,363 |
| Support Gunner          | [Roland SkillStockpile](https://www.lootlemon.com/skill/stockpile-roland)                                | Lootlemon |      2,941 |
| Bouncing Bettie         | [Bouncing Bettie Grenade](https://borderlands.fandom.com/wiki/Bouncing_Bettie_Grenade)                   | Wiki      |      3,368 |
| Bouncing Bettie         | [Grenade Mod](https://borderlands.fandom.com/wiki/Grenade_Mod)                                           | Wiki      |     10,999 |
| Bouncing Bettie         | [Borderlands 1Bouncing Bettie](https://www.lootlemon.com/grenade-mod/bouncing-bettie-bl1)                | Lootlemon |      2,546 |
| Ammo Storage Upgrade    | [Storage Deck Upgrade](https://borderlands.fandom.com/wiki/Storage_Deck_Upgrade)                         | Wiki      |     11,544 |
| Ammo Storage Upgrade    | [Vending machine](https://borderlands.fandom.com/wiki/Vending_machine)                                   | Wiki      |     15,480 |
| Grounded Shield         | [Elemental Shields in Borderlands](https://borderlands.fandom.com/wiki/Elemental_Shields_in_Borderlands) | Wiki      |        653 |
| Grounded Shield         | [Shields in Borderlands](https://borderlands.fandom.com/wiki/Shields/Borderlands)                        | Wiki      |     11,455 |
| Omega                   | [Omega](https://borderlands.fandom.com/wiki/Omega)                                                       | Wiki      |      1,692 |
| Omega                   | [Borderlands 1Omega](https://www.lootlemon.com/shield/omega-bl1)                                         | Lootlemon |      2,812 |
| Havoc                   | [Weapons by title (Borderlands)](<https://borderlands.fandom.com/wiki/Weapons_by_title_(Borderlands)>)   | Wiki      |      5,092 |
| Ajax's Spear            | [Borderlands 1Ajax's Spear](https://www.lootlemon.com/weapon/ajaxs-spear-bl1)                            | Lootlemon |      4,200 |
| Ajax's Spear            | [Borderlands 1Ajax](https://www.lootlemon.com/loot-source/ajax)                                          | Lootlemon |        420 |
| Ogre                    | [Ogre (Borderlands)](<https://borderlands.fandom.com/wiki/Ogre_(Borderlands)>)                           | Wiki      |      3,163 |
| Ogre                    | [Borderlands 1Ogre](https://www.lootlemon.com/weapon/ogre-bl1)                                           | Lootlemon |      4,365 |
| Wee Wee's Super Booster | [Wee Wee's Super Booster](https://borderlands.fandom.com/wiki/Wee_Wee%27s_Super_Booster)                 | Wiki      |      2,855 |
| Wee Wee's Super Booster | [Borderlands 1Wee Wee's Super Booster](https://www.lootlemon.com/shield/wee-wees-super-booster-bl1)      | Lootlemon |      4,110 |
| Wee Wee's Super Booster | [Borderlands 1King Wee Wee](https://www.lootlemon.com/loot-source/king-wee-wee)                          | Lootlemon |        412 |
| Repeater                | [Repeater (Title)](<https://borderlands.fandom.com/wiki/Repeater_(Title)>)                               | Wiki      |      1,457 |
| Repeater                | [Repeater Pistol/parts](https://borderlands.fandom.com/wiki/Repeater_Pistol/parts)                       | Wiki      |     14,690 |
| Hive Mind               | [Hive Mind](https://borderlands.fandom.com/wiki/Hive_Mind)                                               | Wiki      |      2,147 |
| Hive Mind               | [Rocket Launcher/parts](https://borderlands.fandom.com/wiki/Rocket_Launcher/parts)                       | Wiki      |      9,141 |
| Hive Mind               | [Borderlands 1Hive Mind](https://www.lootlemon.com/weapon/hive-mind-bl1)                                 | Lootlemon |      1,731 |
| Hive Mind               | [Borderlands 1Bombardier](https://www.lootlemon.com/class-mod/bombardier-brick-bl1)                      | Lootlemon |      3,260 |
| Bone Shredder           | [Borderlands 1Bone Shredder](https://www.lootlemon.com/weapon/bone-shredder-bl1)                         | Lootlemon |      3,925 |
| Bone Shredder           | [Bone Shredder (Borderlands)](<https://borderlands.fandom.com/wiki/Bone_Shredder_(Borderlands)>)         | Wiki      |      2,906 |
| HellFire                | [Hellfire (Borderlands)](<https://borderlands.fandom.com/wiki/Hellfire_(Borderlands)>)                   | Wiki      |      2,298 |
| HellFire                | [Borderlands 1Hellfire](https://www.lootlemon.com/weapon/hellfire-bl1)                                   | Lootlemon |      4,438 |
| Volcano                 | [Volcano (Borderlands)](<https://borderlands.fandom.com/wiki/Volcano_(Borderlands)>)                     | Wiki      |      3,003 |
| Volcano                 | [Borderlands 1Volcano](https://www.lootlemon.com/weapon/volcano-bl1)                                     | Lootlemon |      4,270 |
| Whitting's Elephant Gun | [Borderlands 1Whitting's Elephant Gun](https://www.lootlemon.com/weapon/whittings-elephant-gun-bl1)      | Lootlemon |      3,505 |
| Whitting's Elephant Gun | [Whitting's Elephant Gun](https://borderlands.fandom.com/wiki/Whitting's_Elephant_Gun)                   | Wiki      |      3,033 |
