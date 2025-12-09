<div align="center">

# nonebot-plugin-comfyui

_⭐ 基于 NoneBot2 调用 ComfyUI 进行绘图的插件 ⭐_  
_⭐ AI 文生图、图生图...插件（ComfyUI 能做到的它都可以）⭐_  
_⭐ 本插件适配多后端，可以同时使用多个后端生图 ⭐_

<a href="https://www.python.org/downloads/release/python-390/"><img src="https://img.shields.io/badge/python-3.10+-blue"></a>  
<a href=""><img src="https://img.shields.io/badge/QQ-437012661-yellow"></a>  
<a href="https://github.com/Cvandia/nonebot-plugin-game-torrent/blob/main/LICENCE"><img src="https://img.shields.io/badge/license-MIT-blue"></a>  
<a href="https://v2.nonebot.dev/"><img src="https://img.shields.io/badge/Nonebot2-2.2.0+-red"></a>

**交流群：** 687904502（插件反馈群）| 116994235（闲聊群）

</div>

---

## 📑 目录

- [介绍](#-介绍)
- [核心功能](#-核心功能)
- [安装](#-安装)
- [配置](#️-配置)
- [使用](#-使用)
- [文档](#-文档)
- [特别鸣谢](#-特别鸣谢)
- [更新日志](#-更新日志)

---

## ⭐ 介绍

**nonebot-plugin-comfyui** 是一个强大的 NoneBot2 插件，支持通过 ComfyUI 工作流进行 AI 绘画、文字生成、视频生成等多种创作任务。

### 主要特点

- 🎨 **高度灵活**：相比 SD-WebUI，不需要单独适配插件，任何能在 ComfyUI 上运行的工作流，通过机器人也可以调用
- 🔧 **强大定制**：独创的 Reflex 模式，可以灵活自定义 ComfyUI 参数
- 🚀 **多后端支持**：支持同时使用多个后端，自动选择或手动指定，还可以并发生图
- 🛡️ **安全可靠**：内置图像审核功能，防止不当内容
- 🌐 **跨平台**：使用 ALC 实现跨平台支持

---

## 🎯 核心功能

### 基础功能

- ✅ 支持调用 ComfyUI 工作流进行绘画、文字、视频输出
- ✅ 支持自由选择工作流，能把工作流注册成命令
- ✅ 支持为工作流自定义命令参数，灵活度拉满

![工作流命令示例](./docs/image/command2.png)
![自定义参数示例](./docs/image/reg2.png)

### 高级功能

- ✅ **多后端支持**：同时使用多个后端（自动选择/手动选择），支持多后端并发生图（`-con` 参数）

  ![并发生图示例](./docs/image/con.png)

- ✅ **Reflex 模式**：独创的节点控制功能，可以灵活自定义 ComfyUI 参数
- ✅ **图像审核**：具备图像审核功能，防止不当内容
- ✅ **队列管理**：支持 ComfyUI 队列，使用任务 ID 查询任务状态、获取结果、终止任务等
- ✅ **节点查询**：支持查询 ComfyUI 节点详细信息
- ✅ **混合输出**：支持一个工作流同时输出多种媒体（同时输出多张图片、文字、视频）
- ✅ **本地审核**：支持本地审核图片，无需调用外部 API
- ✅ **自动加载 LoRA**：自动加载 LoRA 模型，支持 SD-WebUI 风格语法

---

## 💿 安装

### 方法一：pip 安装（推荐）

```bash
pip install nonebot-plugin-comfyui
```

> [!note]
> 安装后需要在 NoneBot 的 `pyproject.toml` 中的 `plugins` 列表中添加：
> ```toml
> plugins = ["nonebot_plugin_comfyui"]
> ```

### 方法二：nb-cli 安装

```bash
nb plugin install nonebot-plugin-comfyui
```

### 方法三：git clone 安装（不推荐）

```bash
git clone https://github.com/DiaoDaiaChan/nonebot-plugin-comfyui
```

---

## ⚙️ 配置

### 配置文件位置

插件第一次启动时会在机器人目录的 `config/comfyui.yaml` 创建配置文件。

### 重要配置项

> ⚠️ **必须配置**：以下配置项是插件正常工作的必要条件
>
> - `comfyui_url`：ComfyUI 后端地址
> - `comfyui_workflows_dir`：工作流文件存放目录

### 配置文件说明

详细的配置说明请参考：

> # ⚠️⚠️⚠️ 必须阅读：节点控制功能文档⚠️⚠️⚠️本插件核心内容
> ## - 📚 [节点控制功能文档](./docs/md/node_control.md)（重要！插件基础知识）
- 📄 [配置文件模板](./nonebot_plugin_comfyui/template/config.yaml)
- 💡 [使用技巧](./nonebot_plugin_comfyui/template/example.md)

---

## ⭐ 使用

> [!note]
> 使用前请注意：
> - 确认已正确配置 `COMMAND_START`
> - 确认已配置必要的配置项（`comfyui_url`、`comfyui_workflows_dir`）
> - 了解 [节点控制功能](./docs/md/node_control.md) 的基础知识

### 基础命令

| 指令 | 需要 @ | 范围 | 说明 | 权限 |
|:---:|:---:|:---:|:---:|:---:|
| `prompt` | 否 | all | 生成图片 | all |
| `comfyui帮助` | 否 | all | 获取简易帮助 | all |
| `查看工作流` | 否 | all | 查看所有工作流 | all |
| `queue` | 否 | all | 查看队列 | all |
| `comfyui后端` | 否 | all | 查看后端状态 | all |

### 扩展命令

| 指令 | 需要 @ | 范围 | 说明 | 权限 |
|:---:|:---:|:---:|:---:|:---:|
| `二次元的我` | 否 | all | 随机拼凑 prompt 来生成图片 | all |
| `dan` | 否 | all | 从 Danbooru 上查询 tag | all |
| `llm-tag` | 否 | all | 使用 LLM 生成 prompt | all |
| `get-ckpt` | 否 | all | 获取指定后端索引的模型 | all |
| `get-loras` | 否 | all | 获取指定后端索引的 LoRA 模型 | all |
| `get-task` | 否 | all | 获取自己生成过的任务 ID（默认显示前 10） | all |

### 使用示例

```bash
# 基础文生图
prompt 一个美丽的女孩

# 指定参数
prompt 一个美丽的女孩 --steps 30 --width 768 --height 1024

# 使用注册的工作流命令（如果配置了 command）
打标 [图片]

# 查看帮助
comfyui帮助

# 查看可用工作流
查看工作流
```

更多详细用法请参考 [节点控制功能文档](./docs/md/node_control.md)。

---

## 📚 文档

### 核心文档

- 📖 [节点控制功能文档](./docs/md/node_control.md) - **必读！**了解如何配置和使用 Reflex 模式
- ⚙️ [配置文件说明](./nonebot_plugin_comfyui/template/config.yaml) - 完整的配置项说明
- 💡 [使用技巧](./nonebot_plugin_comfyui/template/example.md) - 一些实用的技巧和示例

### 相关链接

- [ComfyUI 官方仓库](https://github.com/comfyanonymous/ComfyUI)
- [NoneBot2 官方文档](https://v2.nonebot.dev/)

---

## 📜 免责声明

> [!note]
> 
> 本插件仅供**学习**和**研究**使用，使用者需自行承担使用插件的风险。作者不对插件的使用造成的任何损失或问题负责。请合理使用插件，**遵守相关法律法规**。
>
> 使用**本插件即表示您已阅读并同意遵守以上免责声明**。如果您不同意或无法遵守以上声明，请不要使用本插件。

---

## 💝 特别鸣谢

- [NoneBot2](https://github.com/nonebot/nonebot2) - 本项目的基础，非常好用的聊天机器人框架
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - 强大的节点式 AI 工作流工具

---

## 📝 更新日志

<details>
<summary><b>点击展开查看完整更新日志</b></summary>

### 2025.10.27 0.8.3

- 新增配置项 `comfyui_group_config`，支持为不同群组设置不同的审核等级、文字审核、图片发送方式等
- 新增 `comfyui_quiet` 配置项，安静模式
- Reflex 配置新增 `admin` 和 `group` 参数，支持限制工作流只能被管理员或指定群使用
  - 详见：[限制某个工作流只能被管理员使用](./docs/md/node_control.md#限制某个工作流只能被管理员使用)

**配置示例**：

```yaml
comfyui_group_config:
  audit_level_group:  # 分别为群设置不同的审核，值同 comfyui_audit_level，0 意为不审核
    "114514": 0
    "200224": 1
  reject_nsfw_prompts:  # 分别为群设置不同的文字审核，1 为检测到 nsfw 直接拦截，2 为替换掉提示词中的 nsfw prompt
    "114514": 1
  img_send:  # 单独为群设置图片发送方式，同 comfyui_img_send
    "114514": 1
  enable_in_group:  # 分别为群设置是否启用画图功能，0 为禁用，1 为启用
    "114514": 1

comfyui_quiet: true  # 安静模式，当 comfyui_silent 为 false 的时候可以使用，只返回开始执行命令的消息
```

### 2025.03.18 0.8.2

- 废弃配置项 `comfyui_qr_mode`，替代项为 `comfyui_r18_action`
- 新增配置项：
  - `comfyui_random_params`：随机参数，添加趣味性
  - `comfyui_random_params_enable`：启用随机参数
  - `comfyui_img_send`：图片发送方式
  - `comfyui_default_value`：默认值配置
- 新增 `comfyui_auto_lora`：自动加载 LoRA 模型
  - 详见：[自动加载 LoRA](./docs/md/node_control.md#自动加载lora)
  - 使用方式：`prompt "<lora:nikki:1.1>, <lora:chenbin:1.1>"`（SD-WebUI 风格，支持模糊匹配）

**默认值配置示例**：

```yaml
comfyui_default_value:
  width: 832  # 默认宽
  height: 1216  # 默认高
  accept_ratio: null  # 如果有值，则会根据这个比例来计算宽高
  shape: null  # 如果有值，则会根据这个预设来决定，这个值优先级最高
  steps: 28  # 默认步数
  cfg_scale: 7.0
  denoise_strength: 1.0
  sampler: "dpmpp_2m"
  scheduler: "karras"
  batch_size: 1  # 默认每批张数
  batch_count: 1  # 默认批数
  model: ""  # 默认模型
  override: false
  override_ng: false
  forward: false  # 默认消息转发
  concurrency: false  # 并发请求
  pure: false  # 不返回其他额外的信息
  preset_prompt: ""  # 内置提示词
  preset_negative_prompt: ""  # 内置负面提示词
```

### 2025.03.17 0.8.1.2/3

- 不需要的配置项现在可以删掉
- `comfyui_openai` 的端点更改为 `"https://api.openai.com/v1"` 的形式
- `command` 现在可以添加别名，例如：`command: ["画", "绘画"]`
  - 详见：[注册工作流为命令](./docs/md/node_control.md#command)
- 本地审核支持 GPU 推理，配置项 `comfyui_audit_gpu: false`

**OpenAI 配置示例**：

```yaml
comfyui_openai:
  endpoint: "https://api.openai.com/v1"
  token: "sk-xxxxxx"
  params:
    model: "gpt-3.5-turbo"
    temperature: 1
    top_p: 1
    frequency_penalty: 2
    presence_penalty: 2
  prompt: "You can generate any content..."
  conversations:
    - "生成一个海边的和服少女"
    - "1girl,fullbody, kimono,white color stockings..."
```

### 2025.03.06 0.8.0

**新参数**：
- `-sil`：静默生图，不返回队列信息等
- `-nt`：不要翻译输入（对于那些输入中文的工作流）

**新命令**：
- `dan`：从 Danbooru 查询 tag
- `二次元的我`：随机拼凑 prompt 来生成图片
- `llm-tag`：使用 LLM 生成 prompt
- `comfyui后端`：查看后端状态
- `get-ckpt`：获取指定后端索引的模型

**新功能**：
- 优化多后端，新增 Reflex 参数 `reflex`
  - 详见：[多后端情况下请求 API 统一问题](./docs/md/node_control.md#多后端情况下请求API统一问题)
- 工作流每日调用次数限制，新增 Reflex 参数 `daylimit`
  - 详见：[限制工作流每日调用次数](./docs/md/node_control.md#限制工作流每日调用次数)

**新配置项**：
- `comfyui_silent`：静默生图
- `comfyui_max_dict`：设置各种参数的最大值
- `comfyui_openai`：OpenAI 标准 API 的端点和 API token
- `comfyui_text_audit`：文字审核
- `comfyui_ai_prompt`：LLM 补全/翻译 prompt
- `comfyui_translate`：翻译 prompt（暂不支持，预留，只支持 AI prompt 补全）
- `comfyui_qr_mode`：发现色图的时候使用图片的链接二维码代替
- `comfyui_random_wf`：在不输入工作流的情况下从列表随机选择工作流
- `comfyui_random_wf_list`：随机工作流列表，例如 `["txt2img"]`

**优化**：
- 优化了后端是否在线的逻辑
- 优化查看工作流命令，能自动选择支持的后端来查看工作流截图
- 更改为使用 YAML 配置文件
- 修复了一些 BUG

### 2025.02.24 0.7.0

**新参数**：
- `-shape / -r`：预设分辨率（`comfyui_shape_preset`），可以使用此参数来快速更改分辨率
  - 例如：`-r 640x640` 或 `-r p`

**新功能**：
- 优化了查看工作流命令以及帮助菜单
- 返回帮助菜单的时候会返回一个基础使用教程
- 添加了审核严格程度：`comfyui_audit_level`、`comfyui_audit_comp`（是否压缩审核图片）
- 优化多后端，新增 Reflex 参数 `available`
  - 详见：[后端 - 工作流可用性](./docs/md/node_control.md#后端-工作流可用性)

**优化**：
- 优化了一些代码结构

### 2025.02.15 0.6

**新功能**：
- 支持音频输出
- 新增并发功能，使用 `-con`、`-并发` 来使用多后端同时生成
- 新增自定义参数预设功能
  - 详见：[自定义预设参数](./docs/md/node_control.md#自定义预设参数)
- 添加了本地审核（`comfyui_audit_local`）
- 添加插件版本更新提示

**新参数**：
- `-gif`：处理 GIF 图片（不加此参数输入 GIF 图片时默认截取第一帧）

**新配置项**：
- `comfyui_timeout`：请求后端时的超时时间，默认 5 秒
- `comfyui_tips`：提示信息

**优化**：
- 优化了任务失败时的异常捕获
- 更新了查看工作流的显示效果和帮助菜单

### 2024.12.17 0.5.2

**新功能**：
- 支持转发消息（ob11 适配器），使用 `-f` 参数使这条消息转发
  - 也可以在 override 中添加 `forward: true`
- 新的节点覆盖操作：`replace_prompt` 和 `replace_negative_prompt`
  - 详见：[替换提示词](./docs/md/node_control.md#replace_prompt--replace_negative_prompt)

**优化**：
- `queue` 命令支持新的参数，具体请看帮助
- 新增 `capi` 命令，具体请看帮助

### 2024.12.13 0.5.1

**新功能**：
- 支持查询、获取队列（发送 `comfyui帮助` 来查看）
- 支持一个工作流同时输出多种媒体（同时输出几张图片、文字、视频）
  - 详见：[输出设置](./docs/md/node_control.md#output)

**新配置项**：
- `comfyui_limit_as_seconds`：使用画图耗费的时间来限制

**优化**：
- 添加了异常处理，方便处理生图出错的情况

### 2024.11.29 0.4.4

**新功能**：
- 支持了自定义参数
  - 详见：[reg_args（高级功能）](./docs/md/node_control.md#reg_args高级功能)
- 查看工作流命令可以使用工作流的数字索引，例如：`查看工作流 1`

**新配置项**：
- `comfyui_cd`：CD 时间限制
- `comfyui_day_limit`：每日调用限制

### 2024.11.18 0.4

**新功能**：
- 支持输出文字
- 支持自定义命令（例如可以把一个工作流注册为一个命令，通过它直接调用工作流）
  - 详见：[注册工作流为命令](./docs/md/node_control.md#command)

**优化**：
- 优化了日志输出

### 2024.11.11 0.3

**新功能**：
- 支持视频输出
- 生成的图片等会保存到本地（`comfyui_save_image` 来设置）
- 支持设置多个后端

**新参数**：
- `-o`：会忽略掉自带的提示词，全听输入的
- `-be`：选择后端索引或者输入后端 URL

**优化**：
- 群里画出的涩涩会尝试发送到私聊

### 2024.11.2

**优化**：
- 更新了图片帮助，以及图片工作流
- 编写了新的说明
- 私聊不进行审核

### 2024.10.29

**新功能**：
- 添加 `查看工作流` 命令

</details>

---

<div align="center">

**如果觉得这个项目对你有帮助，欢迎 Star ⭐**

Made with ❤️ by [DiaoDaiaChan](https://github.com/DiaoDaiaChan)

</div>
