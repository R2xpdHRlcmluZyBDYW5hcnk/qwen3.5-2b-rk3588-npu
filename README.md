# Qwen3.5-2B on RK3588 NPU

非官方部署资料：在 8GB RK3588/RK3588S ARM64 Linux 上运行官方来源的 Qwen3.5-2B，保留视觉支持。使用 Rockchip 工具导出未量化 FP16，现成 VLM 服务提供本地 HTTP / Unix Socket 问答。

**完整教程：下载并打开 [deployment.html](deployment.html)**。HTML 的样式、配置、脚本和验证摘要全部内嵌，可离线阅读。安装和转换仍需从各原始发行方下载依赖。

- [转换与安装脚本](scripts/)；[测量和验证记录](evidence/)；[来源版本](SOURCES.md)。
- `qwen3.5-2b.service`，主进程名 `qwen3.5-2b`，DynamicUser；NPU 权限使用 render 与 video 组。
- 仅监听 `127.0.0.1:18080`，另提供 `/run/qwen3.5-2b/inference.sock`（0600）。
- 单并发、服务上下文 2048、448×448 单图输入、systemd MemoryMax=6G。
- 无状态：每个请求传完整 `messages`；请求前后清 KV，不保留服务端会话历史、不做跨请求缓存复用。
- 管理接口：`POST /v1/abort`、`POST /v1/cache/clear`；忙碌清缓存返回 409。支持 SSE，流式客户端断开会取消工作线程。

## 快速复现

先读 [第三方许可说明](THIRD_PARTY_NOTICES.md)。目标板应已有兼容 RKNPU 驱动；本次验证为 vendor 6.1.115 / RKNPU 0.9.8。脚本不更换内核。转换在 x86_64 Linux / WSL，运行在板端。

```bash
# 电脑 Linux / WSL：在本仓库根目录执行
sudo apt-get update
sudo apt-get install --no-install-recommends git curl ca-certificates libgl1 libglib2.0-0t64
export BUILD_DIR=/var/tmp/qwen3.5-2b-build
bash scripts/convert_wsl.sh
```

将 outputs 中的两个模型及 SHA256SUMS 复制到目标板 `/opt/qwen3.5-2b/models/`，将 scripts 复制到 `/var/tmp/qwen35-repro/scripts/`。完整 PowerShell 传输示例在 HTML 中，主机使用 `BOARD_HOST` 占位值。

```bash
# 目标板 root：安装及启动；先确认旧实例已停止且内存足够
bash /var/tmp/qwen35-repro/scripts/install_board.sh
curl --fail --unix-socket /run/qwen3.5-2b/inference.sock http://localhost/health
# 完成教程中的图文和中断验收后启用：
systemctl enable qwen3.5-2b.service qwen3.5-2b-socket.socket
```

## 调用

```bash
curl --fail-with-body --unix-socket /run/qwen3.5-2b/inference.sock \
  http://localhost/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"Qwen3.5-2B","messages":[{"role":"user","content":"你好，请简短介绍自己。"}],"enable_thinking":false,"max_tokens":128}'
```

图片调用、SSE、中断、清理和完全停止服务的方法见完整教程。只做问答，不提供 Agent 或工具执行能力；接口不是 gRPC。OpenAI 请求格式兼容范围及 token 估算行为以本教程说明为准。

## 思考与增量正文

调用方可显式传入 `enable_thinking:true` 与 `stream:true`。服务已支持这两个开关，无需修改服务单元或重启模型。SSE 的 `delta.content` 是正文，`delta.reasoning_content` 是私有推理频道；面向用户的客户端应丢弃后者，以证据读取、查询状态或简短依据摘要展示分析进度。

随仓库提供的 [流式文本客户端](scripts/stream_chat.py) 使用 Python 标准库和本地 Unix Socket，默认启用思考，只增量输出正文。按 Ctrl+C 会关闭当前流，沿用服务已有的断线取消；不会调用影响其他请求的全局中断接口。客户端不保存提示词、回答或会话历史。

```bash
python scripts/stream_chat.py '请简要说明如何核对一条网络连接的可见元数据。'
python -B scripts/test_stream_chat.py
```

当前固定版本的服务把非关闭的 `reasoning_effort` 值统一映射为开启思考，没有实现 low / medium 的不同强度，也没有云端 `thinking_budget` 的自动切换语义。不要把这些参数当作已经生效的原生档位。`max_tokens` 还会被服务扩展为原生生成额度，不能解释为严格的总 token 上限。上下文仍为 2048，调用方须限制输入、响应长度和整个请求的期限；较长思考可能留下较少正文空间。既有验收数据来自关闭思考的请求，不代表开启思考后的性能。

## 验证与限制

功能记录来自 2026-11-04 的一次实际部署：文本、A/B/A 图像切换、中断后继续问答、SSE 断开及错误后的清理均通过；三个 NPU 核心观测到工作；无自动重启及 cgroup OOM kill。不是生产稳定性保证，也未做长期压力测试或该模型 ONNX/NPU 数值一致性验证。

测量的原始量、可直接运行的计算代码、完整输出和结果都在 HTML 的“实测依据”章节。也可运行：

```bash
python scripts/summarize_evidence.py
```

仓库不包含模型、运行库、SDK、第三方服务端源码或样例图片，也没有私人主机地址、SSH 身份或访问令牌。来源权重是官方 BF16，经工具转换成板端 FP16；不是原始 Safetensors 直接在 NPU 运行。

## 许可

自行编写的文档、配置、脚本及新增代码采用 [MIT](LICENSE)。模型、SDK、运行库和服务端依赖各自遵循上游条款，不能由本仓库 MIT 替代。

**第三方 VLM 服务核查时未声明许可证。** 本仓库不分发它的源码或含上游代码上下文的补丁；本地修改脚本只保存新增内容与数值编辑范围，并校验版本。下载引用和本地脚本不授予上游使用、修改或再分发权限；需要这些权限时应向原作者确认。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [SOURCES.md](SOURCES.md)。本项目不代表任何上游官方发行或背书。
