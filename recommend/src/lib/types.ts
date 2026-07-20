export interface CscdResponse<T> {
  success: boolean;
  message: string;
  code: number;
  result: T;
  timestamp: number;
}

export interface Reviewer {
  id: string;
  authorName: string;
  position: string | null;
  education: string | null;
  resume: string | null;
  keyword: string | null;
  advistor: string | null;
  email: string | null;
  org: string | null;
  academician: string | null;
  subject: string | null;
  numAllpaper: string | null;
  hindex: string | null;
}

export interface ArticleAuthor {
  authorSequence: number;
  authorName: string;
  institute: string | null;
  isCorresponding?: boolean;
  authorType?: string | null;
}

export interface Article {
  cscdId: string;
  title: string;
  pageString: string | null;
  articleNumber: string | null;
  citation: string | null;
  highlyCited: number;
  citedNum: number;
  articleUrl: string | null;
  keywords: string | null;
  doi: string | null;
  authors: ArticleAuthor[];
  journal: { issn: string; journalName: string } | null;
  issue: { year: string; volume: string; issue: string } | null;
  abstract: string | null;
}

export type AuthorRole = "first" | "corresponding" | "other";

export interface ArticleWithRole extends Article {
  role: AuthorRole;
}

export interface YearRoleCount {
  year: string;
  first: number;
  corresponding: number;
  other: number;
  total: number;
}

export type SortField = "hindex" | "numAllpaper" | "authorName" | "id";

export interface SearchRequest {
  keywords: string[];
  excludeOrgs: string[];
  excludeNames: string[];
  hasEmail: boolean;
}

export type { ResultFilters, ReviewerBounds } from "./result-filters";
export {
  DEFAULT_RESULT_FILTERS,
  filtersWithBounds,
} from "./result-filters";
