import type { ResultFilters, Reviewer, ReviewerBounds, SearchRequest, SortField } from "./types";
import { DEFAULT_RESULT_FILTERS } from "./result-filters";
import { parseKeywordList, parseNumeric } from "./cscd";

function includesText(value: string | null | undefined, query: string): boolean {
  if (!query.trim()) return true;
  const v = value ?? "";
  if (v === "null") return false;
  return v.toLowerCase().includes(query.trim().toLowerCase());
}

function matchesAny(
  value: string | null | undefined,
  selected: string[]
): boolean {
  if (selected.length === 0) return true;
  const v = (value ?? "").trim();
  if (!v || v === "null") return false;
  return selected.some((s) => v.includes(s) || s.includes(v));
}

function matchesKeywords(
  keyword: string | null | undefined,
  selected: string[]
): boolean {
  if (selected.length === 0) return true;
  const list = parseKeywordList(keyword ?? null);
  return selected.some((s) =>
    list.some((k) => k.includes(s) || s.includes(k))
  );
}

function hasAcademician(value: string | null | undefined): boolean {
  if (!value || value === "null") return false;
  return value.trim().length > 0;
}

export function computeReviewerBounds(reviewers: Reviewer[]): ReviewerBounds {
  if (reviewers.length === 0) {
    return { hMin: 0, hMax: 100, pMin: 0, pMax: 500 };
  }

  let hMin = Infinity;
  let hMax = -Infinity;
  let pMin = Infinity;
  let pMax = -Infinity;

  for (const r of reviewers) {
    const h = parseNumeric(r.hindex);
    const p = parseNumeric(r.numAllpaper);
    hMin = Math.min(hMin, h);
    hMax = Math.max(hMax, h);
    pMin = Math.min(pMin, p);
    pMax = Math.max(pMax, p);
  }

  if (hMax <= hMin) hMax = hMin + 1;
  if (pMax <= pMin) pMax = pMin + 1;

  return { hMin, hMax, pMin, pMax };
}

export function applySearchFilters(
  reviewers: Reviewer[],
  req: SearchRequest
): Reviewer[] {
  return reviewers.filter((r) => {
    if (req.hasEmail && !r.email) return false;

    for (const org of req.excludeOrgs) {
      if (org.trim() && (r.org ?? "").includes(org.trim())) return false;
    }

    for (const name of req.excludeNames) {
      if (name.trim() && (r.authorName ?? "").includes(name.trim())) {
        return false;
      }
    }

    return true;
  });
}

export function filterReviewers(
  reviewers: Reviewer[],
  filters: ResultFilters,
  bounds?: ReviewerBounds
): Reviewer[] {
  return reviewers.filter((r) => {
    if (filters.hasEmail && !r.email) return false;

    if (!includesText(r.id, filters.id)) return false;
    if (!includesText(r.email, filters.email)) return false;
    if (!includesText(r.resume, filters.resume)) return false;

    if (!matchesAny(r.authorName, filters.authorNames)) return false;
    if (!matchesAny(r.org, filters.orgs)) return false;
    if (!matchesAny(r.position, filters.positions)) return false;
    if (!matchesAny(r.education, filters.educations)) return false;
    if (!matchesAny(r.subject, filters.subjects)) return false;
    if (!matchesAny(r.advistor, filters.advistors)) return false;
    if (!matchesKeywords(r.keyword, filters.keywords)) return false;

    if (filters.academician.length > 0) {
      const isAcad = hasAcademician(r.academician);
      const wantYes = filters.academician.includes("yes");
      const wantNo = filters.academician.includes("no");
      if (wantYes && wantNo) {
        // both selected = show all
      } else if (wantYes && !isAcad) return false;
      else if (wantNo && isAcad) return false;
    }

    const h = parseNumeric(r.hindex);
    if (h < filters.minHindex || h > filters.maxHindex) return false;

    const p = parseNumeric(r.numAllpaper);
    if (p < filters.minPapers || p > filters.maxPapers) return false;

    return true;
  });
}

export function countActiveFilters(
  filters: ResultFilters,
  bounds?: ReviewerBounds
): number {
  let n = 0;
  if (filters.authorNames.length) n++;
  if (filters.orgs.length) n++;
  if (filters.positions.length) n++;
  if (filters.educations.length) n++;
  if (filters.subjects.length) n++;
  if (filters.keywords.length) n++;
  if (filters.advistors.length) n++;
  if (filters.academician.length === 1) n++;
  if (filters.email.trim()) n++;
  if (filters.resume.trim()) n++;
  if (filters.id.trim()) n++;
  if (filters.hasEmail) n++;

  if (bounds) {
    if (filters.minHindex > bounds.hMin || filters.maxHindex < bounds.hMax) n++;
    if (filters.minPapers > bounds.pMin || filters.maxPapers < bounds.pMax) n++;
  } else {
    if (filters.minHindex > 0 || filters.maxHindex > 0) n++;
    if (filters.minPapers > 0 || filters.maxPapers > 0) n++;
  }

  return n;
}

export function sortReviewers(
  reviewers: Reviewer[],
  field: SortField,
  asc: boolean
): Reviewer[] {
  const sorted = [...reviewers].sort((a, b) => {
    if (field === "authorName") {
      return (a.authorName ?? "").localeCompare(b.authorName ?? "", "zh-CN");
    }
    if (field === "id") {
      return (a.id ?? "").localeCompare(b.id ?? "", "zh-CN");
    }
    return parseNumeric(a[field]) - parseNumeric(b[field]);
  });
  return asc ? sorted : sorted.reverse();
}

export { DEFAULT_RESULT_FILTERS };
