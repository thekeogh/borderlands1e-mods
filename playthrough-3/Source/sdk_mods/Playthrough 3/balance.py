"""The release's enemy and grenade presets; shared by the menu and gameplay."""

BASE_LEVEL = 69
MIN_ENEMY_LEVEL = 71
NAMED_LEVEL = 71
DEFAULT_MAX = 5
WEIGHTS = {3: (20, 80), 4: (20, 50, 30), 5: (20, 48, 30, 2)}
GRENADE_DAMAGE = {3: 700, 4: 775, 5: 800}
MIN_MAX, MAX_MAX = min(WEIGHTS), max(WEIGHTS)


def max_setting(value):
    return max(MIN_MAX, min(MAX_MAX, int(value)))


def table_rows():
    for value, weights in WEIGHTS.items():
        chances = [f"{weight}%" for weight in weights] + ["—"] * (4 - len(weights))
        yield [str(value), f"{MIN_ENEMY_LEVEL}–{BASE_LEVEL + value}", *chances, str(NAMED_LEVEL), str(GRENADE_DAMAGE[value])]


TABLE_HEADER = ["Max", "Enemy levels", "71", "72", "73", "74", "Named/boss", "Grenade"]
TABLE = " | ".join(TABLE_HEADER) + "\n" + "\n".join(" | ".join(row) for row in table_rows())
DESCRIPTION = (
    "A resettable third playthrough for your level-69 character, including DLCs.\n"
    f"Level-1 cash prices and rewards. Named enemies/bosses stay at {NAMED_LEVEL}.\n\n"
    + TABLE
    + "\n\nEnemy Max Level: 3–5, default 5. Maximum is 69 + the setting; minimum is 71."
      " Each supported ordinary spawn rolls independently. Changes affect new spawns/restores."
      " Grenade numbers are fixed base card damage for standard grenade mods in PT3;"
      " bonuses and multiple hits can change actual damage received."
      " PT1/PT2 retain their normal balance.\n\n"
      "Install the SDK mod and gd_GameStages_PT3.upk, then select Playthrough 3."
      " Press R on Playthrough 3 in the difficulty menu to reset it."
)
