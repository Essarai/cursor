"use client";

import { useMemo, useState } from "react";
import SearchForm from "@/components/SearchForm";
import ReviewerCard from "@/components/ReviewerCard";
import AuthorDetailModal from "@/components/AuthorDetailModal";
import ResultFiltersPanel from "@/components/ResultFiltersPanel";
import type { Reviewer, ReviewerBounds, SortField } from "@/lib/types";
import { filtersWithBounds } from "@/lib/types";
import { extractFilterOptions } from "@/lib/filter-options";
import {
  computeReviewerBounds,
  filterReviewers,
  sortReviewers,
} from "@/lib/utils";

export default function HomePage() {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [excludeOrgs, setExcludeOrgs] = useState<string[]>([]);
  const [excludeNames, setExcludeNames] = useState<string[]>([]);
  const [hasEmail, setHasEmail] = useState(false);
  const [reviewers, setReviewers] = useState<Reviewer[]>([]);
  const [bounds, setBounds] = useState<ReviewerBounds>({
    hMin: 0,
    hMax: 100,
    pMin: 0,
    pMax: 500,
  });
  const [filters, setFilters] = useState(filtersWithBounds(bounds));
  const [sortField, setSortField] = useState<SortField>("hindex");
  const [sortAsc, setSortAsc] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [apiTotal, setApiTotal] = useState<number | null>(null);
  const [selected, setSelected] = useState<Reviewer | null>(null);

  const filterOptions = useMemo(
    () => extractFilterOptions(reviewers),
    [reviewers]
  );

  const displayed = useMemo(() => {
    const filtered = filterReviewers(reviewers, filters, bounds);
    return sortReviewers(filtered, sortField, sortAsc);
  }, [reviewers, filters, bounds, sortField, sortAsc]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const handleSearch = async () => {
    setLoading(true);
    setError(null);
    setApiTotal(null);

    try {
      const res = await fetch("/api/reviewers/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keywords,
          excludeOrgs,
          excludeNames,
          hasEmail,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "检索失败");

      const list = data.reviewers ?? [];
      const nextBounds = computeReviewerBounds(list);
      setReviewers(list);
      setBounds(nextBounds);
      setFilters(filtersWithBounds(nextBounds));
      setSearched(true);
      setApiTotal(data.totalFromApi ?? null);
      showToast(
        `返回 ${data.totalFromApi ?? 0} 位，筛选后 ${data.count ?? 0} 位`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "检索失败");
      setReviewers([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-100 via-slate-50 to-white">
      <header className="border-b border-white/10 bg-gradient-to-br from-brand-700 via-brand-600 to-indigo-700 text-white shadow-lg">
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/15 text-xl backdrop-blur">
              📋
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
                CSCD 审稿人推荐
              </h1>
              <p className="mt-1.5 text-sm text-white/80">
                关键词智能推荐 · 多维度筛选 · 发文记录分析
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6">
        <SearchForm
          keywords={keywords}
          excludeOrgs={excludeOrgs}
          excludeNames={excludeNames}
          hasEmail={hasEmail}
          onKeywordsChange={setKeywords}
          onExcludeOrgsChange={setExcludeOrgs}
          onExcludeNamesChange={setExcludeNames}
          onHasEmailChange={setHasEmail}
          onSearch={handleSearch}
          loading={loading}
        />

        {error && (
          <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span className="mt-0.5">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {searched && !loading && (
          <ResultFiltersPanel
            filters={filters}
            onChange={setFilters}
            options={filterOptions}
            bounds={bounds}
            sortField={sortField}
            sortAsc={sortAsc}
            onSortFieldChange={setSortField}
            onSortAscChange={setSortAsc}
            apiTotal={apiTotal}
            resultCount={displayed.length}
            totalCount={reviewers.length}
          />
        )}

        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="card h-36 animate-pulse bg-gradient-to-r from-slate-100 to-slate-50"
              />
            ))}
          </div>
        )}

        {!loading && searched && displayed.length === 0 && (
          <div className="card px-6 py-16 text-center">
            <div className="mx-auto mb-4 text-4xl opacity-40">🔍</div>
            <p className="text-slate-600">未找到匹配的审稿人</p>
            <p className="mt-1 text-sm text-slate-400">
              请调整关键词或放宽筛选条件
            </p>
          </div>
        )}

        {!loading && displayed.length > 0 && (
          <div className="space-y-3">
            {displayed.map((r) => (
              <ReviewerCard
                key={r.id}
                reviewer={r}
                onClick={() => setSelected(r)}
              />
            ))}
          </div>
        )}

        {!searched && !loading && (
          <div className="card px-6 py-16 text-center">
            <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-brand-50 text-3xl">
              ✨
            </div>
            <h2 className="text-lg font-semibold text-slate-800">
              输入关键词，开始推荐审稿人
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-500">
              例如「计算机视觉」「深度学习」，系统将返回 CSCD 推荐的候选专家。
              支持按 H 指数、发文量滑块筛选，以及机构、学科等多选过滤。
            </p>
          </div>
        )}
      </main>

      <AuthorDetailModal reviewer={selected} onClose={() => setSelected(null)} />

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-xl bg-slate-900/90 px-5 py-3 text-sm text-white shadow-xl backdrop-blur">
          {toast}
        </div>
      )}

      <footer className="py-8 text-center text-xs text-slate-400">
        数据来源于 CSCD · 使用前请标注来源
      </footer>
    </div>
  );
}
