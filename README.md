# 习讯云自动签到

<img src="./img/001.png" style="zoom:60%;" />

## 简介

这是一个为“习讯云”App 实现每日自动签到的项目，既可以在 GitHub Actions 云端运行，也可以在本地运行。程序运行后，会向手机推送签到结果。

在 GitHub Actions 云端运行时，即使电脑或手机没有网络，或者处于关机状态，程序仍然能够每天自动完成签到。

## 目前支持的功能

1. 自动获取首次签到的地址、经纬度等信息。

2. 支持自定义签到地址、经纬度等信息。

3. 根据设定的签到地址和经纬度信息自动发起签到。

4. 向手机推送签到结果。

## 推送服务

默认使用 [Bark](https://bark.day.app/#/tutorial) 推送服务。

项目采用了较多模块化设计，因此可以通过手动修改 `messaging\notifier.py` 和 `config\config.json` 中的相关代码，或将 `messaging\notifier.py` 和 `config\config.json` 中的相关代码发送给 AI 辅助修改，快速自定义为任意推送服务。

签到成功或失败时，程序会向手机推送通知；程序本身发生异常时，也会向手机推送通知；重复签到时，不会向手机推送通知。

## 使用方法

### 1. [Fork](https://github.com/NianBroken/XiXunYunAuto/fork "Fork") 本仓库

`Fork` → `Create fork`

### 2. 开启 工作流读写权限

`Settings` → `Actions` → `General` → `Workflow permissions` →`Read and write permissions` →`Save`

### 3. 添加 Secrets

`Settings` → `Secrets and variables` → `Actions` → `Secrets` → `Repository secrets` → `New repository secret` → `Add secret`

> 填写方式为：Name = Name，Secret = 例子。

> 通常情况下只需要添加以下字段，因为程序会自动获取账户首次签到时的详细地址、经纬度等信息。

> 地点名称是签到地址对应的坐标名称，因此不一定是公司名称。

> 若不需要向手机推送通知，可以不添加 `XIXUNYUN_NOTIFICATION_ENABLED` 和 `XIXUNYUN_PUSH_DEVICE_KEY`。

| Name                          | 例子                   | 说明           |
| ----------------------------- | ---------------------- | -------------- |
| XIXUNYUN_SCHOOL_NAME          | 清华大学               | 学校名称       |
| XIXUNYUN_ACCOUNT              | 2971802058             | 习讯云用户名   |
| XIXUNYUN_PASSWORD             | Y3xhaCkb5PZ4           | 习讯云密码     |
| XIXUNYUN_ADDRESS_NAME         | 中国科学院控股有限公司 | 地点名称       |
| XIXUNYUN_NOTIFICATION_ENABLED | true                   | 启用推送功能   |
| XIXUNYUN_PUSH_DEVICE_KEY      | J65KWMBfyDh3YPLpcvm8   | 推送服务 Key |

> 尚未完成首次签到时，需要添加以下字段。建议先在“习讯云”App 中完成一次手动签到，再使用上述字段，不建议优先使用下述字段。

> 经纬度的小数点后必须保留 6 位数字。

| Name                          | 例子                                         | 说明           |
| ----------------------------- | -------------------------------------------- | -------------- |
| XIXUNYUN_SCHOOL_NAME          | 清华大学                                     | 学校名称       |
| XIXUNYUN_ACCOUNT              | 2971802058                                   | 习讯云用户名   |
| XIXUNYUN_PASSWORD             | Y3xhaCkb5PZ4                                 | 习讯云密码     |
| XIXUNYUN_ADDRESS              | 北京市海淀区科学院南路2号融科资讯中心B座14层 | 详细地址       |
| XIXUNYUN_ADDRESS_NAME         | 中国科学院控股有限公司                       | 地点名称       |
| XIXUNYUN_LONGITUDE            | 123.123456                                   | 地点经度       |
| XIXUNYUN_LATITUDE             | 12.123456                                    | 地点纬度       |
| XIXUNYUN_NOTIFICATION_ENABLED | true                                         | 启用推送功能   |
| XIXUNYUN_PUSH_DEVICE_KEY      | J65KWMBfyDh3YPLpcvm8                         | 推送服务 Key |

### 4. 开启 Actions

`Actions` → `I understand my workflows, go ahead and enable them` → `XiXunYunSignin` → `Enable workflow`

### 5. 运行 程序

`Actions` → `XiXunYunSignin` → `Run workflow`

_若程序正常运行且未报错，此后程序会在每天 UTC+8 的 08:00 自动执行签到。_

_找到 `.github\workflows\main.yml`，按照注释要求设置不同的 cron，即可修改自动签到时间。_

## 许可证

`Copyright © 2026 NianBroken. All rights reserved.`

本项目采用 [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0 "Apache-2.0") 许可证。简而言之，你可以自由使用、修改和分享本项目的代码，但前提是在其衍生作品中必须保留原始许可证和版权信息，并且必须以相同的许可证发布所有修改过的代码。

## 恰饭

[Great-Firewall](https://nianbroken.github.io/Great-Firewall/) 好用的 VPN

[Ciii](https://ciii.klaio.top/) Codex 中转

[Aizex](https://aizex.klaio.top/) ChatGPT 镜像站

以上绝对都是性价比最高的。

## 其他

欢迎提交 `Issues` 和 `Pull requests`。