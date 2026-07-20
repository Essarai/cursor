export type SortField = "hindex" | "numAllpaper" | "authorName" | "id";

export interface ReviewerBounds {
  hMin: number;
  hMax: number;
  pMin: number;
  pMax: number;
}

export interface ResultFilters {
  authorNames: string[];
  orgs: string[];
  positions: string[];
  educations: string[];
  subjects: string[];
  keywords: string[];
  advistors: string[];
  academician: ("yes" | "no")[];
  email: string;
  resume: string;
  id: string;
  minHindex: number;
  maxHindex: number;
  minPapers: number;
  maxPapers: number;
  hasEmail: boolean;
}

export const DEFAULT_RESULT_FILTERS: ResultFilters = {
  authorNames: [],
  orgs: [],
  positions: [],
  educations: [],
  subjects: [],
  keywords: [],
  advistors: [],
  academician: [],
  email: "",
  resume: "",
  id: "",
  minHindex: 0,
  maxHindex: 0,
  minPapers: 0,
  maxPapers: 0,
  hasEmail: false,
};

export function filtersWithBounds(bounds: ReviewerBounds): ResultFilters {
  return {
    ...DEFAULT_RESULT_FILTERS,
    minHindex: bounds.hMin,
    maxHindex: bounds.hMax,
    minPapers: bounds.pMin,
    maxPapers: bounds.pMax,
  };
}
