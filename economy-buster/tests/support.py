"""SDK models for captured money formulas; not a native Unreal emulator."""

from contextlib import ExitStack
import importlib.util
import inspect
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source/sdk_mods/EconomyBuster"
FIXTURE = json.loads((ROOT / "tests/fixtures/bl1e_economy.json").read_text())


class Schema:
    def __init__(self, name, obj=None):
        self.Name, self.obj = name, obj

    def _path_name(self):
        return self.Name

    def _properties(self):
        return [SimpleNamespace(Name=k) for k in vars(self.obj)
                if not k.startswith("_") and k not in ("Class", "ObjectFlags", "path", "sdk")]


class Object(SimpleNamespace):
    def __init__(self, path="Object", class_name="AttributeDefinition", **kwargs):
        super().__init__(path=path, ObjectFlags=0, **kwargs)
        self.Class = Schema(class_name, self)

    def _path_name(self):
        return self.path

    def _get_address(self):
        return id(self)


class Struct(SimpleNamespace):
    @property
    def _type(self):
        return Schema("CapturedStruct", self)


class SDK:
    def __init__(self):
        self.objects = {p: Object(p, r["class"]) for p, r in FIXTURE["definitions"].items()}
        self.inventory, self.vendors, self.loads = [], [], []
        self.callbacks = []
        for path, record in FIXTURE["definitions"].items():
            for key, value in record["fields"].items():
                setattr(self.objects[path], key, self.convert(value))

    def convert(self, value):
        if isinstance(value, dict):
            if "ref" in value:
                path = value["ref"]
                if path not in self.objects:
                    self.objects[path] = Object(path, value["class"])
                return self.objects[path]
            if "struct" in value:
                return Struct(**{k: self.convert(v) for k, v in value["fields"].items()})
            return {k: self.convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.convert(v) for v in value]
        return value

    def find_object(self, _class, path):
        return self.objects[path]

    def load_package(self, path):
        self.loads.append(path)

    def find_all(self, name, exact=True):
        assert exact is False
        return iter(self.vendors if name == "WillowVendingMachine" else self.inventory)

    def input(self, value, ctx):
        if value.InitializationDefinition is not None:
            number = self.formula(value.InitializationDefinition, ctx)
        elif value.BaseValueAttribute is None:
            number = value.BaseValueConstant
        else:
            path = value.BaseValueAttribute._path_name()
            if path.endswith("InventoryPartCashValueModifierTotal"):
                number = ctx.CashValueModifierTotal
            elif path.endswith("GameStage"):
                number = ctx.GameStage
            elif path.endswith("AttrSlotValue_BaseCredits"):
                number = ctx.computed_cash_slot
            elif path.endswith("PlayerCurrencyOnHand"):
                number = ctx.CurrencyOnHand
            else:
                number = ctx.ExpLevel
        return number * value.BaseValueScaleConstant

    def formula(self, definition, ctx):
        f = definition.ValueFormula
        return self.input(f.Multiplier, ctx) * self.input(f.Level, ctx) ** self.input(f.Power, ctx) + self.input(f.Offset, ctx)

    def dispatch(self, path, obj, args, native=lambda: None):
        for callback in self.callbacks:
            for target, phase in callback.specs:
                if target == path and phase == "PRE":
                    assert callback(obj, args, None, None) is None  # No native blocking/override.
        ret = native()
        for callback in self.callbacks:
            for target, phase in callback.specs:
                if target == path and phase in ("POST", "POST_UNCONDITIONAL"):
                    assert callback(obj, args, ret, None) is None
        return ret

    def item(self, definition="gd_shields.A_Item.Item_Shield", level=69, modifier=38.4, class_name="WillowEquipAbleItem"):
        sdk = self

        class Item(Object):
            def ComputeCashValue(self):
                return sdk.dispatch("Engine.WillowInventory:ComputeCashValue", self, Struct(),
                    lambda: int(sdk.input(self.DefinitionData.ItemDefinition.CashValue, self)))

            def InitializeAttributeSlots(self, *, bIncludeNameParts):
                def native():
                    self.slot_calls += 1
                    self.computed_cash_slot = sdk.input(self.DefinitionData.ItemDefinition.AttributeSlotEffects[0].BaseModifierValue, self)
                return sdk.dispatch("WillowGame.WillowItem:InitializeAttributeSlots", self,
                                    Struct(bIncludeNameParts=bIncludeNameParts), native)

        item = Item("Map.Item" + str(len(self.inventory)), class_name,
                    DefinitionData=Struct(ItemDefinition=self.objects[definition], ManufacturerGradeIndex=786501,
                                          UniqueId=12345), ExpLevel=level, CashValueModifierTotal=modifier,
                    CashValue=999999, Quantity=1, Owner=None, bDeleteMe=False, bPendingDelete=False,
                    slot_calls=0, computed_cash_slot=99999, ShieldCapacity=4200, RarityLevel=5)
        self.inventory.append(item)
        return item


def load_mod(tempdir):
    stack = ExitStack()
    sdk = SDK()
    sdk_module = ModuleType("unrealsdk")
    for name in ("find_object", "find_all", "load_package"):
        setattr(sdk_module, name, getattr(sdk, name))
    sdk_module.__version__ = "test-sdk"
    messages = []
    sdk_module.logging = SimpleNamespace(info=lambda m: messages.append(("info", m)),
                                         error=lambda m: messages.append(("error", m)))
    hooks_module = ModuleType("unrealsdk.hooks")
    hooks_module.Type = SimpleNamespace(PRE="PRE", POST="POST", POST_UNCONDITIONAL="POST_UNCONDITIONAL")
    mods = ModuleType("mods_base")
    mods.SETTINGS_DIR = Path(tempdir)
    pc = Object("Map.PC", "WillowPlayerController", Pawn=SimpleNamespace(GetExpLevel=lambda: 69),
                PlayerReplicationInfo=SimpleNamespace(CurrencyOnHand=1234567),
                WorldInfo=Object("Map.World", "WorldInfo", GetMapName=lambda: "Arid_P"),
                GetCurrentPlaythrough=lambda: 0)
    mods.pc = pc
    mods.get_pc = lambda: mods.pc
    mods.get_ordered_mod_list = lambda: [SimpleNamespace(name="One Playthrough", version="4.7.0", author="keogh", is_enabled=True)]
    mods.Game = SimpleNamespace(get_current=lambda: "BL1E")
    mods.ButtonOption = lambda name, **kw: SimpleNamespace(name=name, **kw)

    def hook(path, phase="PRE", hook_identifier=None):
        def decorate(callback):
            callback.specs = getattr(callback, "specs", []) + [(path, phase)]
            callback.hook_identifier = hook_identifier or callback.__name__
            callback.get_active_count = lambda: len(callback.specs)
            return callback
        return decorate
    mods.hook = hook

    def build_mod(**kw):
        mods.registration = kw
        caller = inspect.currentframe().f_back.f_globals
        caller["__version__"] = "0.1.1"
        caller["__version_info__"] = (0, 1, 1)
    mods.build_mod = build_mod
    stack.enter_context(patch.dict(sys.modules, {"unrealsdk": sdk_module, "unrealsdk.hooks": hooks_module, "mods_base": mods}))
    for key in list(sys.modules):
        if key == "EconomyBuster" or key.startswith("EconomyBuster."):
            del sys.modules[key]
    spec = importlib.util.spec_from_file_location("EconomyBuster", SOURCE / "__init__.py", submodule_search_locations=[str(SOURCE)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    sdk.callbacks = module.HOOKS
    return stack, sdk, mods, module, pc, messages
