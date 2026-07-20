import { parseKeywordList } from "./cscd";
import type { Reviewer } from "./types";

function addUnique(set: Set<string>, value: string | null | undefined) {
  if (!value || value === "null") return;
  const v = value.trim();
  if (v) set.add(v);
}

export function extractFilterOptions(reviewers: Reviewer[]) {
  const authorNames = new Set<string>();
  const orgs = new Set<string>();
  const positions = new Set<string>();
  const educations = new Set<string>();
  const subjects = new Set<string>();
  const keywords = new Set<string>();
  const advistors = new Set<string>();

  for (const r of reviewers) {
    addUnique(authorNames, r.authorName);
    addUnique(orgs, r.org);
    addUnique(positions, r.position);
    addUnique(educations, r.education);
    addUnique(subjects, r.subject);
    addUnique(advistors, r.advistor);
    for (const kw of parseKeywordList(r.keyword)) {
      keywords.add(kw);
    }
  }

  const sort = (s: Set<string>) =>
    [...s].sort((a, b) => a.localeCompare(b, "zh-CN"));

  return {
    authorNames: sort(authorNames),
    orgs: sort(orgs),
    positions: sort(positions),
    educations: sort(educations),
    subjects: sort(subjects),
    keywords: sort(keywords),
    advistors: sort(advistors),
  };
}

export type FilterOptions = ReturnType<typeof extractFilterOptions>;
