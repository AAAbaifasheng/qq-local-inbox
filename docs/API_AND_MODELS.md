# API 接入、费用与本地模型适配

> 价格与模型信息核对时间：2026-10-19。服务商可能调整价格、模型名和计费规则，请以官方页面与账单为准。
>
> 本文中的费用是估算，不是报价。实际费用取决于消息长度、输出长度、缓存命中、峰谷时段、重试和你的账号合同。

## 1. 三种分析模式

| 模式 | 是否调用模型 | 文本是否外发 | 适用场景 |
| --- | --- | --- | --- |
| 本地规则 | 否 | 否 | 日常高频消息、先跑通流程、对隐私要求最高 |
| 本机大模型 API | 是，本机 OpenAI 兼容服务 | 只发送到本机回环地址 | 希望比规则更懂语义，又不想把聊天发给云服务 |
| 远程大模型 API | 是，HTTPS 服务商 | 发送给服务商 | 需要更强模型，且接受服务商隐私政策与费用 |

程序只允许连接回环地址上的 NapCat WebSocket/HTTP 和本机模型端点。远程 API 必须是 HTTPS，并且需要显式勾选知情确认、填写 API Key。

## 2. 应用实际发送什么

请求是 OpenAI 兼容的 `POST /v1/chat/completions`：

```json
{
  "model": "deepseek-flash",
  "temperature": 0,
  "response_format": {"type": "json_object"},
  "thinking": {"type": "disabled"},
  "max_tokens": 600,
  "messages": [
    {"role": "system", "content": "……固定分拣提示词……"},
    {"role": "user", "content": "{\"message_text\":\"明天下午三点前提交报名材料\",\"context\":{\"message_type\":\"private\",\"is_group\":false,\"sender_role\":\"\",\"at_me\":false}}"}
  ]
}
```

说明：

- `message_text` 是消息纯文本；不包含图片、文件、语音、原始事件 JSON。
- `context` 只包含消息类型、是否群聊、发送者角色、是否 @ 你；不包含群名称。
- DeepSeek 请求会关闭思考模式并限制 `max_tokens`，减少输出 token 和延迟。
- 本机 Ollama / LM Studio 请求不会带 DeepSeek 的 `thinking` 字段。
- 模型返回必须是 JSON；程序会容忍 ```json 代码块和 JSON 前后的说明文字。
- 群聊在调用模型前会先做本地规则和上下文预筛；普通讨论、提问、广告不会送模型。
- 今日同步也先本地预筛；只有候选/待回复文本调用模型。

## 3. DeepSeek 接入

### 3.1 当前模型名

DeepSeek 当前官方模型名为：

- `deepseek-flash`（DeepSeek-V4.1-Flash，日常分类首选）
- `deepseek-v4-pro`（DeepSeek-V4-Pro，复杂任务，价格更高）

旧的 `deepseek-chat` 兼容名仍可能被接受，但新配置建议直接使用 `deepseek-flash`。应用的 DeepSeek 预设会填入 `deepseek-flash`。

Endpoint：

```text
https://api.deepseek.com/v1/chat/completions
```

### 3.2 配置步骤

1. 在应用中选择“大模型 API”。
2. Endpoint 预设选择 `DeepSeek`。
3. 模型填 `deepseek-flash`。
4. 填写 API Key。
5. 勾选“我知晓远程 API 会把消息文本发送给该服务商”。
6. 点击“开始监听”。

API Key 由 Windows DPAPI 加密保存到 `secrets.dat`；`settings.json` 不保存明文 Key。

### 3.3 cURL 自测

不要把真实 Key 写进命令历史或截图。可以先用环境变量：

```bash
export DEEPSEEK_API_KEY="你的 Key"
curl "https://api.deepseek.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -d '{
    "model": "deepseek-flash",
    "temperature": 0,
    "response_format": {"type": "json_object"},
    "thinking": {"type": "disabled"},
    "max_tokens": 600,
    "messages": [
      {"role": "system", "content": "只输出 JSON。"},
      {"role": "user", "content": "{\"message_text\":\"明天交作业\"}"}
    ]
  }'
