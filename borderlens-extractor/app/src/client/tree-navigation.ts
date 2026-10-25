import type { Family } from "../shared/models";
import { catalogueGroup } from "../shared/taxonomy";
export type TreeState = Record<string, boolean>;
export function familyTreePath(f: Family): string[] {
  const group = catalogueGroup(f);
  return ["Class mods", "Artifacts"].includes(group)
    ? [group, `${group}:${f.character || "Needs review"}`]
    : [group];
}
export function revealTreePath(state: TreeState, path: string[]): TreeState {
  const next = { ...state };
  for (const key of path) next[key] = false;
  return next;
}
export function stepTree(
  state: TreeState,
  paths: string[][],
  direction: "collapse" | "expand",
): TreeState {
  const next = { ...state },
    roots = [...new Set(paths.map((path) => path[0]))];
  const children = [
    ...new Map(
      paths.filter((path) => path.length > 1).map((path) => [path[1], path[0]]),
    ).entries(),
  ];
  if (direction === "collapse") {
    const openChildren = children.filter(
      ([key, parent]) => !state[parent] && !state[key],
    );
    if (openChildren.length) {
      for (const [key] of openChildren) next[key] = true;
    } else {
      for (const key of roots) next[key] = true;
      for (const [key] of children) next[key] = true;
    }
  } else {
    const closedRoots = roots.filter((key) => state[key]);
    if (closedRoots.length) {
      for (const key of closedRoots) next[key] = false;
      for (const [key, parent] of children)
        if (closedRoots.includes(parent)) next[key] = true;
    } else {
      for (const [key] of children) next[key] = false;
    }
  }
  return next;
}
