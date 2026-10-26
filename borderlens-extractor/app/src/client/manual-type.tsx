import type { Family } from "../shared/models";
import { weaponTypes } from "../shared/taxonomy";
import { equipmentTypes, type ManualType } from "../shared/manual-type";
export function ManualTypePicker({
  family,
  disabled,
  change,
}: {
  family: Family;
  disabled: boolean;
  change: (type: ManualType) => void;
}) {
  const manual = family.classification?.origin === "manual";
  const value = manual
    ? family.category === "Weapons"
      ? family.classification?.weaponType || ""
      : family.category
    : "";
  return (
    <div className="manual-classification manual-type-picker">
      <label>
        Item type
        <select
          aria-label="Item type"
          disabled={disabled}
          value={value}
          onChange={(event) =>
            change((event.target.value || null) as ManualType)
          }
        >
          <option value="">Automatic — research / game data</option>
          <optgroup label="Weapons">
            {weaponTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </optgroup>
          <optgroup label="Equipment">
            {equipmentTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
      <p className="muted small">
        {manual
          ? "Manual choice takes priority. Select Automatic to restore research/game data."
          : "Choose a type to override it manually."}{" "}
        Updates immediately; no AI or rebuild.
      </p>
    </div>
  );
}
