<div align="center">

# nonebot-plugin-comfyui

_⭐基于NoneBot2调用Comfyui(https://github.com/comfyanonymous/ComfyUI)进行绘图的插件⭐_  
_⭐AI文生图,图生图...插件(comfyui能做到的它都可以)⭐_  
_⭐本插件适配多后端, 不过对于更多的多后端支持请转到https://github.com/DiaoDaiaChan/nonebot-plugin-stable-diffusion-diao⭐_

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

**在.env中添加以下配置**

|           基础配置            |  类型  | 必填项 |                        默认值                         |                                     说明                                     |
|:-------------------------:|:----:|:---:|:--------------------------------------------------:|:--------------------------------------------------------------------------:|
|        comfyui_url        | str  |  是  |              "http://127.0.0.1:8188"               |                                comfyui后端地址                                 |
|     comfyui_url_list      | list |  否  | ["http://127.0.0.1:8188", "http://127.0.0.1:8288"] |                               comfyui后端地址列表                                |
|        comfyui_multi_backend        | bool |  否  |                       False                        |                                   多后端支持                                    |
|       comfyui_model       | str  |  否  |                         ""                         |                              覆写加载模型节点的时候使用的模型                              |
|   comfyui_workflows_dir   | str  |  是  |                   ./data/comfyui                   |                                comfyui工作流路径                                |
| comfyui_default_workflows | str  |  否  |                     "txt2img"                      | 不传入工作流参数的时候默认使用的工作流名称(请你自己准备喜欢的工作流, 或者复制本仓库中的comfyui_work_flows中的工作流来学习使用) |
|      comfyui_max_res      | int  |  否  |                        2048                        |                                 最大分辨率 ^ 2                                  |
|     comfyui_base_res      | int  |  否  |                        1024                        |                                 基础分辨率 ^ 2                                  |
|       comfyui_audit       | bool |  否  |                        True                        |                                   启动图片审核                                   |
|    comfyui_audit_site     | str  |  否  |         "http://server.20020026.xyz:7865"          |                                   图片审核地址                                   |
|    comfyui_save_image     | bool |  否  |                        True                        |                                是否保存媒体文件到本地                                 |


```env
comfyui_url= "http://127.0.0.1:8188"
comfyui_url_list = ["http://127.0.0.1:8188", "http://127.0.0.1:8288"]
comfyui_multi_backend = False
comfyui_model = ""
comfyui_workflows_dir = "./data/comfyui"
comfyui_default_workflows = "txt2img"
comfyui_max_res = 2048
comfyui_base_res = 1024
comfyui_audit = True
comfyui_audit_site = "http://server.20020026.xyz:7865"
comfyui_save_image = True
```

## 关键!
**comfyui_url**和**comfyui_workflows_dir**是必须的, 否则插件无法正常工作
# 重要!
### 关于comfyui_workflows_dir路径下的工作流格式
### 请导出工作流的时候选择导出为API格式!
## [重要!插件基础芝士](./docs/md/node_control.md)

## ⭐ 使用

> [!note]
> 请注意你的 `COMMAND_START` 以及上述配置项。

### 指令：

|    指令     | 需要@ | 范围 |   说明    |权限|
|:---------:|:---:|:---:|:-------:|:---:|
|  prompt   |  否  |all|  生成图片   |all|
| comfyui帮助 |  否  |all| 获取简易帮助  |all|
|   查看工作流   |  否  |all| 查看所有工作流 |all|


## 💝 特别鸣谢

- [x] [nonebot2](https://github.com/nonebot/nonebot2): 本项目的基础，非常好用的聊天机器人框架。

## TODO
- [ ] 支持中文生图
- [x] 支持图片审核
- [ ] 查看历史生图记录
- [x] 多媒体支持 (已支持图片/视频/文字)
- [x] 保存图片
- [x] 支持设置多个后端
- [x] 支持自定义命令

## 更新日志
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