```

PowerShell 中请使用 `$env:DEEPSEEK_API_KEY`，并注意 JSON 引号转义。

## 4. DeepSeek 价格（2026-10-19 核对）

单位：人民币元 / 百万 tokens。高峰时段为北京时间周一至周五 09:00-12:00、14:00-18:00；其余时间为空闲时段。空闲价格约为高峰的一半。

| 模型 | 输入（缓存命中） | 输入（缓存未命中） | 输出 |
| --- | ---: | ---: | ---: |
| deepseek-flash 高峰 | 0.04 | 2.00 | 8.00 |
| deepseek-flash 空闲 | 0.02 | 1.00 | 4.00 |
| deepseek-v4-pro 高峰 | 0.30 | 9.00 | 27.00 |
| deepseek-v4-pro 空闲 | 0.15 | 4.50 | 13.50 |

上下文长度 1M，最大输出 384K；两者都支持 JSON Output。

### 4.1 Token 怎么估算

DeepSeek 官方给出的近似比例：

- 1 个中文字符 ≈ 0.6 token
- 1 个英文字符 ≈ 0.3 token

本应用的系统提示词较长，且每次请求都会带上；短消息的实际输入通常在数百 token。一次实测（关闭思考模式，短消息）：

- 输入：500 tokens（其中 256 命中缓存，244 未命中）
- 输出：81 tokens
- 合计：581 tokens

同一条消息开启思考模式时：

- 输入：525 tokens
- 输出：301 tokens（其中 228 是思考 token）
- 合计：826 tokens

因此，分类任务关闭思考模式可以显著减少输出费用和延迟。程序已对 DeepSeek 默认关闭思考模式。

### 4.2 单次成本公式

```text
单次成本 ≈
  缓存命中输入 tokens / 1,000,000 × 缓存命中单价
+ 缓存未命中输入 tokens / 1,000,000 × 缓存未命中单价
+ 输出 tokens / 1,000,000 × 输出单价
```

按“500 输入 token + 80 输出 token、无缓存命中”估算：

| 模型/时段 | 单次约 | 100 次/天，30 天 | 1000 次/天，30 天 |
| --- | ---: | ---: | ---: |
| flash 高峰 | ¥0.0016 | ¥4.9 | ¥49 |
| flash 空闲 | ¥0.0008 | ¥2.5 | ¥25 |
| v4-pro 高峰 | ¥0.0067 | ¥20 | ¥200 |
| v4-pro 空闲 | ¥0.0033 | ¥10 | ¥100 |

实际输入/输出会随消息长度变化。缓存命中会降低输入费用；系统提示词固定，通常能命中一部分缓存。请以 DeepSeek 控制台账单为准。

### 4.3 怎么降低消耗

1. **先用本地规则模式**：不调用模型，零 API 费用。
2. **开启群聊预筛**：普通群聊只在本地归档，不送模型。
3. **不需要群聊时关闭“接收群消息”**：范围更小，费用更低。
4. **使用 `deepseek-flash`**，不要默认使用 `deepseek-v4-pro`。
5. **保持思考模式关闭**：程序已默认关闭。
6. **在空闲时段处理大批量历史导入**：价格约为高峰的一半。
7. **不要一次性导入大量无关历史**：导入会按当前模式逐条分析。
8. **优先使用本机模型**：没有按 token 计费，但会占用本机 GPU/CPU。

应用状态栏会显示每次今日同步的“模型分析 X 条”，但不会累计 token。要查看准确用量和账单，请打开 DeepSeek 控制台的用量/账单页面。

## 5. 本地大模型推荐与适配

### 5.1 硬件与模型档位

以下是经验档位，不是硬性要求。实际速度取决于 GPU、显存带宽、量化、上下文长度和模型实现。

| 显存/硬件 | 建议模型档位 | 说明 |
| --- | --- | --- |
| 4-6GB 显存 | 3B-4B，Q4 量化 | 能跑，但语义判断和 JSON 稳定性较弱 |
| 8GB 显存 | 7B-8B，Q4_K_M | 推荐的本地最低档 |
| 12-16GB 显存 | 14B，Q4_K_M | 中文语义和分类更稳，速度中等 |
| 24GB 显存 | 32B，Q4_K_M | 本地质量最好，速度较慢 |
| 仅 CPU | 3B-4B，Q4 | 可用但慢；高消息量建议规则模式 |

量化优先选择 `Q4_K_M`；显存充足可选 Q5/Q6；不建议 Q2。分类任务的上下文通常 8K-16K 足够。

### 5.2 模型选择建议

中文事务分类优先考虑：

- Qwen2.5 系列 Instruct：7B / 14B / 32B，JSON 和中文稳定性较好，适合高频分类。
- Qwen3 系列：8B / 14B / 32B，能力更强；部分版本默认带思考模式，输出更长、更慢，建议使用非思考模式或改用 Qwen2.5。
- Gemma 3 12B / 27B：多语言能力好，适合混合中英文。
- Llama 3.1 8B：英文和通用指令能力好，中文细粒度分类不如 Qwen 系列。

不建议把推理蒸馏模型（如 DeepSeek-R1-Distill 系列）作为每条消息的默认分类器：思考 token 会增加延迟和输出长度，JSON 稳定性也可能下降。需要复杂判断时再单独使用。

模型名称会随 Ollama / LM Studio 版本变化，请以 `ollama list` 或 LM Studio 模型页显示的名称为准。

### 5.3 Ollama

1. 安装 Ollama。
2. 拉取模型，例如：

   ```bash
   ollama pull qwen3:8b
   ```

3. 确认服务在本机运行（默认 `127.0.0.1:11434`）。
4. 在应用中：

   - Endpoint 预设：`Ollama`
   - Endpoint：`http://127.0.0.1:11434/v1/chat/completions`
   - Model：`qwen3:8b`（或你实际拉取的名称）
   - API Key：留空

