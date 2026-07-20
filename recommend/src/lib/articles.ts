import type { Article, ArticleWithRole, AuthorRole, YearRoleCount } from "./types";

function normalizeName(name: string): string {
  return name.replace(/[*†#\s]/g, "").trim();
}

function namesMatch(a: string, b: string): boolean {
  const na = normalizeName(a);
  const nb = normalizeName(b);
  return na === nb || na.includes(nb) || nb.includes(na);
}

export function classifyAuthorRole(
  article: Article,
  reviewerName: string
): AuthorRole {
  const authors = article.authors ?? [];
  const match = authors.find((a) => namesMatch(a.authorName, reviewerName));
  if (!match) return "other";

  const seq = match.authorSequence;
  const name = match.authorName ?? "";
  const isMarked =
    /[*†]|通讯/.test(name) ||
    match.isCorresponding === true ||
    /通讯|corresponding/i.test(match.authorType ?? "");

  if (seq === 1) return "first";
  if (isMarked) return "corresponding";

  const lastSeq = Math.max(...authors.map((a) => a.authorSequence || 0));
  if (authors.length >= 2 && seq === lastSeq) return "corresponding";

  return "other";
}

export function attachRoles(
  articles: Article[],
  reviewerName: string
): ArticleWithRole[] {
  return articles.map((a) => ({
    ...a,
    role: classifyAuthorRole(a, reviewerName),
  }));
}

export function aggregateByYear(articles: ArticleWithRole[]): YearRoleCount[] {
  const map = new Map<string, YearRoleCount>();

  for (const a of articles) {
    const year = a.issue?.year ?? "未知";
    const row = map.get(year) ?? {
      year,
      first: 0,
      corresponding: 0,
      other: 0,
      total: 0,
    };
    row[a.role] += 1;
    row.total += 1;
    map.set(year, row);
  }

  return [...map.values()].sort((a, b) => a.year.localeCompare(b.year));
}

export const ROLE_LABELS: Record<AuthorRole, string> = {
  first: "第一作者",
  corresponding: "通讯作者",
  other: "其他作者",
};

export const ROLE_COLORS: Record<AuthorRole, string> = {
  first: "#2563eb",
  corresponding: "#059669",
  other: "#94a3b8",
};
