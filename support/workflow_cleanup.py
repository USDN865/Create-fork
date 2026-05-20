# 这个脚本用于在 GitHub Actions 工作流最后一步执行残留清理。
# 它会复用程序内部的清理规则，并额外删除工作流生成的临时快照文件。
from __future__ import annotations

import os
import sys
from pathlib import Path

# 工作流清理脚本固定沿用主程序默认时区和时间格式。
TIMEZONE_NAME = "Asia/Shanghai"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
# 这些快照文件只用于在日志中回显 Summary 内容，工作流结束前可以安全删除。
TEMPORARY_SNAPSHOT_FILES = {
    "workflow_summary_snapshot.md",
    "delete_old_runs_summary_snapshot.md",
}


def ensure_project_imports() -> tuple[object, object]:
    # 作为脚本直接执行时，需要先把项目根目录补进导入路径。
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from core.cleanup import cleanup_runtime_artifacts
    from support.logging_utils import RunLogger

    return cleanup_runtime_artifacts, RunLogger


def remove_snapshot_files(project_root: Path, logger: object) -> None:
    # 工作流为了打印 Summary 会生成快照文件，这里会在最后一步统一删除。
    deleted_paths: list[str] = []
    failed_paths: list[str] = []

    for file_name in TEMPORARY_SNAPSHOT_FILES:
        file_path = project_root / file_name
        if not file_path.exists():
            continue
        try:
            file_path.unlink()
            deleted_paths.append(str(file_path.resolve()))
        except OSError:
            failed_paths.append(str(file_path.resolve()))

    if deleted_paths:
        logger.info("工作流清理", "已删除以下工作流临时快照文件")
        for deleted_path in deleted_paths:
            logger.info("工作流清理", deleted_path)

    if failed_paths:
        logger.error("工作流清理", "以下工作流临时快照文件删除失败")
        for failed_path in failed_paths:
            logger.error("工作流清理", failed_path)


def main() -> int:
    # 工作流末尾的清理步骤不应吞掉前序失败，因此这里只负责尽力清理并输出结果。
    cleanup_runtime_artifacts, run_logger_class = ensure_project_imports()
    logger = run_logger_class(TIMEZONE_NAME, TIME_FORMAT)
    # 工作流步骤默认在仓库根目录执行，这里直接把当前工作目录视为项目根目录。
    project_root = Path(os.getcwd())
    cleanup_runtime_artifacts(str(project_root), logger)
    remove_snapshot_files(project_root, logger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
