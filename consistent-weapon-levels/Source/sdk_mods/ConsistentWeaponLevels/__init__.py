"""Correct only the level text after the game has built a weapon card."""

from collections import deque
import re

from mods_base import ButtonOption, SETTINGS_DIR, build_mod, get_pc, hook
from unrealsdk import find_object, logging
from unrealsdk.hooks import Type

from .levels import level_details, ordinary_level

CARD_FUNCTIONS = (
    "WillowGame.StatusMenuExGFxMovie:UpdateCardPanel",
    "WillowGame.StatusMenuExGFxMovie:UpdateCardPanelWithCurrentCell",
    "WillowGame.StatusMenuExGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    "WillowGame.StatusMenuExGFxMovie:extSetMouseOverCell",
    "WillowGame.StatusMenuExGFxMovie:extCard2Visible",
    "WillowGame.StatusMenuExGFxMovie:extCompare",
    "WillowGame.VendingMachineGFxMovie:UpdateCardPanel",
    "WillowGame.VendingMachineGFxMovie:UpdateCardPanelWithItemOfTheDay",
    "WillowGame.VendingMachineGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    "WillowGame.VendingMachineGFxMovie:extSetMouseOverCell",
    "WillowGame.VendingMachineGFxMovie:extCard2Visible",
    "WillowGame.VendingMachineGFxMovie:extCompare",
    "WillowGame.BankGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    "WillowGame.BankGFxMovie:extCard2Visible",
    "WillowGame.BankGFxMovie:StartComparing",
    "WillowGame.ItemPickupGFxMovie:UpdateCompareAgainstThing",
    "WillowGame.WillowHUDGFxMovie:extEquippedCardOpened",
    "WillowGame.QuestAcceptGFxMovie:extSetUpRewardsPage",
)
CARD_PREFIXES = {
    "StatusMenuExGFxMovie": ("topLevel_mc.card1", "topLevel_mc.card2"),
    "VendingMachineGFxMovie": ("topLevel_mc.card1", "topLevel_mc.card2"),
    "BankGFxMovie": ("currentPage.card1", "currentPage.card2"),
    "ItemPickupGFxMovie": ("inventory.card1",),
    "WillowHUDGFxMovie": ("p1.outerequip.equipcard",),
    "QuestAcceptGFxMovie": ("reward.card1",),
}

_enabled = False
_stats = {key: 0 for key in ("card_calls", "weapon_cards", "text_writes",
                           "unchanged", "unsupported", "missing_text", "write_mismatch", "errors")}
_errors = []
_recent_cards = deque(maxlen=40)
# At most one comparison source per menu class. Keep paths, never live actors.
_comparisons = {}


def report_error(exc):
    _stats["errors"] += 1
    message = f"{type(exc).__name__}: {exc}"
    if message not in _errors and len(_errors) < 10:
        _errors.append(message)
        logging.warning(f"[Consistent Weapon Levels] {message}")


def highlighted_item(movie):
    getter = getattr(movie, "GetCurrentHighlightedObject", None)
    if getter is not None:
        return getter()
    if getattr(movie, "bOnItemOfTheDay", False):
        return movie.ItemOfTheDayData.Item
    text_list = getattr(movie, "ActiveTextList", None)
    return text_list.GetHighlightedObject() if text_list is not None else None


def remember_comparison(movie, _args, _ret, _func):
    if not _enabled:
        return
    try:
        item = highlighted_item(movie)
        _comparisons[str(movie.Class.Name)] = (
            movie._path_name(), item._path_name() if item is not None else None)
    except Exception as exc:
        _comparisons.pop(str(movie.Class.Name), None)
        report_error(exc)


def leave_bank_compare(movie, _args, _ret, _func):
    _comparisons.pop(str(movie.Class.Name), None)
    after_card(movie, None, None, None)


