# 这个模块统一执行消息推送请求。
# 推送地址、请求方法、字段键名和字段值都从配置模板动态解析，通知请求失败时也会回退到系统 curl。
from __future__ import annotations

import json
import os
import subprocess
from typing import Any
from urllib.parse import urlencode

from curl_cffi import requests as curl_requests


def send_notification(
    request_template: dict[str, Any],
    message_variables: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    # 推送请求的 URL、请求头、查询参数和请求体字段都会在发送前统一解析。
    url = _resolve_value(request_template.get("url", ""), message_variables)
    method = str(request_template.get("method", "POST")).upper()
    body_type = str(request_template.get("body_type", "form")).lower()
    headers = _resolve_mapping(
        request_template.get("headers", {}), message_variables
    )
    query_params = _resolve_mapping(
        request_template.get("query_params", {}), message_variables
    )
    body_fields = _resolve_mapping(
        request_template.get("body_fields", {}), message_variables
    )

    request_kwargs: dict[str, Any] = {
        # 推送请求的超时时间会和主业务请求复用同一份运行配置。
        # impersonate 保持固定，避免通知模板和网络指纹配置彼此混杂。
        "method": method,
        "url": url,
        "headers": headers,
        "params": query_params,
        "timeout": timeout_seconds,
        "impersonate": "chrome124",
    }

    if body_type == "json":
        # JSON 请求体通过 json 参数发送。
        request_kwargs["json"] = body_fields
    elif body_type == "form":
        # 表单请求体通过 data 参数发送。
        request_kwargs["data"] = body_fields
    else:
        # 未识别的请求体类型统一按 data 发送，保持当前行为稳定。
        request_kwargs["data"] = body_fields

    try:
        response = curl_requests.request(**request_kwargs)
        response_text = response.text
        try:
            response_json = response.json()
        except Exception:
            response_json = None
        return {
            "http_status": response.status_code,
            "raw_text": response_text,
            "json_body": response_json,
            "resolved_request": {
                # 返回值里保留最终展开后的请求快照，供响应记录器直接复用。
                **request_kwargs,
                "body_type": body_type,
                "body_fields": body_fields,
                "timeout_seconds": timeout_seconds,
                "transport": "curl_cffi",
            },
        }
    except Exception as exc:
        return _send_notification_with_curl_binary(
            request_kwargs=request_kwargs,
            body_type=body_type,
            body_fields=body_fields,
            timeout_seconds=timeout_seconds,
            original_error_text=str(exc),
        )


def _send_notification_with_curl_binary(
    request_kwargs: dict[str, Any],
    body_type: str,
    body_fields: dict[str, str],
    timeout_seconds: int,
    original_error_text: str,
) -> dict[str, Any]:
    # Python 层通知请求失败时，这里会改用系统 curl 发送同一份通知。
    curl_binary = "curl.exe" if os.name == "nt" else "curl"
    url = str(request_kwargs.get("url", "")).strip()
    params = request_kwargs.get("params", {})
    if isinstance(params, dict) and params:
        query_string = urlencode(params, doseq=True)
        connector = "&" if "?" in url else "?"
        url = f"{url}{connector}{query_string}"

    curl_args = [
        curl_binary,
        "-sS",
        "-L",
        "-X",
        str(request_kwargs.get("method", "POST")).upper(),
        "--connect-timeout",
        str(timeout_seconds),
        "--max-time",
        str(timeout_seconds),
        url,
        "-w",
        "\n__CURL_STATUS__:%{http_code}",
    ]

    headers = request_kwargs.get("headers", {})
    if isinstance(headers, dict):
        for header_name, header_value in headers.items():
            curl_args.extend(["-H", f"{header_name}: {header_value}"])

    payload_text = ""
    if body_type == "json":
        payload_text = json.dumps(body_fields, ensure_ascii=False)
    else:
        payload_text = urlencode(body_fields, doseq=True)
    if payload_text:
        curl_args.extend(["--data", payload_text])

    try:
        completed = subprocess.run(
            curl_args,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        raise RuntimeError(
            "curl_cffi 和系统 curl 都发送失败。"
            f"curl_cffi 异常: {original_error_text}；"
            f"系统 curl 异常: {exc}"
        ) from exc

    stdout_text = completed.stdout or ""
    stderr_text = completed.stderr or ""
    if "__CURL_STATUS__:" not in stdout_text:
        raise RuntimeError(
            "系统 curl 返回结果缺少状态码标记。"
            f" curl_cffi 异常: {original_error_text}"
            f"；系统 curl 返回码: {completed.returncode}"
            f"；系统 curl 标准错误: {stderr_text.strip()}"
        )

    raw_text, status_line = stdout_text.rsplit("\n__CURL_STATUS__:", 1)
    try:
        http_status = int(status_line.strip())
    except ValueError:
        http_status = None

    response_json = None
    try:
        response_json = json.loads(raw_text)
    except Exception:
        response_json = None

    if completed.returncode != 0 and http_status is None:
        raise RuntimeError(
            f"curl_cffi 异常: {original_error_text}；"
            f"系统 curl 异常: {stderr_text.strip()}"
        )

    return {
        "http_status": http_status,
        "raw_text": raw_text,
        "json_body": response_json,
        "resolved_request": {
            # 回退路径会把 transport 和 fallback_reason 一并写回，方便区分请求实际走过哪条链路。
            **request_kwargs,
            "url": url,
            "body_type": body_type,
            "body_fields": body_fields,
            "timeout_seconds": timeout_seconds,
            "transport": "system_curl_fallback",
            "fallback_reason": original_error_text,
        },
    }


def _resolve_mapping(
    mapping: dict[str, Any], message_variables: dict[str, str]
) -> dict[str, str]:
    # 每个字段都会独立解析，允许同一份模板同时混用运行时变量和固定值。
    resolved: dict[str, str] = {}
    for key, spec in mapping.items():
        value = _resolve_value(spec, message_variables)
        if value == "":
            continue
        resolved[key] = value
    return resolved


def _resolve_value(spec: Any, message_variables: dict[str, str]) -> str:
    # source 为 message 时从消息变量中取值，其他情况按 value 优先、env_name 次之的顺序解析。
    if isinstance(spec, dict):
        source_type = str(spec.get("source", "value")).strip()
        if source_type == "message":
            variable_name = str(spec.get("variable", "")).strip()
            return str(message_variables.get(variable_name, ""))

        value = str(spec.get("value", "")).strip()
        env_name = str(spec.get("env_name", "")).strip()
        if value:
            return value
        if env_name:
            return os.getenv(env_name, "").strip()
        return ""
    return str(spec)
