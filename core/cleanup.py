# 这个模块集中处理程序结束后的缓存和临时残留清理。
# 清理范围只包含白名单里的缓存目录和临时文件，避免误删配置、源码和排查产物。
from __future__ import annotations

from pathlib import Path

from support.logging_utils import RunLogger


SAFE_DIR_NAMES = {
    # 这些目录都属于常见的运行缓存目录或工具缓存目录。
    ".ruff_cache",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

SAFE_FILE_SUFFIXES = {
    # 这些后缀表示 Python 缓存文件或临时文件。
    ".pyc",
    ".pyo",
    ".tmp",
    ".temp",
}

SAFE_FILE_NAMES = {
    # 某些白名单文件不依赖后缀判断，需要单独按文件名识别。
    "__init__",
}

EXCLUDED_PATH_PARTS = {
    # 命中这些路径片段后会整段跳过，避免清理掉仓库元数据和业务输出目录。
    "output",
    ".git",
    ".research",
}


def cleanup_runtime_artifacts(project_root: str, logger: RunLogger) -> None:
    # 从项目根目录递归扫描，只删除白名单中的缓存目录和临时文件。
    root = Path(project_root)
    deleted_paths: list[str] = []
    failed_paths: list[str] = []

    for path in root.rglob("*"):
        # 路径在扫描过程中如果被其他流程删除，直接跳过即可。
        if not path.exists():
            continue
        # 命中排除目录后，整条路径都不再参与后续清理判断。
        if any(part in EXCLUDED_PATH_PARTS for part in path.parts):
            continue

        # 白名单目录会直接走目录删除流程。
        if path.is_dir() and path.name in SAFE_DIR_NAMES:
            _delete_directory(path, deleted_paths, failed_paths)
            continue

        # 白名单文件会按后缀或文件名匹配后删除。
        if path.is_file():
            matches_safe_name = path.name in SAFE_FILE_NAMES
            matches_safe_suffix = path.suffix in SAFE_FILE_SUFFIXES
            if matches_safe_name or matches_safe_suffix:
                _delete_file(path, deleted_paths, failed_paths)

    # 清理完成后会统一输出删除结果，便于判断这次运行是否留下缓存。
    if deleted_paths:
        logger.info("清理残留", "已删除以下缓存或临时文件")
        for deleted_path in deleted_paths:
            logger.info("清理残留", deleted_path)
    else:
        logger.info("清理残留", "没有发现需要删除的缓存或临时文件")

    if failed_paths:
        logger.error("清理残留", "以下缓存或临时文件删除失败")
        for failed_path in failed_paths:
            logger.error("清理残留", failed_path)


def _delete_directory(
    path: Path, deleted_paths: list[str], failed_paths: list[str]
) -> None:
    # 目录删除按先子项后父目录的顺序执行，避免父目录因为仍有内容而删除失败。
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), reverse=True):
        try:
            if child.is_file():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                child.rmdir()
        except FileNotFoundError:
            continue
        except OSError:
            # 子项删除失败时直接停止当前目录清理，避免继续删除后留下半清理状态。
            failed_paths.append(str(child.resolve()))
            return
    try:
        path.rmdir()
        deleted_paths.append(str(path.resolve()))
    except FileNotFoundError:
        return
    except OSError:
        failed_paths.append(str(path.resolve()))


def _delete_file(
    path: Path, deleted_paths: list[str], failed_paths: list[str]
) -> None:
    # 文件删除单独走一个出口，删除策略和结果收集都集中在这里。
    if not path.exists():
        return
    try:
        path.unlink(missing_ok=True)
        deleted_paths.append(str(path.resolve()))
    except FileNotFoundError:
        return
    except OSError:
        failed_paths.append(str(path.resolve()))
