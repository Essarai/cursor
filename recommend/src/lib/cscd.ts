import type { Article, CscdResponse, Reviewer } from "./types";

const BASE_URL =
  process.env.CSCD_BASE_URL ??
  "http://sciencechina.cn/cscdboot/CscdService";

let cachedApiCode: string | null = null;
let apiCodeExpiresAt = 0;

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  return (await res.json()) as T;
}

function isAppCodeError(message?: string): boolean {
  return !!message?.includes("AppCode");
}

async function fetchApiCodeFromCredentials(): Promise<string> {
  const user = process.env.CSCD_USER;
  const password = process.env.CSCD_PASSWORD;
  if (!user || !password) {
    throw new Error(
      "ApiCode 已失效，请在 .env.local 更新 CSCD_API_CODE，或配置 CSCD_USER / CSCD_PASSWORD"
    );
  }

  const params = new URLSearchParams({ user, password });
  const data = await fetchJson<CscdResponse<string>>(
    `${BASE_URL}/getApiCode?${params}`
  );

  if (!data.success || !data.result) {
    const msg = data.message || "获取 ApiCode 失败";
    if (msg.includes("申请失败")) {
      throw new Error(
        "CSCD 账号无法获取 ApiCode（申请失败）。请确认账号已开通 API 权限、IP 已加入白名单，或在 .env.local 中填入有效的 CSCD_API_CODE（约 10 分钟有效）"
      );
    }
    throw new Error(msg);
  }

  cachedApiCode = data.result;
  apiCodeExpiresAt = Date.now() + 9 * 60 * 1000;
  return data.result;
}

async function obtainApiCode(forceRefresh = false): Promise<string> {
  if (!forceRefresh && cachedApiCode && Date.now() < apiCodeExpiresAt) {
    return cachedApiCode;
  }

  if (forceRefresh && process.env.CSCD_USER && process.env.CSCD_PASSWORD) {
    return fetchApiCodeFromCredentials();
  }

  const directCode = process.env.CSCD_API_CODE;
  if (directCode && !forceRefresh) {
    cachedApiCode = directCode;
    apiCodeExpiresAt = Date.now() + 9 * 60 * 1000;
    return directCode;
  }

  if (process.env.CSCD_USER && process.env.CSCD_PASSWORD) {
    return fetchApiCodeFromCredentials();
  }

  if (directCode) {
    cachedApiCode = directCode;
    apiCodeExpiresAt = Date.now() + 9 * 60 * 1000;
    return directCode;
  }

  throw new Error("请配置 CSCD_API_CODE 或 CSCD_USER / CSCD_PASSWORD");
}

function invalidateApiCode() {
  cachedApiCode = null;
  apiCodeExpiresAt = 0;
}

async function withApiCode<T>(
  request: (apiCode: string) => Promise<CscdResponse<T>>
): Promise<T> {
  let apiCode = await obtainApiCode();

  for (let attempt = 0; attempt < 2; attempt++) {
    const data = await request(apiCode);
    if (data.success) {
      return data.result as T;
    }
    if (isAppCodeError(data.message) && attempt === 0) {
      invalidateApiCode();
      apiCode = await obtainApiCode(true);
      continue;
    }
    if (isAppCodeError(data.message)) {
      throw new Error(
        "ApiCode 已过期。请在 .env.local 更新 CSCD_API_CODE，或配置可用的 CSCD_USER / CSCD_PASSWORD 后重启服务"
      );
    }
    throw new Error(data.message || "CSCD 接口请求失败");
  }

  throw new Error("CSCD 接口请求失败");
}

export function normalizeKeywords(input: string | string[]): string {
  const parts = Array.isArray(input)
    ? input
    : input.split(/[;；,，、\n]+/).map((s) => s.trim());
  return parts.filter(Boolean).join(";;");
}

export async function searchReviewers(
  keywords: string | string[]
): Promise<Reviewer[]> {
  const keywordStr = normalizeKeywords(keywords);
  if (!keywordStr) {
    throw new Error("请至少输入一个关键词");
  }

  const params = new URLSearchParams({ keywords: keywordStr });
  const result = await withApiCode((apiCode) =>
    fetchJson<CscdResponse<Reviewer[]>>(
      `${BASE_URL}/getPeerReviewers?${params}`,
      { headers: { ApiCode: apiCode } }
    )
  );

  return result ?? [];
}

interface SearchArticlesResult {
  total: number;
  page: number;
  limit: number;
  data: Article[];
}

export async function searchArticlesPage(params: {
  author: string;
  institute?: string;
  page?: number;
  limit?: number;
}): Promise<SearchArticlesResult> {
  const qs = new URLSearchParams({
    author: params.author,
    page: String(params.page ?? 1),
    limit: String(params.limit ?? 50),
  });
  if (params.institute?.trim()) {
    qs.set("institute", params.institute.trim());
  }

  const result = await withApiCode((apiCode) =>
    fetchJson<CscdResponse<SearchArticlesResult>>(
      `${BASE_URL}/searchArticles?${qs}`,
      { headers: { ApiCode: apiCode } }
    )
  );

  if (!result) {
    throw new Error("检索文献失败");
  }
  return result;
}

export async function fetchAllArticlesByAuthor(
  author: string,
  institute?: string
): Promise<{ articles: Article[]; total: number }> {
  const first = await searchArticlesPage({ author, institute, page: 1, limit: 50 });
  const articles = [...first.data];
  const totalPages = Math.ceil(first.total / 50);

  for (let page = 2; page <= totalPages && page <= 20; page++) {
    const next = await searchArticlesPage({ author, institute, page, limit: 50 });
    articles.push(...next.data);
  }

  return { articles, total: first.total };
}

export function parseKeywordList(keyword: string | null): string[] {
  if (!keyword) return [];
  return keyword
    .split(";;")
    .map((k) => k.trim())
    .filter(Boolean);
}

export function parseNumeric(value: string | null): number {
  if (!value || value === "null") return 0;
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}
