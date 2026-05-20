# 这个模块集中维护习讯云接口的静态定义。
# 请求方法、接口地址、默认请求头和请求体类型都只在这里声明，业务层只负责读取结果。
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EndpointDefinition:
    # 这个数据结构描述单个接口的静态元信息。
    # name 表示接口在日志、错误提示和阶段结果中的展示名称。
    name: str
    # method 表示调用当前接口时使用的 HTTP 方法。
    method: str
    # url 保存当前接口的完整访问地址。
    url: str
    # body_type 表示请求体编码方式，用来区分表单请求和无请求体请求。
    body_type: str
    # headers 保存当前接口默认附带的请求头。
    headers: dict[str, str]


MOBILE_DEFAULT_HEADERS = {
    # 这一组请求头用来模拟移动端 WebView，尽量贴近真实手机客户端的访问特征。
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 13; 22101316C Build/TQ3A.230901.001; wv) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.144 "
        "Mobile Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
}


FORM_POST_HEADERS = {
    # 表单类 POST 接口会在默认移动端请求头基础上追加内容类型和来源页信息。
    **MOBILE_DEFAULT_HEADERS,
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://api.xixunyun.com",
    "Referer": "https://api.xixunyun.com/",
}


SCHOOL_MAP_ENDPOINT = EndpointDefinition(
    # 这个接口用于根据学校名称获取学校 ID 列表。
    name="获取学校 ID 接口",
    method="GET",
    url="https://api.xixunyun.com/login/schoolmap",
    body_type="none",
    headers=MOBILE_DEFAULT_HEADERS,
)


LOGIN_ENDPOINT = EndpointDefinition(
    # 这个接口用于账号密码登录，并返回 token 和用户资料。
    name="账号登录接口",
    method="POST",
    url="https://api.xixunyun.com/login/api",
    body_type="form",
    headers=FORM_POST_HEADERS,
)


SIGN_HOME_ENDPOINT = EndpointDefinition(
    # 这个接口用于查询当前签到状态、本月签到记录和签到资源信息。
    name="签到查询接口",
    method="GET",
    url="https://api.xixunyun.com/signin40/homepage",
    body_type="none",
    headers=MOBILE_DEFAULT_HEADERS,
)


SIGN_SUBMIT_ENDPOINT = EndpointDefinition(
    # 这个接口用于提交签到请求。
    name="发起签到接口",
    method="POST",
    url="https://api.xixunyun.com/signin_rsa",
    body_type="form",
    headers=FORM_POST_HEADERS,
)


def build_login_version(current_year: int | None) -> str:
    # 登录接口要求携带 version 参数，这里统一根据年份推导对应值。
    if current_year is None:
        return "6.0.0"
    if current_year <= 2026:
        return "5.2.0"

    # 2026 年之后的版本号会按既有规则逐年递增。
    version_number = 5.2 + (current_year - 2026) * 0.5
    return f"{version_number:.1f}.0"
