# 这个模块统一生成消息推送的标题和正文。
# 主流程只提供结构化快照数据，正文固定整理为四个部分。
from __future__ import annotations

from collections.abc import Callable

from core.models import ExecutionSnapshot


DEFAULT_TITLES = {
    # 不同最终状态对应的默认标题统一在这里维护。
    "success": "习讯云签到成功",
    "failure": "习讯云签到失败",
    "exception": "习讯云签到异常",
    "repeated": "习讯云重复签到",
}

DEFAULT_LAYOUTS = {
    # 这里给出四种结果状态各自的默认四段正文顺序。
    "success_sections": [
        "overview",
        "recent_signs",
        "profile",
        "delivery",
    ],
    "failure_sections": [
        "overview",
        "recent_signs",
        "profile",
        "delivery",
    ],
    "exception_sections": [
        "overview",
        "recent_signs",
        "profile",
        "delivery",
    ],
    "repeated_sections": [
        "overview",
        "recent_signs",
        "profile",
        "delivery",
    ],
}

LAYOUT_KEY_BY_STATUS = {
    # 最终状态和配置中的区块数组名称映射集中在这里维护。
    "success": "success_sections",
    "failure": "failure_sections",
    "exception": "exception_sections",
    "repeated": "repeated_sections",
}


def build_message(
    snapshot: ExecutionSnapshot, layout_config: dict[str, list[str]]
) -> dict[str, str]:
    # 标题按最终状态选取，正文按固定四段结构生成。
    title = snapshot.final_title or DEFAULT_TITLES.get(
        snapshot.final_status, "习讯云签到异常"
    )
    body = _compose_body(snapshot, layout_config)
    return {
        "title": title,
        "current_time": snapshot.current_time_text,
        "body": body,
    }


def _compose_body(
    snapshot: ExecutionSnapshot, layout_config: dict[str, list[str]]
) -> str:
    # 正文始终整理为四个部分，旧配置里的区块名会自动回退到默认顺序。
    layout_key = LAYOUT_KEY_BY_STATUS.get(
        snapshot.final_status, "exception_sections"
    )
    section_order = _resolve_section_order(layout_key, layout_config)
    builders: dict[str, Callable[[ExecutionSnapshot], str]] = {
        # 四个区块名和实际构造函数的对应关系只在这里维护。
        "overview": _build_overview_section,
        "recent_signs": _build_recent_signs_section,
        "profile": _build_profile_section,
        "delivery": _build_delivery_section,
    }

    sections: list[str] = []
    for section_name in section_order:
        builder = builders.get(section_name)
        if not builder:
            continue
        section_text = builder(snapshot)
        if section_text:
            sections.append(section_text)

    if sections:
        return "\n\n".join(sections).strip()

    # 四个部分都没有可展示内容时，正文仍然会至少保留一个可读结果。
    fallback_section = _build_overview_section(snapshot)
    if fallback_section:
        return fallback_section

    fallback_section = _build_recent_signs_section(snapshot)
    if fallback_section:
        return fallback_section

    fallback_section = _build_profile_section(snapshot)
    if fallback_section:
        return fallback_section

    fallback_section = _build_delivery_section(snapshot)
    if fallback_section:
        return fallback_section

    return "当前没有可展示的消息内容"


def _resolve_section_order(
    layout_key: str, layout_config: dict[str, list[str]]
) -> list[str]:
    # 只有显式提供四个新部分且不重复时，才按配置顺序展示，否则回退到默认顺序。
    configured_order = layout_config.get(layout_key, [])
    if not isinstance(configured_order, list):
        return DEFAULT_LAYOUTS[layout_key]

    normalized_order: list[str] = []
    valid_section_names = set(DEFAULT_LAYOUTS[layout_key])
    for section_name in configured_order:
        normalized_name = _normalize_text(section_name)
        is_valid_section = normalized_name in valid_section_names
        is_new_section = normalized_name not in normalized_order
        if is_valid_section and is_new_section:
            normalized_order.append(normalized_name)

    if len(normalized_order) == len(valid_section_names):
        return normalized_order
    # 任意一个区块缺失、重名或写错时，正文顺序统一回退到默认布局。
    return DEFAULT_LAYOUTS[layout_key]


