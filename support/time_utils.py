# 这个模块统一维护时区获取、时间格式化和签到历史时间解析逻辑。
# 这样可以保证消息正文、控制台日志和 Summary 使用完全一致的时间规则。
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE_NAME = "Asia/Shanghai"
# 统一默认到上海时区，保证本地运行和 GitHub Actions 的日期判断基线一致。


def get_timezone(timezone_name: str) -> ZoneInfo:
    # 时区名称无效时统一回退到上海时区，保证程序仍然能够继续运行。
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE_NAME)


def now_in_timezone(timezone_name: str) -> datetime:
    # 当前时间统一通过这里获取，避免不同模块各自处理时区。
    return datetime.now(get_timezone(timezone_name))


def format_datetime(moment: datetime, time_format: str) -> str:
    # 时间字符串格式化也走统一出口，保证消息、Summary 和日志格式一致。
    return moment.strftime(time_format)


def today_text(timezone_name: str) -> str:
    # 当天日期文本统一基于配置中的时区计算。
    return now_in_timezone(timezone_name).strftime("%Y-%m-%d")


def format_unix_timestamp(
    timestamp_value: str | int | float, timezone_name: str, time_format: str
) -> str:
    # 签到接口返回的秒级时间戳会在这里统一转换为配置要求的本地时间字符串。
    timestamp_seconds = float(timestamp_value)
    local_time = datetime.fromtimestamp(
        timestamp_seconds, tz=timezone.utc
    ).astimezone(get_timezone(timezone_name))
    return format_datetime(local_time, time_format)


def parse_sign_history_items(
    sign_in_month: list[dict],
    timezone_name: str,
    time_format: str,
    limit: int = 5,
) -> list[str]:
    # 最近签到记录优先使用秒级时间戳换算时间，缺少时间戳时再回退到接口直接提供的日期文本。
    # 返回顺序和接口列表顺序保持一致，通常是最新记录在前，较旧记录在后。
    recent_items: list[str] = []
    for item in sign_in_month[:limit]:
        sign_timestamp = item.get("sign_time")
        sign_time_text = str(item.get("sign_time_text", "")).strip()
        if sign_timestamp not in (None, ""):
            try:
                # 时间戳能够解析时，直接采用本地化后的完整日期时间。
                recent_items.append(
                    format_unix_timestamp(
                        sign_timestamp, timezone_name, time_format
                    )
                )
                continue
            except Exception:
                pass
        if sign_time_text:
            # 只有日期没有时分秒时，统一补零点时间，保持展示格式一致。
            if len(sign_time_text) == 10:
                recent_items.append(f"{sign_time_text} 00:00:00")
            else:
                recent_items.append(sign_time_text)
        else:
            # 两种时间来源都缺失时，会显式标记这条记录缺少时间信息。
            recent_items.append("签到记录时间缺失")
    return recent_items
