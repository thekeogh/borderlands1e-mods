"""Read-only loot metadata collected only when diagnostics are requested.

No gameplay observers, argument samples or extra native hooks. Initializer
signatures come from the discovery already required by the gameplay hooks.
"""

import re


class LootDiagnostics:
    def __init__(self, runtime):
        self.runtime = runtime
        self.initializer_signatures = []

    def snapshot(self):
        chests = []
        try:
            for obj in self.runtime.sdk.find_all("WillowInteractiveObject"):
                definition = getattr(obj, "InteractiveObjectDefinition", None)
                if definition is None or not re.search(r"chest|crate_metal", definition._path_name(), re.I):
                    continue
                chests.append({"object": obj._path_name(), "definition": definition._path_name(),
                               "class": str(obj.Class.Name), "usable": getattr(obj, "bCanBeUsed", None)})
                if len(chests) >= 24:
                    break
        except Exception as exc:
            self.runtime.problem("loot chest diagnostics", exc)
        return {"initializer_signatures": list(self.initializer_signatures), "chests": chests}
