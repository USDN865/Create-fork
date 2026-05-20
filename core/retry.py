# 这个模块统一封装接口动作和阶段动作的重试规则。
# 主流程只关心阶段顺序和成功条件，不再重复维护重试次数、日志输出和等待逻辑。
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from support.logging_utils import RunLogger


ResultType = TypeVar("ResultType")


class RetryManager:
    # 这个对象负责执行带重试的动作，并在每次尝试期间记录阶段日志。
    def __init__(
        self, attempt_limit: int, interval_seconds: int, logger: RunLogger
    ) -> None:
        self.attempt_limit = attempt_limit
        self.interval_seconds = interval_seconds
        self.logger = logger

    def execute(
        self,
        stage: str,
        action: Callable[[int], ResultType],
        should_retry: Callable[[ResultType], tuple[bool, str]],
    ) -> ResultType:
        # should_retry 返回两个值，第一个值表示是否继续重试，第二个值表示这次失败的具体原因。
        last_result: ResultType | None = None
        for attempt in range(1, self.attempt_limit + 1):
            # 每次尝试开始前先写日志，便于在控制台和 Summary 中还原执行顺序。
            self.logger.info(stage, f"开始第 {attempt} 次执行")
            result = action(attempt)
            last_result = result
            retry_needed, reason = should_retry(result)
            if not retry_needed:
                # 首次失败后如果重试成功，会额外记录成功发生在第几次尝试。
                if attempt > 1:
                    self.logger.success(stage, f"第 {attempt} 次执行成功")
                return result

            if attempt == self.attempt_limit:
                # 达到最后一次尝试后不再等待，直接把最后一次结果交给调用方处理。
                self.logger.error(
                    stage, f"已达到最大执行次数 3 次，最后失败原因: {reason}"
                )
                return result

            # 仍有剩余次数时，先记录失败原因，再按固定间隔等待下一次尝试。
            self.logger.error(
                stage,
                (
                    f"第 {attempt} 次执行失败，"
                    f"{self.interval_seconds} 秒后重试。"
                    f"失败原因: {reason}"
                ),
            )
            time.sleep(self.interval_seconds)

        return last_result  # type: ignore[return-value]
