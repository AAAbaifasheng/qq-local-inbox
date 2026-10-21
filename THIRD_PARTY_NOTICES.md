# 第三方组件与引用说明

本项目是独立的本地桌面工具，不是腾讯 QQ 官方产品，也不隶属于 NapCatQQ、DeepSeek、Ollama 或 LM Studio。以下说明用于标注依赖、协议与使用边界。

## NapCatQQ

- 项目：NapCatQQ
- 仓库：https://github.com/NapNeko/NapCatQQ
- 作用：第三方 QQ 协议端 / OneBot 11 实现，本项目通过本机 WebSocket 与 HTTP 与其通信。
- 许可证：上游仓库采用混合许可并带有额外使用限制；GitHub 许可证识别结果为 `Other` / `NOASSERTION`，不是标准 MIT/Apache 声明。使用、分发或二次开发前请阅读上游 `LICENSE` 与仓库说明，并遵守其授权条件。
- 本项目不包含、不修改、不重新分发 NapCatQQ 源码或二进制；NapCatQQ 需要你自行安装和登录。

## OneBot 11

- 项目：OneBot 11 协议
- 仓库：https://github.com/botuniverse/onebot-11
- 作用：消息事件与 HTTP API 的协议约定。
- 许可证：上游仓库未在 GitHub 标注标准 SPDX 许可证；使用前请阅读仓库条款。
- 本项目只实现协议客户端，不包含协议规范文本或参考实现代码。

## websocket-client

- 项目：websocket-client
- 仓库：https://github.com/websocket-client/websocket-client
- 作用：连接本机 NapCat WebSocket。
- 许可证：Apache License 2.0。
- 本项目通过 `requirements.txt` 安装该依赖，不修改其源码。

## qrcode

- 项目：qrcode
- 仓库：https://github.com/lincolnloop/python-qrcode
- 作用：把 NapCat WebUI 返回的登录内容绘制成二维码（Canvas）。
- 许可证：BSD License。
- 本项目通过 `requirements.txt` 安装该依赖，不修改其源码。

## PyInstaller（仅打包）

- 项目：PyInstaller
- 官网：https://pyinstaller.org/
- 作用：把源码打包成 Windows onefile exe；不是运行时 Python 依赖。
- 许可证：GPL 2.0-or-later，附带 bootloader exception；exe 中打包的 Python/Tcl/Tk 仍遵循各自许可证。
- 发布 exe 前请自行确认打包环境的依赖许可证与分发义务。

## Python 与 Tkinter

- 项目：Python / Tcl/Tk
- 官网：https://www.python.org/
- 作用：运行时与桌面界面。
- 许可证：Python Software Foundation License；Tcl/Tk 使用其各自许可证。
- 源码运行需要用户自行安装 Python 3.11/3.12；本项目提供的 onefile exe 会打包 Python 运行时与 Tcl/Tk，相关许可证随 exe 一并适用。

## DeepSeek API

- 服务：DeepSeek API
- 官网/文档：https://api-docs.deepseek.com/
- 作用：可选的远程 OpenAI 兼容模型服务。
- 说明：本项目不包含 DeepSeek 模型或服务端代码。启用远程 API 后，消息文本与最少上下文会发送给该服务商；费用、数据留存和使用条款以 DeepSeek 官方页面为准。

## Ollama

- 项目：Ollama
- 官网：https://ollama.com/
- 作用：可选的本机模型运行时，提供 OpenAI 兼容接口。
- 说明：本项目不包含 Ollama 或其模型；请自行安装并遵守其许可证与模型许可。

## LM Studio

- 项目：LM Studio
- 官网：https://lmstudio.ai/
- 作用：可选的本机模型桌面运行时，提供 OpenAI 兼容接口。
- 说明：本项目不包含 LM Studio 或其模型；请自行安装并遵守其许可证与模型许可。

## 超星学习通与 Tampermonkey（可选）

- 本项目不隶属于超星学习通，也不提供学习通登录、提交、签到或自动答题能力。
- 学习通接入是可选的只读桥：用户在已登录的学习通网页中运行本项目生成的油猴脚本，把作业元数据发送到本机回环服务。
- 学习通没有面向学生的公开官方 API；页面结构、接口和访问规则可能变化。自动化访问可能受平台用户协议限制，使用前请自行确认并承担相应风险。
- Tampermonkey / Violentmonkey 是第三方浏览器扩展，本项目不包含其代码，也不对其行为负责；请从官方扩展商店安装。
- `assets/chaoxing_bridge.user.js` 是本项目提供的脚本模板，不含真实账号信息；生成后的脚本包含本机接入令牌，请勿公开分享。

## 腾讯 QQ

- 本项目不提供 QQ 登录、协议逆向、消息发送、自动回复或账号管理能力。
- 本项目通过用户自行安装的 NapCatQQ 连接本机服务；QQ 账号、登录状态和消息内容由用户自行管理。
- 使用 QQ 接入需遵守腾讯 QQ 用户协议、相关规则和当地法律。第三方协议端可能带来账号风险，请自行评估。
- “QQ”及相关标识属于腾讯公司；本项目不使用腾讯官方 Logo 作为项目标识。

## 图标

`assets/icon.png` 与 `assets/icon.ico` 为本项目生成的图标，不包含第三方商标或素材。`vibe_images/` 为本地设计过程文件，不随仓库发布。

## 免责声明

本项目按“现状”提供，不提供任何明示或暗示担保。模型分类、日期推算、优先级和费用估算都可能出错；学习通作业的识别、截止时间和提交状态也可能因页面变化而失真。重要事务请以原始消息、学习通页面、学校/单位通知和服务商账单为准。因使用本项目产生的账号、数据、费用、合规或其他风险，由使用者自行承担。

如果你认为本项目遗漏了必要的第三方标注，请通过仓库 Issue 说明具体项目与链接。
