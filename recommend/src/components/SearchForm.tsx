"use client";

import TagField from "./TagField";

interface Props {
  keywords: string[];
  excludeOrgs: string[];
  excludeNames: string[];
  hasEmail: boolean;
  onKeywordsChange: (v: string[]) => void;
  onExcludeOrgsChange: (v: string[]) => void;
  onExcludeNamesChange: (v: string[]) => void;
  onHasEmailChange: (v: boolean) => void;
  onSearch: () => void;
  loading: boolean;
}

export default function SearchForm({
  keywords,
  excludeOrgs,
  excludeNames,
  hasEmail,
  onKeywordsChange,
  onExcludeOrgsChange,
  onExcludeNamesChange,
  onHasEmailChange,
  onSearch,
  loading,
}: Props) {
  return (
    <div className="card overflow-hidden shadow-md shadow-slate-200/50">
      <div className="border-b border-slate-100 bg-gradient-to-r from-white to-slate-50/80 px-6 py-4">
        <h2 className="text-base font-semibold text-slate-900">检索条件</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          输入论文关键词，从 CSCD 获取候选审稿人（每次最多 100 位）
        </p>
      </div>

      <div className="space-y-5 p-6">
        <TagField
          label="论文关键词"
          hint="按 Enter 添加，支持粘贴多个词（逗号/分号分隔）"
          tags={keywords}
          onChange={onKeywordsChange}
          placeholder="例如：计算机视觉、深度学习"
          color="blue"
        />

        <div className="grid gap-5 border-t border-slate-100 pt-5 sm:grid-cols-2">
          <TagField
            label="排除机构"
            hint="避免利益冲突"
            tags={excludeOrgs}
            onChange={onExcludeOrgsChange}
            placeholder="例如：清华大学"
            color="red"
          />
          <TagField
            label="排除姓名"
            hint="作者、合作者或已邀请者"
            tags={excludeNames}
            onChange={onExcludeNamesChange}
            placeholder="例如：张三"
            color="red"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-5">
          <label className="flex cursor-pointer items-center gap-2.5 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={hasEmail}
              onChange={(e) => onHasEmailChange(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            仅显示有邮箱的审稿人
          </label>

          <button
            type="button"
            className="btn-primary min-w-[120px] px-6 py-2.5 shadow-sm shadow-brand-600/20"
            disabled={loading || keywords.length === 0}
            onClick={onSearch}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                检索中
              </span>
            ) : (
              "检索审稿人"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
