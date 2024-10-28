<div align="center">

# nonebot-plugin-comfyui

_⭐基于NoneBot2调用Comfyui(https://github.com/comfyanonymous/ComfyUI)进行绘图的插件⭐_
_⭐AI文生图,图生图...插件(comfyui能做到的它都可以)⭐_  
_⭐本插件适配单后端, 对于多后端请转到https://github.com/DiaoDaiaChan/nonebot-plugin-stable-diffusion-diao⭐_

<a href="https://www.python.org/downloads/release/python-390/"><img src="https://img.shields.io/badge/python-3.10+-blue"></a>  <a href=""><img src="https://img.shields.io/badge/QQ-437012661-yellow"></a> <a href="https://github.com/Cvandia/nonebot-plugin-game-torrent/blob/main/LICENCE"><img src="https://img.shields.io/badge/license-MIT-blue"></a> <a href="https://v2.nonebot.dev/"><img src="https://img.shields.io/badge/Nonebot2-2.2.0+-red"></a>

</div>

---

## ⭐ 介绍

**支持调用comfyui工作流进行绘画的插件, 支持选择工作流, 调整分辨率等等**

## 📜 免责声明

> [!note]
> 本插件仅供**学习**和**研究**使用，使用者需自行承担使用插件的风险。作者不对插件的使用造成的任何损失或问题负责。请合理使用插件，**遵守相关法律法规。**
使用**本插件即表示您已阅读并同意遵守以上免责声明**。如果您不同意或无法遵守以上声明，请不要使用本插件。


## 💿 安装

<details>
<summary>安装</summary>

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

|      基础配置      | 类型  | 必填项 |           默认值           |                                     说明                                     |
|:--------------:|:---:|:---:|:-----------------------:|:--------------------------------------------------------------------------:|
|  comfyui_url   | str |  是  | "http://127.0.0.1:8188" |                                comfyui后端地址                                 |
|comfyui_model| str |  否  |           ""            |                              覆写加载模型节点的时候使用的模型                              |
|  comfyui_workflows_dir  | str |  是  |     ./data/comfyui      |                                comfyui工作流路径                                |
| comfyui_default_workflows | str |  否  |        "txt2img"        | 不传入工作流参数的时候默认使用的工作流名称(请你自己准备喜欢的工作流, 或者复制本仓库中的comfyui_work_flows中的工作流来学习使用) |
|  comfyui_max_res  | int |  否  |          2048           |                                 最大分辨率 ^ 2                                  |
| comfyui_base_res | int |  否  |          1024           |                                 基础分辨率 ^ 2                                  |

## 关键!
**comfyui_url**和**comfyui_workflows_dir**是必须的, 否则插件无法正常工作
### 关于comfyui_workflows_dir路径下的工作流格式
### 请导出工作流的时候选择导出为API格式!
### 每个工作流必须拥有对应的_reflex.json文件, 来映射节点, 例如
目前支持映射的节点如下 (有能力的小伙伴可以在./nonebot_plugin_comfyui/backend/comfyui.py第120行左右中添加更多节点)
```
sampler  # 采样器节点, 对应了采样器, 调度器, 种子, 步数, 降噪幅度
seed  # 覆写种子
image_size  # 图片的分辨率, 对应空lantent图像
prompt  # 提示词
negative_prompt  # 反向提示词
checkpoint  # load_checkopint节点, 对应了模型
load_image  # load_image节点, 对应了加载图片
tipo  # tipo提示词生成节点
```
比如说你有一个工作流叫做my_txt2img.json  
你需要创建一个my_txt2img_reflex.json文件, 内容如下
````
{
  "prompt": 2,  # 对应comfyui-api-json中的node id 为 2的节点, 并且覆写
  "image_size": 4,
  "output": 6,  # output 是必须的(你的 Save Image 节点), 其他的其实都可以不需要
  "seed": 3
}
# 高级节点控制
{
  "tipo": {"50": {"override": {"tags": "append_prompt"}}},
  "sampler": 52,
  "image_size": 53,
  "output": 72
  }
````
这样插件就可以正确映射节点中的内容
## ⭐ 使用

> [!note]
> 请注意你的 `COMMAND_START` 以及上述配置项。

### 指令：

|    指令     | 需要@ | 范围 |   说明    |权限|
|:---------:|:---:|:---:|:-------:|:---:|
|  prompt   |  否  |all|  生成图片   |all|
| comfyui帮助 |  是  |all| 获取简易帮助  |all|


## 💝 特别鸣谢

- [x] [nonebot2](https://github.com/nonebot/nonebot2): 本项目的基础，非常好用的聊天机器人框架。

## TODO
- [ ] 支持中文生图
- [ ] 支持图片审核
- [ ] 查看历史生图记录