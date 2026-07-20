from typing import Any, Iterable

from .reviewer_agent import ReviewerSelectionAgent, build_default_agent
from .reviewer_models import ManuscriptInput


NODE_LABELS = {
    "validate_input": "输入校验完成",
    "extract_keywords": "核心关键词提炼完成",
    "confirm_keywords": "核心关键词已确认",
    "fetch_candidates": "已从接口 2 获取候选审稿人",
    "stage1_filter": "第一阶段筛选完成",
    "fetch_articles": "已从接口 3 获取候选人发文",
    "stage2_filter": "第二阶段筛选完成",
    "generate_report": "筛选报告生成完成",
}


def main() -> None:
    print("CSCD 审稿人筛选 Agent")
    manuscript = _collect_manuscript()
    agent = build_default_agent()
    thread_id, events = agent.start(manuscript)
    interrupt_value = _consume_events(events)

    if interrupt_value:
        keywords = _confirm_keywords(interrupt_value)
        interrupt_value = _consume_events(
            agent.resume_keywords(thread_id, keywords)
        )
        if interrupt_value:
            raise RuntimeError("工作流出现未处理的额外人工中断")

    state = agent.graph.get_state(agent.config(thread_id))
    print("\n" + str(state.values.get("report", "未生成报告")))


def _collect_manuscript() -> ManuscriptInput:
    title = _required_input("论文标题：")
    abstract = _required_input("论文摘要：")
    keywords = _split_input(input("原始关键词（逗号分隔，可留空）："))
    authors = _split_input(input("作者姓名（逗号分隔，可留空）："))
    organizations = _split_input(input("作者机构（逗号分隔，可留空）："))
    return ManuscriptInput(
        title=title,
        abstract=abstract,
        keywords=keywords,
        authors=authors,
        organizations=organizations,
    )


def _consume_events(events: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    interrupt_value: dict[str, Any] | None = None
    for event in events:
        for node_name, update in event.items():
            if node_name == "__interrupt__":
                interrupts = update if isinstance(update, tuple) else (update,)
                if interrupts:
                    value = getattr(interrupts[0], "value", interrupts[0])
                    if isinstance(value, dict):
                        interrupt_value = value
                continue
            print(f"[LangGraph] {NODE_LABELS.get(node_name, node_name)}")
            if node_name == "fetch_candidates" and isinstance(update, dict):
                print(f"  候选人数：{len(update.get('candidates', []))}")
            if node_name == "stage1_filter" and isinstance(update, dict):
                print(f"  初筛人数：{len(update.get('stage1_candidates', []))}")
            if node_name == "stage2_filter" and isinstance(update, dict):
                print(f"  最终人数：{len(update.get('final_reviewers', []))}")
    return interrupt_value


def _confirm_keywords(interrupt_value: dict[str, Any]) -> list[str] | None:
    keywords = interrupt_value.get("keywords", [])
    print("\n模型提炼的核心关键词：", "、".join(keywords))
    print("提炼说明：", interrupt_value.get("reasoning", ""))
    while True:
        answer = input(
            "直接回车确认；如需修改，请输入 1–4 个逗号分隔的关键词："
        ).strip()
        if not answer:
            return None
        revised = _split_input(answer)
        if 1 <= len(revised) <= 4:
            return revised
        print("关键词数量必须为 1-4 个，请重新输入。")


def _required_input(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("该项不能为空。")


def _split_input(value: str) -> list[str]:
    normalized = value.replace("，", ",").replace("；", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


if __name__ == "__main__":
    main()
