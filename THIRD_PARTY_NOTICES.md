# 第三方依赖与许可边界

本仓库 MIT 仅覆盖自行编写的文档、配置、脚本和新增代码，不向第三方软件、模型或商标授予任何权利。

| 依赖 | 来源及固定版本 | 许可处理 |
| --- | --- | --- |
| Qwen3.5-2B | [Qwen 官方仓库](https://huggingface.co/Qwen/Qwen3.5-2B/tree/15852e8c16360a2fea060d615a32b45270f8a8fc) | 模型声明 Apache-2.0；权重不分发，使用者从官方获取并遵循其条款。 |
| RKLLM | [release-v1.3.1](https://github.com/airockchip/rknn-llm/blob/f7390530443bf84f0394255a449d7cbe81e69d1c/LICENSE) | 遵循上游 LICENSE 及所含第三方条款；不收录 SDK 或运行库。 |
| RKNN Toolkit2 / Runtime | [v2.5.0](https://github.com/airockchip/rknn-toolkit2/blob/2c723177a94fac65cbc036d722907ddbc91980cf/LICENSE) | 适用专门 RKNN SDK 协议；不以 MIT 重新许可，不收录二进制。 |
| rkllm-docker 的 VLM 服务 | [固定提交](https://github.com/Hanzo-Huang/rkllm-docker/tree/ad016395d68e4fa789e139567b92c2320ba02249) | 核查时未声明许可证；不分发其源码或含其源码上下文的补丁。本地修改脚本只包含新增内容及编辑坐标，不授予上游权限。 |
| uv / Python / Python 依赖 / systemd | 各原始发行方 | 由使用者分别获取，各自许可证继续适用；本仓库只记录依赖版本和配置。 |

VLM 服务未声明许可证，不等于可自由使用、修改或再分发。需要相关权利时应向原作者确认，尤其不要将其源码和本仓库 MIT 一起重新打包。安装脚本的下载引用不是许可证授权。本教程记录已验证的本地部署，不承诺上游的再分发权利或生产稳定性。

本项目为非官方部署资料，与 Qwen、Rockchip 及上述上游项目无隶属或背书关系。未收录第三方图片，也没有发布模型产物、SDK、运行库、访问令牌或私人机器信息。