5. 先用“本地规则”跑通，再切换到“大模型 API”。

Ollama 的 OpenAI 兼容端点支持 `response_format` JSON 模式；如果某个版本或模型不支持，程序会尝试从返回文本中提取 JSON。

### 5.4 LM Studio

1. 安装 LM Studio，下载并加载一个 Instruct 模型。
2. 在 Developer / Local Server 页面启动服务，默认端口 1234。
3. 在应用中：

   - Endpoint 预设：`LM Studio`
   - Endpoint：`http://127.0.0.1:1234/v1/chat/completions`
   - Model：LM Studio 显示的模型标识
   - API Key：留空

4. 如果模型输出代码块或前后说明文字，程序会自动提取 JSON；仍失败时换用 JSON 模式支持更好的模型。

### 5.5 本机模型适配注意事项

- 使用 **Instruct / Chat** 模型，不要使用 Base 模型。
- 温度设为 0（程序已设置）。
- 优先选择支持 JSON / structured output 的模型或服务。
- 群聊消息量大时，本地 7B/8B 可能也会明显占用 GPU；可以先只分析私聊，或保持群聊本地规则归档。
- 本机模型端点只绑定 `127.0.0.1`，不要暴露到局域网。
- 如果模型把 JSON 包在 Markdown 代码块里，程序会去掉代码块并提取第一个 JSON 对象。
- 如果模型返回 400（例如不支持 `response_format`），请升级 Ollama/LM Studio，或换一个支持 JSON 模式的服务。
- 本机模型不会产生 API token 费用，但仍消耗电力、GPU 时间和硬件寿命。

## 6. 隐私边界

- 规则模式：聊天文本不离开本机。
- 本机模型：文本只发送到本机回环地址；但模型服务本身可能记录请求日志，请检查其配置。
- 远程模型：文本和最少上下文发送给服务商；服务商可能记录、留存或用于其政策允许的用途。
- 不发送：群名称、图片、文件、语音、原始 OneBot 事件 JSON、NapCat Token。
- API Key 使用 DPAPI 加密保存；不要把 Key 写入截图、聊天、Issue 或提交。
- 远程 API 关闭或清除凭据后，程序不会继续向该服务发送请求。

## 7. 排错

| 现象 | 检查 |
| --- | --- |
| 401 / 403 | Key 是否正确、是否过期、余额是否充足、模型是否有权限 |
| 404 / model not found | 模型名是否与官方/本地服务一致 |
| 400 response_format | 本地服务是否支持 JSON 模式；尝试升级或更换模型 |
| 返回非 JSON | 换 Instruct 模型；确认输出不是纯自然语言；程序会尝试提取 JSON |
| 本地模型很慢 | 降低模型规模、使用 Q4、检查是否在 CPU 上运行、减少上下文 |
| 费用过高 | 检查是否用 Pro、是否开启思考、是否高峰时段、是否把群聊送远程 |
| 远程地址被拒绝 | 必须是 HTTPS、需要知情确认和 Key；本机地址不要求 Key |

## 8. 官方参考

- DeepSeek 模型与价格：https://api-docs.deepseek.com/zh-cn/quick_start/pricing/
- DeepSeek Token 计算：https://api-docs.deepseek.com/zh-cn/quick_start/token_usage/
- DeepSeek Chat Completions：https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/
- Ollama OpenAI 兼容：https://docs.ollama.com/api/openai-compatibility
- Ollama 模型库：https://ollama.com/library
- LM Studio OpenAI 兼容：https://lmstudio.ai/docs/app/api/endpoints/openai
- NapCatQQ：https://github.com/NapNeko/NapCatQQ

价格、模型名和接口可能变化；部署前请再次核对官方页面。
