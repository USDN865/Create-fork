# 这个模块统一封装访问习讯云接口时使用的 HTTP 客户端。
# 主路径优先使用 curl_cffi，请求失败时再回退到系统 curl，尽量提高不同环境下的连通稳定性。
from __future__ import annotations

import os
import json
import subprocess
from typing import Any
from urllib.parse import urlencode

from curl_cffi import requests as curl_requests

from api.endpoints import EndpointDefinition
from core.models import ApiCallResult
from support.response_recorder import ResponseRecorder


class ApiClient:
    # 所有业务接口请求都通过这个对象发出。
    # 当前实现不保留长连接 Session，目的是减少连接复用把偶发 TLS 抖动持续放大的情况。
    def __init__(
        self, timeout_seconds: int, response_recorder: ResponseRecorder
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.response_recorder = response_recorder

    def request(
        self,
        endpoint: EndpointDefinition,
        stage: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiCallResult:
        # 每次请求都会先整理一份请求摘要，供原始响应记录和异常排查复用。
        request_headers = {**endpoint.headers, **(headers or {})}
        request_summary = {
            "method": endpoint.method,
            "url": endpoint.url,
            "params": params or {},
            "data": data or {},
            "headers": request_headers,
        }

        try:
            # 主请求路径会直接通过 curl_cffi 发起。
            response = curl_requests.request(
                method=endpoint.method,
                url=endpoint.url,
                headers=request_headers,
                params=params,
                data=data,
                timeout=self.timeout_seconds,
                impersonate="chrome124",
                allow_redirects=True,
            )
            raw_text = response.text
            parsed_json = None
            try:
                # 响应能够按 JSON 解析时，会同时保留结构化结果。
                parsed_json = response.json()
            except Exception:
                parsed_json = None

            # 无论响应正文能否解析成 JSON，都要把原始内容完整记录下来。
            self.response_recorder.record(
                stage=stage,
                endpoint_name=endpoint.name,
                request_summary=request_summary,
                response_payload=parsed_json,
                raw_text=raw_text,
                error_text="",
            )
            return ApiCallResult(
                endpoint_name=endpoint.name,
                http_status=response.status_code,
                raw_text=raw_text,
                json_body=parsed_json,
                error_text="",
            )
        except Exception as exc:
            # 主请求失败时优先尝试系统 curl 回退，尽量覆盖 Python 层偶发失败场景。
            fallback_result = self._request_with_curl_binary(
                endpoint,
                stage,
                request_summary,
                params,
                data,
                request_headers,
                str(exc),
            )
            if fallback_result is not None:
                return fallback_result

            error_text = str(exc)
            # 回退也无法完成时，仍然补一条失败记录，保证异常路径可追踪。
            self.response_recorder.record(
                stage=stage,
                endpoint_name=endpoint.name,
                request_summary=request_summary,
                response_payload=None,
                raw_text="",
                error_text=error_text,
            )
            return ApiCallResult(
                endpoint_name=endpoint.name,
                http_status=None,
                raw_text="",
                json_body=None,
                error_text=error_text,
            )

    def close(self) -> None:
        # 当前实现没有需要额外释放的长连接资源，这里保留统一关闭入口供主流程调用。
        return None

    def _request_with_curl_binary(
        self,
        endpoint: EndpointDefinition,
        stage: str,
        request_summary: dict[str, Any],
        params: dict[str, Any] | None,
        data: dict[str, Any] | None,
        headers: dict[str, str],
        original_error_text: str,
    ) -> ApiCallResult | None:
        # 当 Python 层请求失败时，这里会改用系统 curl 再尝试一次同样的请求。
        # Windows 和非 Windows 环境的 curl 可执行文件名不同，这里按系统类型选择。
        curl_binary = "curl.exe" if os.name == "nt" else "curl"
        url = endpoint.url
        if params:
            # 带查询参数的请求会先把 query string 拼到 URL 上，保持和主请求相同的访问目标。
            query_string = urlencode(params, doseq=True)
            connector = "&" if "?" in url else "?"
            url = f"{url}{connector}{query_string}"

        curl_args = [
            curl_binary,
            "-sS",
            "-L",
            "-X",
            endpoint.method,
            "--connect-timeout",
            str(self.timeout_seconds),
            "--max-time",
            str(self.timeout_seconds),
            url,
            "-w",
            "\n__CURL_STATUS__:%{http_code}",
        ]

        for header_name, header_value in headers.items():
            curl_args.extend(["-H", f"{header_name}: {header_value}"])

        if endpoint.method.upper() == "POST" and data:
            # POST 请求会沿用表单编码方式发送请求体。
            curl_args.extend(["--data", urlencode(data, doseq=True)])

        try:
            completed = subprocess.run(
                curl_args,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return None

        stdout_text = completed.stdout or ""
        stderr_text = completed.stderr or ""
        if "__CURL_STATUS__:" not in stdout_text:
            # 状态标记缺失时无法可靠拆分响应正文和状态码，因此直接放弃这次回退结果。
            return None

        raw_text, status_line = stdout_text.rsplit("\n__CURL_STATUS__:", 1)
        http_status = None
        try:
            http_status = int(status_line.strip())
        except ValueError:
            http_status = None

        parsed_json = None
        try:
            parsed_json = json.loads(raw_text)
        except Exception:
            parsed_json = None

        # 回退结果只有在未拿到 HTTP 状态码时，才把异常文本写入统一结果字段。
        # 只要系统 curl 已经返回状态码，后续阶段就继续按 HTTP 结果和业务结果判断成败。
        combined_error_text = f"curl_cffi 异常: {original_error_text}"
        if completed.returncode != 0 and stderr_text:
            combined_error_text = (
                f"{combined_error_text}；系统 curl 异常: {stderr_text.strip()}"
            )

        self.response_recorder.record(
            stage=stage,
            endpoint_name=f"{endpoint.name}，系统 curl 回退",
            request_summary=request_summary,
            response_payload=parsed_json,
            raw_text=raw_text,
            error_text="" if http_status else combined_error_text,
        )
        return ApiCallResult(
            endpoint_name=endpoint.name,
            http_status=http_status,
            raw_text=raw_text,
            json_body=parsed_json,
            error_text="" if http_status else combined_error_text,
        )


def format_business_error(result: ApiCallResult) -> str:
    # 这里把接口请求结果统一整理成适合直接展示的错误说明文本。
    if result.error_text:
        return f"{result.endpoint_name} 请求异常: {result.error_text}"
    if result.http_status is None:
        return f"{result.endpoint_name} 未拿到 HTTP 状态码"
    if not isinstance(result.json_body, dict):
        return f"{result.endpoint_name} 返回的不是合法 JSON 响应"
    return f"{result.endpoint_name} 返回业务码 {result.code}，消息为 {result.message}"
