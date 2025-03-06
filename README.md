<div align="center">

# nonebot-plugin-comfyui

_⭐基于NoneBot2调用Comfyui(https://github.com/comfyanonymous/ComfyUI)进行绘图的插件⭐_  
_⭐AI文生图,图生图...插件(comfyui能做到的它都可以)⭐_  
_⭐本插件适配多后端, 可以同时使用多个后端生图哦_

<a href="https://www.python.org/downloads/release/python-390/"><img src="https://img.shields.io/badge/python-3.10+-blue"></a>  <a href=""><img src="https://img.shields.io/badge/QQ-437012661-yellow"></a> <a href="https://github.com/Cvandia/nonebot-plugin-game-torrent/blob/main/LICENCE"><img src="https://img.shields.io/badge/license-MIT-blue"></a> <a href="https://v2.nonebot.dev/"><img src="https://img.shields.io/badge/Nonebot2-2.2.0+-red"></a>

</div>

---

## ⭐ 介绍

**支持调用comfyui工作流进行绘画的插件, 支持选择工作流, 调整分辨率等等**
## 群 687904502 / 116994235

## 📜 免责声明

> [!note]
> 本插件仅供**学习**和**研究**使用，使用者需自行承担使用插件的风险。作者不对插件的使用造成的任何损失或问题负责。请合理使用插件，**遵守相关法律法规。**
使用**本插件即表示您已阅读并同意遵守以上免责声明**。如果您不同意或无法遵守以上声明，请不要使用本插件。

## 核心功能/优势!
- 相比SD-WebUI, 不需要单独适配插件, 能在comfyui上跑通, 使用机器人一样可以!具有很高的灵活度!
- [x] 支持调用comfyui工作流进行绘画/文字/视频输出
- [x] 支持自由选择工作流, 能把工作流注册成命令, 并且支持为工作流自定义命令参数, 灵活度拉满!
![emb](./docs/image/command2.png)
![emb](./docs/image/reg2.png)
- [x] 支持同时使用多个后端(自动选择/手动选择), 支持多后端同时生图(-con 参数)
![emb](./docs/image/con.png)
- [x] 独创reflex模式, 来自定义comfyui参数
- [x] 具备图像审核, 防止涩涩
- [x] 使用ALC实现跨平台
- [x] 支持comfyui队列, 使用任务id来查询任务状态, 获取任务生成结果, 终止任务等等
- [x] 支持查询comfyui节点详细信息
- [x] 支持一个工作流同时输出多种媒体(同时输出几张图片, 文字, 视频)
- [x] 支持本地审核图片了, 不需要再调用雕雕的api

## 💿 安装

`pip` 安装

```bash
pip install nonebot-plugin-comfyui
```
> [!note] 在nonebot的pyproject.toml中的plugins = ["nonebot_plugin_comfyui"]添加此插件

`nb-cli`安装
```bash
nb plugin install nonebot-plugin-comfyui
```

`git clone`安装(不推荐)

- 命令窗口`cmd`下运行
```bash
git clone https://github.com/DiaoDaiaChan/nonebot-plugin-comfyui
```

## ⚙️ 配置

**插件第一次启动会在机器人目录/config/comfyui.yaml创建配置文件**
# [配置文件](./nonebot_plugin_comfyui/template/config.yaml)

## 关键!
**comfyui_url**和**comfyui_workflows_dir**是必须的, 否则插件无法正常工作
# [重要!插件基础芝士](./docs/md/node_control.md)
## 一些小trick
## [trick](./nonebot_plugin_comfyui/template/example.md)

## ⭐ 使用

> [!note]
> 请注意你的 `COMMAND_START` 以及上述配置项。

### 指令：

|    指令     | 需要@ | 范围 |   说明    |权限|
|:---------:|:---:|:---:|:-------:|:---:|
|  prompt   |  否  |all|  生成图片   |all|
| comfyui帮助 |  否  |all| 获取简易帮助  |all|
|   查看工作流   |  否  |all| 查看所有工作流 |all|
|   queue   |  否  |all|  查看队列   |all|


## 💝 特别鸣谢

- [x] [nonebot2](https://github.com/nonebot/nonebot2): 本项目的基础，非常好用的聊天机器人框架。

## 更新日志
### 2025.03.05 0.8.0
- 新的参数 -sil, 静默生图, 不返回队列信息等
- 新的参数 -nt, 不要翻译输入 (对于那些输入中文的工作流)
- 新的命令: dan, 二次元的我, llm-tag, comfyui后端, get-ckpt
- 优化多后端, 新的reflex参数 reflex, 见 [多后端情况下请求API统一问题](./docs/md/node_control.md#多后端情况下请求API统一问题)
- 工作流每日调用次数限制, 新的reflex参数 daylimit, 见 [每日次数限制](./docs/md/node_control.md#限制工作流每日调用次数)
- 新的配置项目 (本README可以找到详细)
- comfyui_silent 静默生图
- comfyui_max_dict 设置各种参数的最大值
- comfyui_openai openai标准api的断点和api token
- comfyui_text_audit 文字审核
- comfyui_ai_prompt llm补全/翻译prompt
- comfyui_translate 翻译prompt (暂不支持没有找到合适的免费翻译API, 预留, 只支持ai prompt补全)
- comfyui_qr_mode 发现色图的时候使用图片的链接二维码代替
- comfyui_random_wf 在不输入工作流的情况下从以下列表随机选择工作流
- comfyui_random_wf_list = ["txt2img"]
- 优化了后端是否在线的逻辑
- 修复了一些BUG
- 优化查看工作流命令, 能自动选择支持的后端来查看工作流截图
- 更改为使用yaml配置文件, 说明也一并迁移到 [配置文件](./nonebot_plugin_comfyui/template/config.yaml)
### 2025.02.24 0.7.0
- 新的参数 -shape / -r  , 预设分辨率(comfyui_shape_preset), 可以使用此参数来快速更改分辨率 (-r 640x640 / -r p)
- 优化了查看工作流命令以及帮助菜单
- 返回帮助菜单的时候会返回一个基础使用教程
- 添加了审核严格程度, comfyui_audit_level, comfyui_audit_comp (是否压缩审核图片) 
- 优化了一些代码结构
- 优化多后端,  新的reflex参数 available, 见 [后端 - 工作流可用性](./docs/md/node_control.md#后端-工作流可用性)
### 2025.02.15 0.6
- 支持音频输出
- 新的 -gif 参数 / 不加上它输入gif图片的时候默认截取第一帧
- 优化了任务失败时候的异常捕获
- 新增comfyui_timeout, 请求后端的时候的超时时间, 默认5秒
- 新增了tips
- 新增了并发功能, 使用 -con, -并发 来使用多后端同时生成
- 新增了自定义参数预设功能  [设定自定义参数](./docs/md/node_control.md#自定义预设参数)
- 更新了查看工作流的显示效果和帮助菜单
- 添加插件版本更新提示
- 添加了本地审核 (comfyui_audit_local)
### 2024.12.17 0.5.2
- 支持转发消息(ob11适配器), 使用 -f 参数使这条消息转发, 也可以在override中添加 forward: true
- queue命令支持新的参数, 具体请看帮助
- 新capi命令, 具体请看帮助
- 新的节点覆盖操作, replace_prompt和replace_negative_prompt [替换提示词](./docs/md/node_control.md#replace_prompt--replace_negative_prompt)
### 2024.12.13 0.5.1
- 支持查询, 获取队列 (发送 comfyui帮助来查看)
- 添加能使用画图耗费的时间来限制 (设置 comfyui_limit_as_seconds = true)
- 添加了异常, 方便处理生图出错的情况
- 支持一个工作流同时输出多种媒体(同时输出几张图片, 文字, 视频) [输出设置](./docs/md/node_control.md#output)
### 2024.11.29 0.4.4
- 支持了自定义参数 见 [重要!插件基础芝士](./docs/md/node_control.md#reg_args-难点-敲黑板)
- 查看工作流命令可以使用工作流的数字索引, 例如 查看工作流 1
- 添加了CD和每日调用限制(见comfyui_cd, comfyui_day_limit)
### 2024.11.18 0.4
- 支持输出文字
- 支持自定义命令(例如我可以把一个工作流注册为一个命令, 通过它直接调用工作流), 请看[新的覆写节点](./docs/md/node_control.md#覆写节点名称)
- 优化了日志输出
### 2024.11.11 0.3
- 支持视频
- 生成的图片等会保存到本地(comfyui_save_image)来设置
- 群里画出的涩涩会尝试发送到私聊
- 新的 -o 参数, 会忽略掉自带的提示词, 全听输入的
- 新的 -be 参数, 选择后端索引或者输入后端url
- 支持设置多个后端
### 2024.11.2
- 更新了图片帮助, 以及图片工作流
- 编写了新的说明
- 私聊不进行审核
### 2024.10.29 
- 添加 查看工作流 命令