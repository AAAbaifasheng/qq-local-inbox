# NapCatQQ 本机连接配置（Windows）

> NapCatQQ / QQ 的版本、UI 和配置项可能变化，以下给出需要实现的配置目标，不依赖固定菜单名称。优先参考 NapCat 官方文档和你当前版本的界面。
>
> NapCatQQ 是第三方项目，本项目不包含其代码，也不隶属于腾讯或 NapCatQQ。使用前请阅读上游 LICENSE、QQ 用户协议和 [第三方引用说明](../THIRD_PARTY_NOTICES.md)。完整使用流程见 [使用教程](USER_GUIDE.md)。

## 1. 检查当前 NapCat

- 确认 NapCat 已登录且好友消息事件正常。
- 优先使用官方 GitHub Releases / 官方文档，不下载来路不明的打包程序。
- 如果账号被要求进行设备验证，请在官方客户端/官方流程中操作，不要把登录票据发给他人。

官方链接：
- NapCatQQ 仓库与 Releases：https://github.com/NapNeko/NapCatQQ
- NapCatQQ Desktop：https://github.com/NapNeko/NapCatQQ-Desktop
- OneBot 11 消息事件说明：https://github.com/botuniverse/onebot-11/blob/master/event/message.md

## 2. 创建 OneBot 11 WebSocket Server

在 NapCat 的网络配置 / OneBot 11 配置中新增 **WebSocket Server**（不是反向 WebSocket）：

- 启用：是
- Host：`127.0.0.1`（仅本机）
- Port：`3001`（如端口被占用可改，但随后要同步到桌面程序）
- Access Token：建议设置高强度随机字符串；不是 NapCat WebUI 登录密码。Token 留空时程序也能连接，但任何本机进程都能访问该端口，共享电脑上不要留空。
- 消息上报：启用普通消息事件
- 若有 `reportSelfMessage`：关闭

若同一台 Windows 电脑运行 NapCat 和 QQ Local Inbox，保持监听地址在回环接口。不要使用 `0.0.0.0`，不要在路由器上做端口映射，也不要把 WebSocket 服务公开到公网。

## 3. （可选）创建 HTTP Server 供历史导入

只有需要“导入已有聊天记录”时才配置。NapCat 的 HTTP Server 与 WebSocket Server 是两套独立配置：

- 启用：是
- Host：`127.0.0.1`（仅本机）
- Port：`3000`（以实际配置为准）
- Access Token：建议设置高强度随机字符串；可以与 WS Token 不同。留空时任何本机进程都能访问该端口。

程序会向 `http://127.0.0.1:3000/<action>` 发送本机 HTTP 请求，使用到的接口：

- `get_friend_list` / `get_group_list`：读取好友/群列表
- `get_friend_msg_history` / `get_group_msg_history`：读取指定会话最近 N 条历史文本

同样不要绑定 `0.0.0.0`、不做端口映射、不暴露到公网。历史导入只读取你选择的会话，不下载图片/文件，不自动拉取。

## 4. 在 QQ Local Inbox 连接

1. 从项目根目录执行 `install.ps1`，再双击 `run.bat`。
2. 默认地址为 `ws://127.0.0.1:3001`。
3. 将 NapCat OneBot WebSocket Access Token 粘贴到 Token 输入框。Token 会用 Windows DPAPI 加密保存，程序不会把明文写进 settings.json 或数据库；之后启动可自动连接。若 NapCat 的 Token 为空，这里也可以留空。
4. 默认不接收群聊；若需要群作业/比赛通知，再手动勾选“接收群消息”。开启后实时群聊与今日同步使用同一范围；普通群聊只本地归档，只有候选/待回复文本才会交给模型。
5. 选择“本地规则”或“大模型 API”。本机模型直接使用 Ollama / LM Studio；DeepSeek 选择预设后需勾选“我知晓远程 API 会把消息文本发送给该服务商”，并填写 API Key。远程地址必须是 HTTPS。API Key 用 DPAPI 加密保存；知情确认保存在 settings.json。
6. 首次配置完成后点击“开始监听”。之后启动应用会按“启动时自动连接”设置自动连接，不需要重复输入 Token/Key；需要修改设置时先点击“停止监听”。只有连接后到达的实时事件会处理，不会自动调用历史消息接口。
7. 如需导入历史记录，点击“导入历史”，填写 HTTP 地址（默认 `http://127.0.0.1:3000`）、HTTP Access Token，选择好友/群与条数。导入的候选仍会进入待审核，必须人工确认。当前分析模式为远程 API 时，对话框会提示每条导入文本会发送给服务商。