def _build_overview_section(snapshot: ExecutionSnapshot) -> str:
    # 第一部分固定展示积分摘要、结果标签和接口结果，失败与异常时会继续补充原因和错误定位信息。
    lines: list[str] = []
    _extend_section_lines(lines, _build_score_summary_section(snapshot))
    _extend_section_lines(lines, _build_status_section(snapshot))
    if snapshot.final_status in {"failure", "exception"}:
        _extend_section_lines(lines, _build_reason_section(snapshot))
    if snapshot.final_status == "exception":
        _extend_section_lines(lines, _build_stage_section(snapshot))
        _extend_section_lines(lines, _build_error_location_section(snapshot))
        _extend_section_lines(lines, _build_context_section(snapshot))
    return "\n".join(lines).strip()


def _build_score_summary_section(snapshot: ExecutionSnapshot) -> str:
    # 积分和签到统计会集中放在同一个结果摘要区块里。
    lines: list[str] = []
    score_summary = _build_score_summary_line(snapshot)
    if score_summary:
        lines.append(score_summary)
    _append_combined_line(
        lines,
        [("当前积分", snapshot.point), ("积分排名", snapshot.point_rank)],
    )
    return "\n".join(lines).strip()


def _build_recent_signs_section(snapshot: ExecutionSnapshot) -> str:
    # 最近签到记录最多展示快照里已经整理好的几条时间文本。
    if not snapshot.recent_sign_times:
        return "无法获取本月最近签到记录"
    count = len(snapshot.recent_sign_times)
    lines = ["本月最近" + str(count) + "次签到时间："]
    lines.extend(
        _normalize_text(item)
        for item in snapshot.recent_sign_times
        if _normalize_text(item)
    )
    return "\n".join(lines).strip()


def _build_profile_section(snapshot: ExecutionSnapshot) -> str:
    # 用户信息区块只展示当前快照中已经成功拿到的资料字段。
    lines: list[str] = []
    _append_combined_line(
        lines, [("用户ID", snapshot.user_id), ("学号", snapshot.user_number)]
    )
    _append_combined_line(
        lines, [("姓名", snapshot.user_name), ("班级", snapshot.class_name)]
    )
    _append_combined_line(
        lines,
        [
            ("入学年份", snapshot.entrance_year),
            ("毕业年份", snapshot.graduation_year),
        ],
    )
    return "\n".join(lines).strip()


def _build_delivery_section(snapshot: ExecutionSnapshot) -> str:
    # 第四部分固定展示消息来源和强制推送状态。
    lines: list[str] = []
    _extend_section_lines(lines, _build_source_section(snapshot))
    _extend_section_lines(lines, _build_force_push_section(snapshot))
    return "\n".join(lines).strip()


def _build_force_push_section(snapshot: ExecutionSnapshot) -> str:
    # 强制推送区块只展示当前这次消息是否由强制推送触发。
    return _build_force_push_line(snapshot)


def _build_source_section(snapshot: ExecutionSnapshot) -> str:
    # 来源区块只负责说明这条消息来自哪个运行环境。
    lines: list[str] = []
    _append_labeled_line(lines, "消息推送来源", snapshot.environment_label)
    return "\n".join(lines).strip()


def _build_status_section(snapshot: ExecutionSnapshot) -> str:
    # 状态区块集中展示最终结果标签和接口结果说明。
    lines: list[str] = []
    result_label = _get_result_label(snapshot)
    if result_label:
        lines.append(result_label)
    _append_labeled_line(lines, "发起签到接口业务码", snapshot.sign_api_code)
    _append_labeled_line(lines, "发起签到接口消息", snapshot.sign_api_message)
    _append_labeled_line(
        lines,
        "签到查询接口消息",
        snapshot.verify_query_message or snapshot.initial_query_message,
    )
    return "\n".join(lines).strip()


