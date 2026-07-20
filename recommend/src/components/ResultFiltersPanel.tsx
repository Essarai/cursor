"use client";

import { useMemo, useState } from "react";
import MultiSelect from "@/components/MultiSelect";
import RangeSlider from "@/components/RangeSlider";
import type { FilterOptions } from "@/lib/filter-options";
import type { ResultFilters, ReviewerBounds, SortField } from "@/lib/types";
import { filtersWithBounds } from "@/lib/types";
import { countActiveFilters } from "@/lib/utils";

interface Props {
  filters: ResultFilters;
  onChange: (filters: ResultFilters) => void;
  options: FilterOptions;
  bounds: ReviewerBounds;
  sortField: SortField;
  sortAsc: boolean;
  onSortFieldChange: (f: SortField) => void;
  onSortAscChange: (asc: boolean) => void;
  apiTotal: number | null;
  resultCount: number;
  totalCount: number;
}

export default function ResultFiltersPanel({
  filters,
  onChange,
  options,
  bounds,
  sortField,
  sortAsc,
  onSortFieldChange,
  onSortAscChange,
  apiTotal,
  resultCount,
  totalCount,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const active = countActiveFilters(filters, bounds);

  const set = <K extends keyof ResultFilters>(key: K, value: ResultFilters[K]) => {
    onChange({ ...filters, [key]: value });
  };

  const academicianSelected = useMemo(() => {
    const s: string[] = [];
    if (filters.academician.includes("yes")) s.push("有院士信息");
    if (filters.academician.includes("no")) s.push("无院士信息");
    return s;
  }, [filters.academician]);

  const onAcademicianChange = (selected: string[]) => {
    const next: ("yes" | "no")[] = [];
    if (selected.includes("有院士信息")) next.push("yes");
    if (selected.includes("无院士信息")) next.push("no");
    set("academician", next);
  };

  return (
    <div className="card overflow-hidden">
      <div className="border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-800">结果筛选</h3>
            <p className="mt-0.5 text-xs text-slate-500">
              显示 {resultCount}
              {resultCount !== totalCount ? ` / ${totalCount}` : ""} 位
              {apiTotal != null && ` · CSCD 返回 ${apiTotal} 条`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {active > 0 && (
              <span className="rounded-full bg-brand-100 px-2.5 py-0.5 text-xs font-medium text-brand-700">
                {active} 个条件
              </span>
            )}
            <button
              type="button"
              className="rounded-lg px-2.5 py-1 text-xs text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
              onClick={() => onChange(filtersWithBounds(bounds))}
            >
              重置筛选
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-5 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <RangeSlider
            label="H 指数"
            min={bounds.hMin}
            max={bounds.hMax}
            valueMin={filters.minHindex}
            valueMax={filters.maxHindex}
            onChange={(min, max) => {
              onChange({ ...filters, minHindex: min, maxHindex: max });
            }}
          />
          <RangeSlider
            label="发文量"
            min={bounds.pMin}
            max={bounds.pMax}
            valueMin={filters.minPapers}
            valueMax={filters.maxPapers}
            onChange={(min, max) => {
              onChange({ ...filters, minPapers: min, maxPapers: max });
            }}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MultiSelect
            label="机构"
            options={options.orgs}
            selected={filters.orgs}
            onChange={(v) => set("orgs", v)}
            placeholder="不限机构"
          />
          <MultiSelect
            label="职称"
            options={options.positions}
            selected={filters.positions}
            onChange={(v) => set("positions", v)}
            placeholder="不限职称"
          />
          <MultiSelect
            label="学科"
            options={options.subjects}
            selected={filters.subjects}
            onChange={(v) => set("subjects", v)}
            placeholder="不限学科"
          />
          <MultiSelect
            label="学历"
            options={options.educations}
            selected={filters.educations}
            onChange={(v) => set("educations", v)}
            placeholder="不限学历"
          />
          <MultiSelect
            label="研究方向"
            options={options.keywords}
            selected={filters.keywords}
            onChange={(v) => set("keywords", v)}
            placeholder="不限方向"
          />
          <MultiSelect
            label="姓名"
            options={options.authorNames}
            selected={filters.authorNames}
            onChange={(v) => set("authorNames", v)}
            placeholder="不限姓名"
          />
        </div>

        <button
          type="button"
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
          onClick={() => setExpanded(!expanded)}
        >
          <svg
            className={`h-3.5 w-3.5 transition ${expanded ? "rotate-90" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          {expanded ? "收起" : "展开"}更多条件
        </button>

        {expanded && (
          <div className="grid gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2 lg:grid-cols-3">
            <MultiSelect
              label="导师"
              options={options.advistors}
              selected={filters.advistors}
              onChange={(v) => set("advistors", v)}
              placeholder="不限"
            />
            <MultiSelect
              label="院士"
              options={["有院士信息", "无院士信息"]}
              selected={academicianSelected}
              onChange={onAcademicianChange}
              placeholder="不限"
            />
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-600">邮箱</label>
              <input
                className="input py-2 text-sm"
                placeholder="模糊匹配"
                value={filters.email}
                onChange={(e) => set("email", e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-600">简介</label>
              <input
                className="input py-2 text-sm"
                placeholder="模糊匹配"
                value={filters.resume}
                onChange={(e) => set("resume", e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-600">作者 ID</label>
              <input
                className="input py-2 text-sm"
                placeholder="精确或部分匹配"
                value={filters.id}
                onChange={(e) => set("id", e.target.value)}
              />
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-4 border-t border-slate-100 pt-4">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={filters.hasEmail}
              onChange={(e) => set("hasEmail", e.target.checked)}
              className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            仅显示有邮箱
          </label>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">排序</span>
            <select
              className="input w-auto py-1.5 text-sm"
              value={sortField}
              onChange={(e) => onSortFieldChange(e.target.value as SortField)}
            >
              <option value="hindex">H 指数</option>
              <option value="numAllpaper">发文量</option>
              <option value="authorName">姓名</option>
              <option value="id">作者 ID</option>
            </select>
            <button
              type="button"
              className="btn-ghost px-2 py-1.5"
              onClick={() => onSortAscChange(!sortAsc)}
              title={sortAsc ? "升序" : "降序"}
            >
              {sortAsc ? "↑ 升序" : "↓ 降序"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
