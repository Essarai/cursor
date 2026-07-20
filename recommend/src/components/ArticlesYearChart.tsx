"use client";

import type { YearRoleCount, AuthorRole } from "@/lib/types";
import { ROLE_COLORS, ROLE_LABELS } from "@/lib/articles";

interface Props {
  data: YearRoleCount[];
}

export default function ArticlesYearChart({ data }: Props) {
  if (!data.length) {
    return (
      <p className="py-8 text-center text-sm text-slate-400">暂无发文数据</p>
    );
  }

  const maxTotal = Math.max(...data.map((d) => d.total), 1);

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-4 text-xs text-slate-600">
        {(Object.keys(ROLE_LABELS) as AuthorRole[]).map((role) => (
          <span key={role} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: ROLE_COLORS[role] }}
            />
            {ROLE_LABELS[role]}
          </span>
        ))}
      </div>

      <div className="flex items-end gap-2 overflow-x-auto pb-2">
        {data.map((row) => (
          <div key={row.year} className="flex min-w-[44px] flex-col items-center">
            <div
              className="flex w-9 flex-col-reverse overflow-hidden rounded-t-md border border-slate-200 bg-slate-50"
              style={{ height: `${Math.max(24, (row.total / maxTotal) * 160)}px` }}
              title={`${row.year}: ${row.total} 篇`}
            >
              {(["other", "corresponding", "first"] as AuthorRole[]).map((role) => {
                const count = row[role];
                if (!count) return null;
                return (
                  <div
                    key={role}
                    style={{
                      backgroundColor: ROLE_COLORS[role],
                      flex: count,
                    }}
                    title={`${ROLE_LABELS[role]}: ${count}`}
                  />
                );
              })}
            </div>
            <span className="mt-1.5 text-[11px] text-slate-500">{row.year}</span>
            <span className="text-[10px] text-slate-400">{row.total}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
