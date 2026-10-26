export type DuplicateMatch = {
  id: string;
  name: string;
  category: string;
  character?: string;
  reasons: string[];
};
export type DuplicateResults = {
  itemId: string;
  searched: number;
  total: number;
  matches: DuplicateMatch[];
};