## 5. 自动连接与今日同步

- 勾选“启动时自动连接”后，应用启动会使用 DPAPI 加密保存的 Token/Key 自动连接 NapCat；如果 NapCat 尚未启动，WebSocket 客户端会每 4 秒重连，不必重启应用。
- 勾选“启动时同步今天消息”后，应用会通过本机 HTTP 接口读取最近 50 个会话中今天有活动的文本：每会话最多 30 条、总计 300 条。
- 今日同步与实时群聊会先用本地规则预筛；普通文本只本地入库，只有候选/待回复文本才会交给当前模型（本机或远程）。这样既补齐今天的信息，又减少远程暴露与调用量。实时私聊仍逐条交给当前模型。
- 群聊降噪：只有直接 @ 你、群主/管理员或群公告要求全体成员执行、带明确截止时间的作业/报名/提交通知、比赛/竞赛公开信息才进入候选；群内普通提问、讨论、玩笑、招募/代课/家教广告只本地入库，不生成待办。
- 同一会话、同一文本、同一截止日的活跃待办会自动合并；启动时也会合并历史重复候选，已确认记录不会被删除。
- 顶部“同步今天”按钮可手动重跑；已入库的消息会直接跳过，不会重复调用模型。
- 不想自动同步时取消勾选即可；设置会在下次启动生效。

## 6. 诊断

- WebSocket 连接失败：核对 NapCat 是否启动、端口、WebSocket Server 类型和 Token。
- 401 / Unauthorized：核对 WebSocket Access Token；不要填写 NapCat WebUI Token。
- 收不到群消息：在应用里显式勾选群消息，并确认 NapCat 的事件范围。
- “地址必须为本机”：这是隐私模式的设计限制。当前版本拒绝远程 IP / 主机名。
- 默认端口改过：在桌面程序地址栏改为 `ws://127.0.0.1:你的端口`。
- 历史导入失败：确认 NapCat 已开启 HTTP Server、Host 为 `127.0.0.1`、端口与 Token 正确；HTTP Token 与 WS Token 可以不同。
- 自动连接未启动：检查状态栏提示；常见原因是未勾选远程知情确认、远程 Key 未填写、模型名为空或 WS 地址不是本机。
- 今天同步失败：确认 HTTP Server 已开启、端口/Token 正确；可先点击“同步今天”手动重试。
- 凭据失效：DPAPI 凭据与 Windows 用户绑定；更换 Windows 账户或把数据目录移到其他电脑后，需要重新输入 Key/Token。
- 历史导入返回 0 条：该会话最近 N 条可能没有文本内容（纯图片/文件会被忽略），或 NapCat 版本不提供历史接口；调整条数后再试。
- 本地模型分析失败：确认 Ollama / LM Studio 已启动、模型名称与已安装模型一致、端点是本机地址；失败的消息会用本地规则入库，不会丢失。
- 使用 DeepSeek 时提示“API 地址只允许连接本机地址”：请先勾选“我知晓远程 API 会把消息文本发送给该服务商”，再点击开始监听。
- 使用远程 API 时提示缺少 API Key：远程端点必须填写 Key；本机端点可留空。
- Token 为空时连接成功但担心安全：在 NapCat 的 WebSocket / HTTP Server 设置 Token，并在程序与导入对话框中同步填写。

注意：此程序是 OneBot 客户端连接到 NapCat 的本地 WebSocket Server，并通过本机 HTTP Server 手动导入历史记录。它不提供 QQ 登录能力，也不会发送消息。
