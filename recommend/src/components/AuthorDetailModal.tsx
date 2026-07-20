"use client";

import { useEffect, useState } from "react";
import type { Reviewer, ArticleWithRole } from "@/lib/types";
import type { YearRoleCount } from "@/lib/types";
import ArticlesYearChart from "./ArticlesYearChart";
import { ROLE_COLORS, ROLE_LABELS } from "@/lib/articles";

interface Props {
  reviewer: Reviewer | null;
  onClose: () => void;
}

export default function AuthorDetailModal({ reviewer, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [articles, setArticles] = useState<ArticleWithRole[]>([]);
  const [byYear, setByYear] = useState<YearRoleCount[]>([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!reviewer) return;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ author: reviewer.authorName });
        if (reviewer.org) params.set("institute", reviewer.org);
        const res = await fetch(`/api/reviewers/articles?${params}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "加载失败");
        setArticles(data.articles ?? []);
        setByYear(data.byYear ?? []);
        setTotal(data.total ?? 0);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败");
        setArticles([]);
        setByYear([]);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [reviewer]);

  if (!reviewer) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-white shadow-xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              {reviewer.authorName}
            </h2>
            <p className="mt-0.5 text-sm text-slate-500">{reviewer.org ?? "—"}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            ✕
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-4">
          {loading && (
            <div className="space-y-3 py-8">
              <div className="h-32 animate-pulse rounded-lg bg-slate-100" />
              <div className="h-20 animate-pulse rounded-lg bg-slate-100" />
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {!loading && !error && (
            <>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-medium text-slate-800">
                  发文年份分布
                </h3>
                <span className="text-xs text-slate-400">
                  CSCD 共 {total} 篇，已加载 {articles.length} 篇
                </span>
              </div>
              <p className="mb-4 text-xs text-slate-400">
                通讯作者：CSCD 未单独提供该字段时，按末位作者或姓名标注符号推断
              </p>
              <ArticlesYearChart data={byYear} />

              <h3 className="mb-3 mt-6 text-sm font-medium text-slate-800">
                论文列表
              </h3>
              <ul className="space-y-3">
                {[...articles]
                  .sort((a, b) =>
                    (b.issue?.year ?? "").localeCompare(a.issue?.year ?? "")
                  )
                  .map((a) => (
                    <li
                      key={a.cscdId}
                      className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className="rounded px-2 py-0.5 text-xs font-medium text-white"
                          style={{ backgroundColor: ROLE_COLORS[a.role] }}
                        >
                          {ROLE_LABELS[a.role]}
                        </span>
                        <span className="text-xs text-slate-400">
                          {a.issue?.year ?? "—"} · {a.journal?.journalName ?? "—"}
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm font-medium text-slate-800">
                        {a.title}
                      </p>
                      {a.articleUrl && (
                        <a
                          href={a.articleUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1 inline-block text-xs text-brand-600 hover:underline"
                        >
                          查看 CSCD 详情
                        </a>
                      )}
                    </li>
                  ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
