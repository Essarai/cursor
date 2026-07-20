"use client";

import { parseKeywordList, parseNumeric } from "@/lib/cscd";
import type { Reviewer } from "@/lib/types";

interface Props {
  reviewer: Reviewer;
  onClick: () => void;
}

export default function ReviewerCard({ reviewer, onClick }: Props) {
  const keywords = parseKeywordList(reviewer.keyword).slice(0, 5);
  const hindex = parseNumeric(reviewer.hindex);
  const papers = parseNumeric(reviewer.numAllpaper);
  const isAcademician =
    reviewer.academician && reviewer.academician !== "null";

  return (
    <button
      type="button"
      onClick={onClick}
      className="group card w-full overflow-hidden p-0 text-left transition hover:border-brand-300 hover:shadow-lg hover:shadow-brand-100/50"
    >
      <div className="flex">
        <div className="w-1 shrink-0 bg-gradient-to-b from-brand-500 to-indigo-500 opacity-0 transition group-hover:opacity-100" />

        <div className="min-w-0 flex-1 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-lg font-semibold text-slate-900 group-hover:text-brand-700">
                  {reviewer.authorName}
                </h3>
                {reviewer.position && (
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                    {reviewer.position}
                  </span>
                )}
                {reviewer.education && (
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                    {reviewer.education}
                  </span>
                )}
                {isAcademician && (
                  <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                    院士
                  </span>
                )}
              </div>

              {reviewer.org && reviewer.org !== "null" && (
                <p className="mt-1.5 text-sm text-slate-600">{reviewer.org}</p>
              )}

              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                {reviewer.subject && reviewer.subject !== "null" && (
                  <span>学科：{reviewer.subject}</span>
                )}
                {reviewer.email && reviewer.email !== "null" && (
                  <span className="text-brand-600">{reviewer.email}</span>
                )}
              </div>
            </div>

            <div className="flex shrink-0 gap-3">
              <div className="rounded-xl bg-brand-50 px-3 py-2 text-center">
                <div className="text-lg font-bold tabular-nums text-brand-700">
                  {hindex || "—"}
                </div>
                <div className="text-[10px] font-medium uppercase tracking-wide text-brand-500/80">
                  H 指数
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 px-3 py-2 text-center">
                <div className="text-lg font-bold tabular-nums text-slate-700">
                  {papers || "—"}
                </div>
                <div className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
                  发文量
                </div>
              </div>
            </div>
          </div>

          {keywords.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {keywords.map((kw) => (
                <span
                  key={kw}
                  className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                >
                  {kw}
                </span>
              ))}
            </div>
          )}

          {reviewer.resume && reviewer.resume !== "null" && (
            <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-400">
              {reviewer.resume}
            </p>
          )}

          <p className="mt-3 text-xs font-medium text-brand-600 opacity-0 transition group-hover:opacity-100">
            查看发文记录 →
          </p>
        </div>
      </div>
    </button>
  );
}
