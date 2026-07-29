"""硬性过滤与阶段一粗筛（Python 工程层）。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from agent.types import ReviewerCandidate

_ROOT = Path(__file__).resolve().parents[1]
_SPLIT_RE = re.compile(r"[;；,，、\n]+")
_PART_SPLIT_RE = re.compile(r"[/\s·]+")

STAGE1_MIN_OVERLAP = float(os.getenv("AGENT_STAGE1_MIN_OVERLAP", "0.5"))
STAGE1_MAX_SELECTED = int(os.getenv("AGENT_STAGE1_MAX_SELECTED", "25"))
# 多词聚合：最佳命中权重 + 均值权重（需和为 1）
_OVERLAP_MAX_WEIGHT = float(os.getenv("AGENT_OVERLAP_MAX_WEIGHT", "0.6"))
_OVERLAP_MEAN_WEIGHT = 1.0 - _OVERLAP_MAX_WEIGHT

# 阶段一入选敏感过滤（军事/国防相关，避免后续 LLM 内容审核失败）
_SENSITIVE_FILTER_ENABLED = os.getenv("AGENT_STAGE1_SENSITIVE_FILTER", "1").strip() not in (
    "0",
    "false",
    "False",
)

# 黑名单配置：默认 config/stage1_blacklist.json，可用环境变量覆盖路径
_DEFAULT_BLACKLIST_PATH = _ROOT / "config" / "stage1_blacklist.json"
_blacklist_cache: Dict[str, Any] | None = None
_blacklist_mtime: float | None = None

def _blacklist_path() -> Path:
    custom = os.getenv("AGENT_STAGE1_BLACKLIST_PATH", "").strip()
    return Path(custom) if custom else _DEFAULT_BLACKLIST_PATH


def _norm_person(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def load_stage1_blacklist(*, force: bool = False) -> Dict[str, Any]:
    """读取阶段一黑名单配置（按文件 mtime 自动热更新）。"""
    global _blacklist_cache, _blacklist_mtime
    path = _blacklist_path()
    try:
        mtime = path.stat().st_mtime if path.is_file() else None
    except OSError:
        mtime = None

    if (
        not force
        and _blacklist_cache is not None
        and _blacklist_mtime == mtime
    ):
        return _blacklist_cache

    empty: Dict[str, Any] = {
        "names": set(),
        "emails": set(),
        "candidate_ids": set(),
        "name_orgs": set(),
    }
    if mtime is None:
        _blacklist_cache = empty
        _blacklist_mtime = None
        return empty

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _blacklist_cache = empty
        _blacklist_mtime = mtime
        return empty

    names = {
        _norm_person(x)
        for x in (raw.get("names") or [])
        if str(x).strip()
    }
    emails = {
        _norm_person(x)
        for x in (raw.get("emails") or [])
        if str(x).strip()
    }
    candidate_ids = {
        str(x).strip()
        for x in (raw.get("candidate_ids") or [])
        if str(x).strip()
    }
    name_orgs: Set[Tuple[str, str]] = set()
    for item in raw.get("name_orgs") or []:
        if not isinstance(item, dict):
            continue
        name = _norm_person(item.get("name") or "")
        org = _normalize_org(str(item.get("org") or ""))
        if name and org:
            name_orgs.add((name, org))

    parsed = {
        "names": names,
        "emails": emails,
        "candidate_ids": candidate_ids,
        "name_orgs": name_orgs,
    }
    _blacklist_cache = parsed
    _blacklist_mtime = mtime
    return parsed


def blacklist_hit_reason(candidate: ReviewerCandidate) -> str:
    """命中黑名单时返回原因标签，否则空串。"""
    bl = load_stage1_blacklist()
    name = _norm_person(candidate.name)
    if name and name in bl["names"]:
        return f"blacklist:name:{candidate.name}"
    email = _norm_person(candidate.email)
    if email and email in bl["emails"]:
        return f"blacklist:email:{candidate.email}"
    cid = str(candidate.id or "").strip()
    if cid and cid in bl["candidate_ids"]:
        return f"blacklist:id:{cid}"
    org = _normalize_org(candidate.org)
    if name and org and (name, org) in bl["name_orgs"]:
        return f"blacklist:name_org:{candidate.name}|{candidate.org}"
    return ""


def is_blacklisted_candidate(candidate: ReviewerCandidate) -> bool:
    return bool(blacklist_hit_reason(candidate))


# 命中机构名、学科、研究方向、简历等任一字段即视为敏感（子串匹配）
_SENSITIVE_MARKERS: Tuple[str, ...] = (
    "解放军",
    "人民解放军",
    "陆军",
    "海军",
    "空军",
    "火箭军",
    "武警",
    "军事",
    "军工",
    "军械",
    "军区",
    "战区",
    "作战",
    "战场",
    "战法",
    "武器",
    "兵器",
    "导弹",
    "弹药",
    "装甲兵",
    "国防大学",
    "国防科技大学",
    "国防科大",
    "国防科技",
    "军事科学",
    "军事医学",
    "军医大学",
    "装备学院",
    "指挥学院",
    "装甲兵学院",
    "无人装备",
    "特种作战",
    "火力打击",
    "侦察监视",
    "涉密",
    "保密资格",
    "核潜艇",
    "战斗机",
    "轰炸机",
    "武装警察",
    "military",
    "warfare",
    "weapon",
    "missile",
)

# 分层计分
_EXACT_SCORE = 1.0
_SUBSTRING_SCORE = 0.7
_MIN_SUBSTRING_LEN = 2
_MIN_SUBSTRING_COVERAGE = 0.5  # 较短词长度 / 较长词长度，抑制「同步」命中「自适应同步」
_MIN_BIGRAM_TOKEN_LEN = 3  # bigram 软匹配要求两侧都足够长
_BIGRAM_FLOOR = 0.2
_BIGRAM_SCORE_MIN = 0.3
_BIGRAM_SCORE_MAX = 0.65


def parse_keywords(text: str) -> List[str]:
    return [p.strip().lower() for p in _SPLIT_RE.split(text.strip()) if p.strip()]


def _normalize_org(org: str) -> str:
    return re.sub(r"\s+", "", org.strip().lower())


def is_coi_conflict(candidate_org: str, author_org: str) -> bool:
    """机构熔断：同一单位或上下级学院视为利益冲突。"""
    if not author_org.strip() or not candidate_org.strip():
        return False

    left = _normalize_org(author_org)
    right = _normalize_org(candidate_org)
    if not left or not right:
        return False

    return left in right or right in left


def filter_coi(
    candidates: Sequence[ReviewerCandidate],
    author_org: str,
) -> List[ReviewerCandidate]:
    if not author_org.strip():
        return list(candidates)
    return [c for c in candidates if not is_coi_conflict(c.org, author_org)]


def _candidate_sensitive_text(candidate: ReviewerCandidate) -> str:
    parts = [
        candidate.org,
        candidate.subject,
        candidate.position,
        candidate.resume,
        " ".join(candidate.research_keywords or []),
    ]
    return " ".join(str(p) for p in parts if p).lower()


def is_sensitive_candidate(candidate: ReviewerCandidate) -> bool:
    """黑名单或军事/国防等敏感画像：命中则判定为敏感，阶段一入选时剔除。"""
    if is_blacklisted_candidate(candidate):
        return True
    if not _SENSITIVE_FILTER_ENABLED:
        return False
    text = _candidate_sensitive_text(candidate)
    if not text.strip():
        return False
    return any(marker.lower() in text for marker in _SENSITIVE_MARKERS)


def sensitive_hit_marker(candidate: ReviewerCandidate) -> str:
    """返回命中的第一个敏感/黑名单标记（调试/展示用）。"""
    bl_reason = blacklist_hit_reason(candidate)
    if bl_reason:
        return bl_reason
    text = _candidate_sensitive_text(candidate)
    for marker in _SENSITIVE_MARKERS:
        if marker.lower() in text:
            return marker
    return ""


def filter_sensitive(
    candidates: Sequence[ReviewerCandidate],
) -> Tuple[List[ReviewerCandidate], List[ReviewerCandidate]]:
    """拆成（非敏感, 敏感）两份，保持原顺序。"""
    kept: List[ReviewerCandidate] = []
    dropped: List[ReviewerCandidate] = []
    for candidate in candidates:
        if is_sensitive_candidate(candidate):
            dropped.append(candidate)
        else:
            kept.append(candidate)
    return kept, dropped


def _expand_tokens(tokens: Iterable[str]) -> set[str]:
    """保留整词，并按 /、空格、· 拆出长度≥2 的片段。"""
    expanded: set[str] = set()
    for token in tokens:
        token = token.strip().lower()
        if not token:
            continue
        expanded.add(token)
        for part in _PART_SPLIT_RE.split(token):
            if len(part) >= 2:
                expanded.add(part)
    return expanded


def _keyword_terms(keywords: Sequence[str]) -> List[str]:
    """有序去重的关键词列表（含 / 等分隔的片段）。"""
    terms: List[str] = []
    seen: set[str] = set()
    for token in keywords:
        token = str(token).strip().lower()
        if not token:
            continue
        parts = [token, *_PART_SPLIT_RE.split(token)]
        for part in parts:
            part = part.strip()
            if len(part) < 2 or part in seen:
                continue
            seen.add(part)
            terms.append(part)
    return terms


def _char_bigrams(text: str) -> set[str]:
    t = text.strip().lower()
    if not t:
        return set()
    if len(t) < 2:
        return {t}
    return {t[i : i + 2] for i in range(len(t) - 1)}


def _bigram_jaccard(left: str, right: str) -> float:
    a = _char_bigrams(left)
    b = _char_bigrams(right)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


def _bigram_soft_score(jaccard: float) -> float:
    if jaccard < _BIGRAM_FLOOR:
        return 0.0
    # 将 [floor, 1] 线性映射到 [BIGRAM_SCORE_MIN, BIGRAM_SCORE_MAX]
    span = 1.0 - _BIGRAM_FLOOR
    ratio = (jaccard - _BIGRAM_FLOOR) / span if span > 0 else 0.0
    return _BIGRAM_SCORE_MIN + (_BIGRAM_SCORE_MAX - _BIGRAM_SCORE_MIN) * ratio


def token_pair_score(paper_token: str, reviewer_token: str) -> float:
    """单个论文词 vs 单个审稿人词的分层相似度。"""
    pt = paper_token.strip().lower()
    rt = reviewer_token.strip().lower()
    if not pt or not rt:
        return 0.0
    if pt == rt:
        return _EXACT_SCORE

    shorter, longer = (pt, rt) if len(pt) <= len(rt) else (rt, pt)
    coverage = len(shorter) / len(longer) if longer else 0.0
    if (
        len(shorter) >= _MIN_SUBSTRING_LEN
        and coverage >= _MIN_SUBSTRING_COVERAGE
        and shorter in longer
    ):
        return _SUBSTRING_SCORE

    # 两侧都够长才做 bigram，避免双字短词靠局部字面重合刷分
    if len(pt) >= _MIN_BIGRAM_TOKEN_LEN and len(rt) >= _MIN_BIGRAM_TOKEN_LEN:
        return _bigram_soft_score(_bigram_jaccard(pt, rt))
    return 0.0


def aggregate_term_scores(scores: Sequence[float]) -> float:
    """将各论文词的最佳命中分聚合成总重合度。

    ``0.6 * max + 0.4 * mean``：
    - 只精确命中 1/2 词 → 0.80（不再 soft-OR 拉满 1.0）
    - 一词精确 + 一词子串 → ~0.94
    - 两词都精确 → 1.0
    - 三词只命中专有词 → ~0.73（仍高于入选阈值，不被均值拖死）
    """
    if not scores:
        return 0.0
    clamped = [max(0.0, min(1.0, float(score))) for score in scores]
    max_s = max(clamped)
    mean_s = sum(clamped) / len(clamped)
    return _OVERLAP_MAX_WEIGHT * max_s + _OVERLAP_MEAN_WEIGHT * mean_s


def keyword_overlap_score(
    paper_keywords: Sequence[str],
    paper_title: str,
    reviewer_keywords: Sequence[str],
) -> float:
    """
    论文关键词 vs 审稿人研究方向的精细重合度。

    对每个论文词取与审稿人词的最大分层分，再按「最佳命中 + 整体覆盖」聚合：
    - 精确相等 → 1.0
    - 互为子串，且较短词长度占比 ≥ 0.5 → 0.7
      （「自适应」可命中「自适应同步」，「同步」不能）
    - 两侧词长 ≥ 3 且字 bigram Jaccard ≥ 0.2 → 映射到 0.30–0.65
    - 聚合：``0.6 * max(s_i) + 0.4 * mean(s_i)``，避免单点 1.0 或均值过低
    """
    paper_terms = _keyword_terms(paper_keywords)
    title_lower = paper_title.strip().lower()
    if title_lower:
        for kw in paper_keywords:
            kw = str(kw).strip().lower()
            if kw and kw in title_lower and kw not in paper_terms:
                paper_terms.append(kw)

    reviewer_terms = list(_expand_tokens(reviewer_keywords))
    if not paper_terms or not reviewer_terms:
        return 0.0

    scores: List[float] = []
    for pt in paper_terms:
        best = max(token_pair_score(pt, rt) for rt in reviewer_terms)
        scores.append(best)
    return aggregate_term_scores(scores)


def rank_candidates(
    candidates: Sequence[ReviewerCandidate],
    paper_keywords: Sequence[str],
    paper_title: str,
) -> List[ReviewerCandidate]:
    """关键词重合度 + H 指数加权，返回完整排序列表。"""
    if not candidates:
        return []

    max_h = max((c.hindex for c in candidates), default=0.0) or 1.0
    scored: List[tuple[float, ReviewerCandidate]] = []

    for candidate in candidates:
        overlap = keyword_overlap_score(
            paper_keywords,
            paper_title,
            candidate.research_keywords,
        )
        h_norm = candidate.hindex / max_h
        composite = overlap * 0.7 + h_norm * 0.3
        candidate.overlap_score = round(overlap, 4)
        scored.append((composite, candidate))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored]


def select_highest_overlap(
    candidates: Sequence[ReviewerCandidate],
    paper_keywords: Sequence[str],
    paper_title: str,
) -> Tuple[List[ReviewerCandidate], List[ReviewerCandidate], Dict[str, Any]]:
    """按重合度排序，overlap ≥ 阈值入选；超过上限则取综合排名前 N。

    入选时剔除敏感候选人，并从后续达标候选人中回补，尽量凑满上限。
    """
    all_ranked = rank_candidates(candidates, paper_keywords, paper_title)
    empty_meta = {
        "min_overlap": STAGE1_MIN_OVERLAP,
        "max_selected": STAGE1_MAX_SELECTED,
        "max_overlap": 0.0,
        "capped": False,
        "passed_min_overlap_count": 0,
        "sensitive_filtered_count": 0,
        "sensitive_backfilled_count": 0,
        "sensitive_names": [],
    }
    if not all_ranked:
        return [], [], empty_meta

    max_overlap = max(c.overlap_score for c in all_ranked)
    passed = [c for c in all_ranked if c.overlap_score >= STAGE1_MIN_OVERLAP]

    # 未做敏感过滤时本会入选的窗口长度，用于统计「向后回补」人数
    target_n = min(STAGE1_MAX_SELECTED, len(passed))

    selected: List[ReviewerCandidate] = []
    sensitive_dropped: List[ReviewerCandidate] = []
    for candidate in passed:
        if len(selected) >= STAGE1_MAX_SELECTED:
            break
        if is_sensitive_candidate(candidate):
            sensitive_dropped.append(candidate)
            continue
        selected.append(candidate)

    selected_keys = {(c.name, c.org) for c in selected}
    # 回补 = 入选者中落在原 Top-N 窗口之外的人数
    backfilled = sum(
        1
        for idx, candidate in enumerate(passed)
        if idx >= target_n and (candidate.name, candidate.org) in selected_keys
    )
    non_sensitive_passed = sum(1 for c in passed if not is_sensitive_candidate(c))
    capped = non_sensitive_passed > STAGE1_MAX_SELECTED

    return all_ranked, selected, {
        "min_overlap": STAGE1_MIN_OVERLAP,
        "max_selected": STAGE1_MAX_SELECTED,
        "max_overlap": max_overlap,
        "capped": capped,
        "passed_min_overlap_count": len(passed),
        "sensitive_filtered_count": len(sensitive_dropped),
        "sensitive_backfilled_count": backfilled,
        "sensitive_names": [c.name for c in sensitive_dropped[:10]],
    }
