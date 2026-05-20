# 这个模块单独负责生成 GitHub Actions Summary 文本。
# Summary 只渲染主流程已经整理好的结构化结果，不再自行推断业务状态或配置来源。
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.models import ExecutionSnapshot


STAGE_LABELS = {
    # 阶段键和展示名称的映射统一放在这里，保证 Summary 内外表达一致。
    "school_id": "获取学校 ID",
    "login": "账号登录",
    "initial_query": "首次签到查询",
    "sign_submit": "发起签到",
    "verify_query": "签到后验证",
    "notification": "消息推送",
}


@dataclass(slots=True)
class SummaryBlock:
    # Summary 的每个区块都统一用这个结构表达，方便单独控制行内容和空行规则。
    lines: list[str]
    # preserve_inner_spacing 为 True 时，当前区块内部会按原始行距拼接。
    preserve_inner_spacing: bool = False


def build_summary(
    snapshot: ExecutionSnapshot, layout_config: dict[str, list[str]]
) -> str:
    # Summary 最终输出为 Markdown 文本，区块顺序完全遵循配置给出的 sections。
    section_order = layout_config.get("sections", [])
    builders: dict[str, Callable[[ExecutionSnapshot], SummaryBlock | None]] = {
        # 区块键名和构造函数的映射集中在这里，便于配置层和渲染层保持一一对应。
        "headline": _headline,
        "config_sources": _config_sources,
        "result": _result,
        "recent_signs": _recent_signs,
        "timeline": _timeline,
        "workflow_info": _workflow_info,
        "error": _error,
    }

    blocks: list[SummaryBlock] = []
    for section_name in section_order:
        # 配置里出现未知区块名时会直接跳过，避免展示层配置失误影响主流程。
        builder = builders.get(section_name)
        if not builder:
            continue
        block = builder(snapshot)
        if block and block.lines:
            blocks.append(block)
    return _join_summary_blocks(blocks) + "\n"


def _headline(snapshot: ExecutionSnapshot) -> SummaryBlock:
    # 头部区块固定输出项目标题。
    return SummaryBlock(lines=["# 习讯云自动签到"])


def _status_label(status: str) -> str:
    # 阶段状态统一在这里映射成中文标签。
    return {
        "success": "成功",
        "failure": "失败",
        "exception": "异常",
        "repeated": "重复签到",
        "skipped": "未执行",
    }.get(status, status or "未执行")


def _final_status_label(status: str) -> str:
    # 最终状态标签和阶段状态标签分开维护，避免文案混用。
    return {
        "success": "签到成功",
        "failure": "签到失败",
        "exception": "签到异常",
        "repeated": "重复签到",
    }.get(status, status or "未设置")


def _result(snapshot: ExecutionSnapshot) -> SummaryBlock:
    # 运行结果区块会按固定阶段顺序展示每一段业务结果。
    lines = ["## 运行结果"]
    for stage_key in [
        "school_id",
        "login",
        "initial_query",
        "sign_submit",
        "verify_query",
        "notification",
    ]:
        lines.append(_build_stage_result_line(snapshot, stage_key))
    lines.append(f"**最终状态**：{_final_status_label(snapshot.final_status)}")
    lines.append(f"**结果说明**：{snapshot.reason or '无'}")
    return SummaryBlock(lines=lines)


def _build_stage_result_line(
    snapshot: ExecutionSnapshot, stage_key: str
) -> str:
    # 单个阶段没有结果时，会明确说明流程尚未进入该阶段。
    result = snapshot.stage_results.get(stage_key)
    stage_label = STAGE_LABELS[stage_key]
    if not result:
        return f"**{stage_label}**：业务码：未执行，未执行，说明：当前流程未进入该阶段"

    parts = [
        f"**{stage_label}**：业务码：{result.code or '未提供'}",
        _status_label(result.status),
    ]
    if result.detail:
        parts.append(f"说明：{result.detail}")
    return "，".join(parts)


def _config_sources(snapshot: ExecutionSnapshot) -> SummaryBlock | None:
    # 配置来源区块只有在主流程已经整理出来源说明时才输出。
    if not snapshot.config_sources_text:
        return None
    lines = ["## 配置读取来源"]
    lines.extend(snapshot.config_sources_text)
    return SummaryBlock(lines=lines)


def _recent_signs(snapshot: ExecutionSnapshot) -> SummaryBlock:
    # 最近签到记录区块无论成功与否都会输出，缺失时给出明确提示。
    lines = ["## 最近签到记录"]
    if snapshot.recent_sign_times:
        lines.extend(snapshot.recent_sign_times)
    else:
        lines.append("无法获取最近签到记录")
    return SummaryBlock(lines=lines)


def _timeline(snapshot: ExecutionSnapshot) -> SummaryBlock | None:
    # 阶段日志区块会直接复用原始日志行，并放进文本代码块中保留格式。
    if not snapshot.timeline:
        return None
    timeline_lines = [
        item.raw_line.rstrip()
        for item in snapshot.timeline
        if item.raw_line.strip()
    ]
    if not timeline_lines:
        return None
    return SummaryBlock(
        lines=["## 阶段日志", "```text", *timeline_lines, "```"],
        preserve_inner_spacing=True,
    )


def _workflow_info(snapshot: ExecutionSnapshot) -> SummaryBlock | None:
    # 工作流信息区块由运行环境整理结果直接构成。
    if not snapshot.workflow_info_text:
        return None
    lines = ["## 工作流信息"]
    lines.extend(snapshot.workflow_info_text)
    return SummaryBlock(lines=lines)


def _error(snapshot: ExecutionSnapshot) -> SummaryBlock | None:
    # 只有存在错误上下文时才渲染错误详情区块。
    if not any(
        [
            snapshot.error_stage,
            snapshot.error_endpoint,
            snapshot.error_file,
            snapshot.error_traceback,
        ]
    ):
        return None
    lines = ["## 错误详情"]
    if snapshot.error_stage:
        lines.append(f"出错阶段：{snapshot.error_stage}")
    if snapshot.error_endpoint:
        lines.append(f"出错接口：{snapshot.error_endpoint}")
    if snapshot.error_file:
        lines.append(f"出错文件：{snapshot.error_file}")
    if snapshot.error_line:
        lines.append(f"出错行号：{snapshot.error_line}")
    if snapshot.error_traceback:
        traceback_lines = [
            line.rstrip()
            for line in snapshot.error_traceback.splitlines()
            if line.strip()
        ]
        if traceback_lines:
            lines.extend(["```text", *traceback_lines, "```"])
            return SummaryBlock(lines=lines, preserve_inner_spacing=True)
    return SummaryBlock(lines=lines)


def _join_summary_blocks(blocks: list[SummaryBlock]) -> str:
    # 区块之间统一保留一个空区块间距，区块内部是否保留原始行距由各区块自己决定。
    rendered_blocks: list[str] = []
    for block in blocks:
        normalized_lines = [
            line.rstrip() for line in block.lines if line and line.strip()
        ]
        if not normalized_lines:
            continue
        if block.preserve_inner_spacing:
            rendered_blocks.append("\n".join(normalized_lines))
        else:
            rendered_blocks.append("\n\n".join(normalized_lines))
    return "\n\n".join(rendered_blocks).strip()
