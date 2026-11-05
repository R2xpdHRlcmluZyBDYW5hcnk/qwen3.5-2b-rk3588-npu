# 来源与版本记录

查询日期：2026-11-04，时区 UTC+08:00。所有结论限于固定版本和列明的实测条件。

## 模型与工具

- Qwen 官方模型：[Qwen/Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B/tree/15852e8c16360a2fea060d615a32b45270f8a8fc)。固定 revision `15852e8c16360a2fea060d615a32b45270f8a8fc`，模型元数据声明 Apache-2.0。来源权重及许可证由使用者从官方仓库获取，本仓库不分发权重。
- 语言转换及运行时：[airockchip/rknn-llm](https://github.com/airockchip/rknn-llm/tree/f7390530443bf84f0394255a449d7cbe81e69d1c)，release-v1.3.1；其 [LICENSE](https://github.com/airockchip/rknn-llm/blob/f7390530443bf84f0394255a449d7cbe81e69d1c/LICENSE) 及所含第三方条款继续适用。
- 视觉编译及运行时：[airockchip/rknn-toolkit2](https://github.com/airockchip/rknn-toolkit2/tree/2c723177a94fac65cbc036d722907ddbc91980cf)，v2.5.0；适用 [RKNN SDK License](https://github.com/airockchip/rknn-toolkit2/blob/2c723177a94fac65cbc036d722907ddbc91980cf/LICENSE)，不能以本仓库 MIT 许可证替代。
- VLM 服务：[Hanzo-Huang/rkllm-docker](https://github.com/Hanzo-Huang/rkllm-docker/tree/ad016395d68e4fa789e139567b92c2320ba02249)，固定 commit `ad016395d68e4fa789e139567b92c2320ba02249`。这是第三方个人测试项目，不是 Qwen 或 Rockchip 的官方服务端发行版。
- Python 环境工具：[uv 0.13.7](https://github.com/astral-sh/uv/releases/tag/0.13.7)。下载由脚本校验 SHA-256，本仓库不分发工具二进制。

## 查询条件与结果

1. 通过 MCP search_service 检查官方模型配置、RKLLM CHANGELOG 和 benchmark：确认 Qwen3.5 是视觉语言模型，RKLLM 已添加支持。官方量化 benchmark 不用于推导本教程 FP16 的性能或内存。
2. 通过 Hugging Face 官方 API 检查模型文件清单与固定提交，下载后核验原权重 SHA-256：`aa33250c4fc64891ddfaba3a314fd9542ea371843c387178b425fbcc5ed680b1`。
3. 通过实际 Toolkit 构建与板端测试核实未量化路径：`do_quantization=False`，运行时日志为 FP16；这不是将原始 BF16 Safetensors 文件直接交给 NPU。视觉模型同样未量化。
4. 通过 `gh repo view --json licenseInfo` 和 `gh api repos/.../contents` 检查服务端仓库许可证：API 返回 `licenseInfo: null`，根目录没有 LICENSE；固定版本源码也没有许可证声明。不能推断它采用 MIT 或其他开源许可。
5. 通过 `gh api repos/airockchip/.../contents/LICENSE?ref=...` 检查上述固定 SDK 版本的许可证。RKLLM 的许可证包含再分发条件及第三方声明；RKNN 使用专门 SDK 协议。

## 思考与流式参数补查

2026-11-05，MCP Search Service。查询前复用上述固定版本与接口记录，补读 [Qwen3.5-2B 模型卡](https://huggingface.co/Qwen/Qwen3.5-2B/blob/15852e8c16360a2fea060d615a32b45270f8a8fc/README.md)、[阿里云 Chat Completions 参数](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions) 与 [深度思考说明](https://www.alibabacloud.com/help/en/model-studio/deep-thinking)。查询条件为 enable_thinking、reasoning_effort、thinking_budget、流式 reasoning_content / content 及模型支持范围。结果：2B 模型支持显式启用思考；云端档位和预算的适用范围不能直接套用到本地 RKLLM。

本地核对 `apply_local_changes.py` 结果散列对应的服务源码。enable_thinking 为布尔开关，非关闭的 reasoning_effort 统一进入思考模式，没有档位差异或 thinking_budget。SSE 分开输出私有推理与正文，Qwen 的 max_tokens 会扩展为原生生成额度。补丁让 `--timeout 0` 关闭流式无输出超时，HTTP 空闲连接保留有限等待时间。仓库只包含本地修改的编辑坐标和新增代码。上述核查未新增板端性能测量。

## 发布边界

本仓库仅分发自行编写的教程、服务配置、转换/安装/验证脚本及本地新增代码，使用 MIT。没有收录第三方服务端源码、含上游源码上下文的差异补丁、模型、SDK、运行库或示例图片。安装脚本从原作者固定版本获取依赖；`apply_local_changes.py` 仅存储本地新增内容和数值编辑范围，并校验原始源码与结果散列。它不向使用者授予上游服务端的使用、修改或再分发许可。需要这些权限时，应向原作者确认；没有明确许可的上游不能作为可自由再分发的软件打包。

模型名、芯片名和项目名称用于标识兼容目标，不表示获得权利人认可或背书。本项目不是 Qwen、Rockchip、Armbian、systemd 或第三方服务项目的官方发行版。
