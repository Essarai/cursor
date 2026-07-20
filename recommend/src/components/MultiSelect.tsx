"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  label: string;
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  maxHeight?: number;
}

export default function MultiSelect({
  label,
  options,
  selected,
  onChange,
  placeholder = "选择…",
  maxHeight = 200,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const filtered = options.filter((o) =>
    o.toLowerCase().includes(query.trim().toLowerCase())
  );

  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((s) => s !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  const summary =
    selected.length === 0
      ? placeholder
      : selected.length <= 2
        ? selected.join("、")
        : `已选 ${selected.length} 项`;

  return (
    <div ref={ref} className="relative">
      <label className="mb-1.5 block text-xs font-medium text-slate-600">
        {label}
      </label>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`flex w-full items-center justify-between rounded-lg border bg-white px-3 py-2 text-left text-sm transition ${
          open
            ? "border-brand-500 ring-2 ring-brand-100"
            : "border-slate-200 hover:border-slate-300"
        } ${selected.length ? "text-slate-800" : "text-slate-400"}`}
      >
        <span className="truncate pr-2">{summary}</span>
        <svg
          className={`h-4 w-4 shrink-0 text-slate-400 transition ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {selected.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {selected.map((s) => (
            <span
              key={s}
              className="inline-flex items-center gap-1 rounded-md bg-brand-50 px-2 py-0.5 text-xs text-brand-700"
            >
              <span className="max-w-[120px] truncate">{s}</span>
              <button
                type="button"
                onClick={() => toggle(s)}
                className="opacity-60 hover:opacity-100"
                aria-label={`移除 ${s}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {open && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
          {options.length > 6 && (
            <div className="border-b border-slate-100 p-2">
              <input
                className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm outline-none focus:border-brand-500"
                placeholder="搜索…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoFocus
              />
            </div>
          )}
          <div className="overflow-y-auto p-1" style={{ maxHeight }}>
            {filtered.length === 0 ? (
              <p className="px-3 py-2 text-xs text-slate-400">无匹配项</p>
            ) : (
              filtered.map((opt) => {
                const checked = selected.includes(opt);
                return (
                  <label
                    key={opt}
                    className={`flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 text-sm transition hover:bg-slate-50 ${
                      checked ? "bg-brand-50/50" : ""
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(opt)}
                      className="mt-0.5 rounded border-slate-300 text-brand-600"
                    />
                    <span className="leading-snug text-slate-700">{opt}</span>
                  </label>
                );
              })
            )}
          </div>
          {selected.length > 0 && (
            <div className="border-t border-slate-100 p-2">
              <button
                type="button"
                className="w-full rounded-md py-1 text-xs text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                onClick={() => onChange([])}
              >
                清空选择
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