def _build_reason_section(snapshot: ExecutionSnapshot) -> str:
    # 原因说明只在快照里存在有效文本时才输出。
    reason_text = _normalize_text(snapshot.reason)
    if reason_text:
        return f"原因说明：{reason_text}"
    return ""


def _build_stage_section(snapshot: ExecutionSnapshot) -> str:
    # 出错阶段和出错接口会放在同一个区块中，便于快速定位异常位置。
    lines: list[str] = []
    _append_labeled_line(lines, "出错阶段", snapshot.error_stage)
    _append_labeled_line(lines, "出错接口", snapshot.error_endpoint)
    return "\n".join(lines).strip()


def _build_error_location_section(snapshot: ExecutionSnapshot) -> str:
    # 出错文件和出错行号会集中展示，方便直接跳到对应位置排查。
    lines: list[str] = []
    _append_labeled_line(lines, "出错文件", snapshot.error_file)
    _append_labeled_line(lines, "出错行号", snapshot.error_line)
    return "\n".join(lines).strip()


def _build_context_section(snapshot: ExecutionSnapshot) -> str:
    # 异常上下文优先展示已经整理好的上下文行，缺失时再展示堆栈文本。
    lines = [
        _normalize_text(item)
        for item in snapshot.context_lines
        if _normalize_text(item)
    ]
    if not lines and snapshot.error_traceback:
        lines = [
            _normalize_text(line)
            for line in snapshot.error_traceback.splitlines()
            if _normalize_text(line)
        ]
    return "\n".join(lines).strip()


def _build_score_summary_line(snapshot: ExecutionSnapshot) -> str:
    # 积分摘要会把本次积分、本月签到天数和连续签到天数压缩到同一行展示。
    parts = _collect_value_parts(
        [
            ("本次签到获得 {value} 积分", snapshot.sign_point),
            ("本月签到 {value} 天", snapshot.sign_in_month_count),
            ("连续签到 {value} 天", snapshot.continuous_sign_in),
        ]
    )
    return "，".join(parts).strip()


def _get_result_label(snapshot: ExecutionSnapshot) -> str:
    # 最终状态标签统一在这里映射成可直接展示的中文文本。
    labels = {
        "success": "本次结果：签到成功",
        "failure": "本次结果：签到失败",
        "exception": "本次结果：签到异常",
        "repeated": "本次结果：重复签到",
    }
    return labels.get(snapshot.final_status, "本次结果：签到异常")


def _build_force_push_line(snapshot: ExecutionSnapshot) -> str:
    # 强制推送状态固定输出为完整句子，避免正文里出现空白。
    if snapshot.force_push_active:
        return "本次消息为强制推送"
    return "本次消息不是强制推送"


def _normalize_text(value: object) -> str:
    # 所有进入正文的值都会先在这里做空值和空白清理。
    if value is None:
        return ""
    return str(value).strip()


def _append_labeled_line(lines: list[str], label: str, value: object) -> None:
    # 只有值非空时才追加带标签的单行文本，避免正文出现空标签。
    text = _normalize_text(value)
    if text:
        lines.append(f"{label}：{text}")


def _extend_section_lines(lines: list[str], section_text: str) -> None:
    # 复合区块会把已有子区块按行拆开追加，保证区块内部没有空行。
    for line in section_text.splitlines():
        normalized_line = _normalize_text(line)
        if normalized_line:
            lines.append(normalized_line)


def _collect_value_parts(patterns: list[tuple[str, object]]) -> list[str]:
    # 模板片段只有在值非空时才参与结果行拼接。
    parts: list[str] = []
    for pattern, value in patterns:
        text = _normalize_text(value)
        if text:
            parts.append(pattern.format(value=text))
    return parts


def _append_combined_line(
    lines: list[str], field_pairs: list[tuple[str, object]]
) -> None:
    # 同一语义层级的字段会合并到一行，并用中文逗号连接。
    parts = [
        f"{label}：{text}"
        for label, value in field_pairs
        if (text := _normalize_text(value))
    ]
    if parts:
        lines.append("，".join(parts))