def card_items(movie):
    """Associate native card slots with their items, including both compare cards."""
    kind = str(movie.Class.Name)
    paths = CARD_PREFIXES[kind]
    if kind == "ItemPickupGFxMovie":
        owner = getattr(movie, "MyHUDOwner", None)
        comparison = getattr(owner, "ItemComparison", ())
        return [(paths[0], comparison[0] if len(comparison) else None)]
    if kind == "WillowHUDGFxMovie":
        pc = get_pc()
        pawn = pc.Pawn if pc is not None else None
        hud = getattr(pc, "myHUD", None)
        comparison = getattr(hud, "ItemComparison", ())
        if (len(comparison) >= 2 and comparison[0] is not None
                and str(comparison[0].Class.Name) != "WillowWeapon"):
            return [(paths[0], comparison[1])]
        return [(paths[0], pawn.Weapon if pawn is not None else None)]
    if kind == "QuestAcceptGFxMovie":
        return [(paths[0], getattr(getattr(movie, "CardContents", None), "Inv", None))]
    item = highlighted_item(movie)
    source_movie, source_item = _comparisons.get(kind, (None, None))
    comparing = (source_movie == movie._path_name() if kind == "BankGFxMovie"
                 else bool(movie.IsComparing()))
    if not comparing:
        return [(paths[0], item)]
    result = [(paths[1], item)]
    if source_movie == movie._path_name() and source_item is not None:
        try:
            source = find_object("WillowInventory", source_item)
        except ValueError:
            source = None  # Item/menu may have gone away since comparison began.
        if source is not None:
            result.append((paths[0], source))
    return result


def apply_card(movie, card, weapon):
    if weapon is None or str(weapon.Class.Name) != "WillowWeapon":
        return
    _stats["weapon_cards"] += 1
    record = {"movie": movie._path_name(), "card": card,
              "weapon": weapon._path_name(), "internal_level": int(weapon.ExpLevel)}
    try:
        record.update(level_details(weapon))
        level = record["ordinary_required_level"]
        if level is None:
            record["result"] = "unsupported"
        else:
            # Native SetLevelRequirementIndicatorForCard writes precisely this
            # text field. Never change its met/unmet frame, visibility or colour.
            field = card + ".requirement.requirement"
            name = movie.GetVariableString(field + "._name")
            before = movie.GetVariableString(field + ".text")
            record["field_name"] = name
            record["before"] = before
            numbers = list(re.finditer(r"\d+", before or ""))
            if name != "requirement" or len(numbers) != 1:
                record["result"] = "missing_text"
            else:
                match = numbers[0]
                after = before[:match.start()] + str(level) + before[match.end():]
                if after != before:
                    movie.SetVariableString(field + ".text", after)
                    record["result"] = "text_writes"
                else:
                    record["result"] = "unchanged"
                record["after"] = movie.GetVariableString(field + ".text")
                if record["after"] != after:
                    record["result"] = "write_mismatch"
        _stats[record["result"]] += 1
    except Exception as exc:
        record["result"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
        report_error(exc)
    _recent_cards.append(record)


def after_card(movie, _args, _ret, _func):
    if not _enabled:
        return
    _stats["card_calls"] += 1
    try:
        for card, item in card_items(movie):
            apply_card(movie, card, item)
    except Exception as exc:
        report_error(exc)


_card_hooks = [hook(path, Type.POST, hook_identifier=f"ConsistentWeaponLevels.card:{path}")(
    after_card) for path in CARD_FUNCTIONS]
_compare_hooks = [hook(path, Type.PRE, hook_identifier=f"ConsistentWeaponLevels.compare:{path}")(
    remember_comparison) for path in (
        "WillowGame.StatusMenuExGFxMovie:extCompare",
        "WillowGame.VendingMachineGFxMovie:extCompare",
        "WillowGame.BankGFxMovie:StartComparing",
    )]
_compare_hooks.append(hook("WillowGame.BankGFxMovie:LeaveCompare", Type.POST)(leave_bank_compare))


def on_enable():
    global _enabled
    _comparisons.clear()
    _recent_cards.clear()
    _errors.clear()
    for key in _stats:
        _stats[key] = 0
    _enabled = True
    logging.info("[Consistent Weapon Levels] UI text fix enabled (no gameplay level hooks).")


def on_disable():
    global _enabled
    _enabled = False
    _comparisons.clear()


def export_diagnostics(_option=None):
    from .diagnostics import export
    try:
        path = export(SETTINGS_DIR, __version__, _enabled, _stats, _errors,
                      list(_recent_cards), [*_card_hooks, *_compare_hooks])
        if path is not None:
            logging.info(f"[Consistent Weapon Levels] Exported to {path}")
    except Exception as exc:
        report_error(exc)


__version__: str
__version_info__: tuple[int, ...]

build_mod(
    hooks=[*_card_hooks, *_compare_hooks],
    options=[ButtonOption("Export level diagnostics", on_press=export_diagnostics)],
    on_enable=on_enable,
    on_disable=on_disable,
)
