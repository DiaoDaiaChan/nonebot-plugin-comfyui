# 本插件提供了详细的控制节点输入的功能

## 为什么需要这个功能?
## 答: 因为comfyui的工作流导出的时候, 使用的参数固定死了(比如种子, 分辨率, 步数等等), 本功能就可以选择哪些参数进行定制化(例如重新输入分辨率等等)
***
## 在开始之前, 准备API格式的JSON文件
### 首先,对于图片工作流来说必须要有一个Save Image(Preview Image也行)节点来输出
![emb](../image/setting4.png)
### 之后, 导出API格式的JSON工作流文件
![emb](../image/setting1.png)  
![emb](../image/setting2.png)  
![emb](../image/setting3.png)  
***
# 接下来是重点, 本插件的核心, Reflex
## 创建一个json文件, 名称和工作流名称一致, 并且加上_reflex, 把它们一起放在./data/comfyui(你设置的工作流路径内)
比如说你有一个工作流叫做my_txt2img.json 
![emb](../image/setting1.png) 
你需要创建一个my_txt2img_reflex.json文件, 内容如下
```json
{
  "sampler": 3,
  "image_size": 5,
  "output": 9,
  "prompt": 6,
  "negative_prompt": 7,
  "command": "绘画",
  "note": "基础sdxl文生图工作流"
  }
```
## 不清楚如何编写reflex的话, 机器人第一次启动创建一些默认工作流(默认路径: 机器人目录/data/comfyui), 请你结合以下文档以及默认工作流来学习
### 键为: 请看表 覆写节点名称 , 值为comfyui导出的json文件中对应的节点ID
****
### 覆写节点名称

|     覆写节点名称      | 是否必须填写 |                                                                          详细参数/会覆写掉的参数                                                                           |                                                        说明                                                        |权限|
|:---------------:|:------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------:|:----------------------------------------------------------------------------------------------------------------:|:---:|
|     output      |   是    |                                                                          无(关键节点, 必须要填)                                                                          |                                              对应comfyui的Save image节点                                              |all|
|     sampler     |   否    |                                                        seed, steps, cfg, sampler_name, scheduler,denoise                                                        |                                               对应comfyui的KSampler节点                                               |all|
|      seed       |   否    |                                                                              seed                                                                               |                                                   覆写任何有seed的节点                                                   |all|
|   image_size    |   否    |                                                                    width, height, batch_size                                                                    |                                           对应comfyui的EmptyLatentImage节点                                           |all|
|     prompt      |   否    |                                                                         text  (覆写正面提示词)                                                                         |                                            对应comfyui的CLIPTextEncode节点                                            |all|
| negative_prompt |   否    |                                                                        text   (覆写负面提示词)                                                                         |                                            对应comfyui的CLIPTextEncode节点                                            |all|
|   checkpoint    |   否    |                                                                            ckpt_name                                                                            |                                        对应comfyui的CheckpointLoaderSimple节点                                        |all|
|   load_image    |   否    |                                                                              image                                                                              |                                              对应comfyui的LoadImage节点                                               |all|
|      tipo       |   否    |                                                                    width, height, seed, tags                                                                    |                                                 对应comfyui的TIPO节点                                                 |all|
|    override     |   否    | 字典,支持的键prompt, negative_prompt, accept_ratio, seed, steps, cfg_scale, denoise_strength, height, width, video, work_flows, sampler, scheduler, batch_size, model | 选择到此工作流的时候使用的自定义参数, 例如我想要此工作流默认使用30步绘图, 使用采样器ddim,但是不想修改工作流文件, 可以这样写"override": {"sampler": "ddim", "steps": 30} |all|
|      note       |   否    |                                                                      字符串, 备注节点, 会被加入到帮助菜单中                                                                      |                                                        备注                                                        |all|
|      media      |   否    |                                                          字符串, 暂时支持image, video, text,"media": "video"                                                           |                                               字符串, 标记这条工作流的输出是什么类型                                               |all|
|     command     |   否    |                                                              该工作流的名称会被注册为命令  ,"command": "tagger"                                                               |                  例如工作流名叫 tagger, 添加此覆写之后, 使用 tagger 命令即可自动调用此节点(可以不和工作流名称相同哦!你的命令不一定要是tagger!)                   |all|
|    reg_args     |   否    |                                                                     为注册的命令添加参数  ,用法请看下面的例子                                                                      |                              例如在一个工作流中, 我想要控制一个参数, 但是默认的节点覆写没有, 我就可以使用这个来为命令添加自定义参数                              |all|
|    available    |   否    |                                                                       列表, 代表这个工作流在哪个后端可用                                                                        |                                       在多后端工作模式中, 有些工作流可能有些后端无法调用, 故提供此覆写操作                                       |all|
|    daylimit     |   否    |                                                                       整数, 代表这个工作流每天能调用几次                                                                        |                                                整数, 代表这个工作流每天能调用几次                                                |all|
|     reflex      |   否    |                                                                               字典                                                                                |                                                为某个特定后端的某个节点选择指定的值                                                |all|
|      admin      |   否    |                                                                               布尔                                                                                |                                                添加之后此工作流不允许非管理员使用                                                |all|1


****
## 节点高级操作
|          覆写操作           | 需要额外参数 |              参数说明               |            说明             |权限|
|:-----------------------:|:------:|:-------------------------------:|:-------------------------:|:---:|
|         randint         |   否    |                /                |         随机生成一个整数          |all|
|      append_prompt      |   否    |                /                |    将工作流中自带的正面提示词添加到输入中    |all|
| append_negative_prompt  |   否    |                /                |    将工作流中自带的负面提示词添加到输入中    |all|
|     replace_prompt      |   否    |                /                |  将输入提示词替换到工作流中的{prompt}中  |all|
| replace_negative_prompt |   否    |                /                | 将输入负面提示词替换到工作流中的{prompt}中 |all|
|         upscale         |   是    |           upscale_1.5           |      对数字进行乘算, 数字为倍率       |all|
|          value          |   是    | value_你的值_值的类型(int, str, float) |     固定工作流中的数值(优先级最高)      |all|
|          image          |   是    |             image_0             |      适用于需要加载多个图片的工作流      |all|
****
## 还请你阅读仓库内的comfyui_work_flows来学习基本使用

### ⚠️⚠️⚠️!注意看图! 关键是output, 连接到了SaveImage节点, 这个是必须的️⚠️⚠️

![emb](../image/node.png)
### ️⚠️⚠️其他的节点都可以不覆写, 但是你就无法通过参数来控制工作流内的参数 ️⚠️⚠️️⚠️
![emb](../image/setting5.png)
```
{
"prompt": 32,
"output": 94,  # 必须要!
"load_image": 3,
"negative_prompt": 7
}
----第二个例子-----
{
"tipo": 50,
"sampler": 52,  # sampler节点
"seed": 52  # 只替换sampler节点中的seed参数
"image_size": 53,
"output": 72,
  }
```
### 接下来为高级节点控制, 请观察以下
### 覆写的意思是, prompt -t 30 , 这里的步数30步, 覆写到comfyui的API json中, 因为api json中的值是固定的
```
{
# 覆写多个节点
"prompt": [114, 514]  # 为节点114, 和 514 添加覆写
"override": {"sampler": "ddim", "steps": 30}  # 选择到此工作流的时候使用的自定义参数, 例如我想要此工作流默认使用30步绘图, 使用采样器ddim,但是不想修改工作流文件
"note": "文生图工作流"  # 仅用作备注
}
```
### 高级节点控制 / 可以同时覆写多个节点
### 格式为: 节点ID: {"override": {"comfyui api json 中的键": "操作(请看下面的表-节点高级操作)"}} ↓请看图
![emb](../image/advance_node_control.png)  
```
"prompt": {"50": {"override": {"text": "append_prompt"}}, "52": {"override": {"text": "append_prompt"}}}  # 覆写节点id为52的节点, 键为text, 操作为把api json文件中的text的值加到正面提示词中
```

# 以下是详细讲解
## [节点覆写](#节点覆写)
## [高级节点覆写操作](#高级节点覆写操作)

# 节点覆写

## output
- 本插件工作必须需要这个覆写对于图片来说, 可以是save image节点, 也可以是Preview Image节点, show text, video 节点也是可以的.
```json
{
  "output": 9
}
```
![emb](../image/output.png) 
![emb](../image/output2.png) 
- 接下来介绍如何同时输出多种媒体(例如同时输出图片以及文字, 视频)
```json
{
    "output": {
    "image": [
    31,
    32
    ],
    "text": [33],
    "video": [34]
  }
}
```
- 以上例子中, 31是save image节点, 32是preview image节点, 33是一个文本框, 34是video combine输出节点, 机器人会同时输出2张图片, 一段文字, 一段视频

## sampler
- 采样器, 添加覆写之后就可以使用命令参数来覆写seed, steps, cfg, sampler_name, scheduler,denoise, 对应comfyui的KSampler节点
```json
{
  "sampler": 9
}
```
![emb](../image/sampler.png)
![emb](../image/sampler2.png)
## seed
- 种子, 覆写节点中的 seed / noise_seed, 如果你发现画图一直是同一张, 考虑是不是没有覆写它
```json
{
  "seed": 9
}
```
![emb](../image/seed.png)
![emb](../image/seed2.png)

## image_size
- 空的潜空间图像, 可以理解为图片最后的大小啦, 对应comfyui的EmptyLatentImage节点, 每批张数以及图片的高度和宽度由它决定
```json
{
  "image_size": 4
}
```
![emb](../image/image_size.png)
![emb](../image/image_size2.png)

## prompt / negative_prompt
- 提示词, 其实可以是任何需要输入text的节点, negative_prompt同
```json
{
  "prompt": 6
}
```
![emb](../image/positive.png)
![emb](../image/negative.png)
![emb](../image/text.png)

## checkpoint
- 模型, 对应comfyui的LoadCheckpoint节点(个人用得比较少, 覆写了之后可以使用 -m 参数来指定模型!)
```json
{
  "checkpoint": 45
}
```
![emb](../image/ckpt.png)
![emb](../image/ckpt2.png)

## load_image
- 加载图像节点, 对应comfyui的LoadImage节点
```json
{
  "load_image": 17
}
```
![emb](../image/uploadimg.png)
![emb](../image/uploadimg2.png)

## override

- 覆写节点, 可以为工作流加载默认的参数, 例如
- 支持的键prompt, negative_prompt, accept_ratio, seed, steps, cfg_scale, denoise_strength, height, width, work_flows, sampler, scheduler, batch_size, model, override, override_ng, backend, batch_count, forward, concurrency, shape, silent, notice, no_trans  
```
{
"override": {
  "prompt": "",  # 提示词
  "negative_prompt": "",  # 负面提示词
  "accept_ratio": "2:1",  # 画幅比例
  "seed": 123456,  # 种子
  "steps": 35,  # 迭代步数
  "cfg_scale": 7.5,   # cfg
  "denoise_strength": 0.7,  # 降噪强度
  "height": 512,  # 图像高度
  "width": 768,  # 图像宽度
  "work_flows": "default",  # 选择的工作流
  "sampler": "Euler a",  # 采样器
  "scheduler": "normal",  # 调度器
  "batch_size": 1,  # 每批次数量
  "batch_count": 1,  # 总批次
  "model": "stable-diffusion-v1-5.ckpt",  # 模型
  "override": false,  # 不使用内置正面提示词
  "override_ng": false,  # 不使用内置负面提示词
  "forward": false,  # 转发消息
  "concurrency": false,  # 并发
  "shape": "832x1216",  # 也是默认分辨率 
  "silent": false,  # 静默生图
  "notice": false,  # 执行完成后通知
  "no_trans": false  # 不翻译提示词
  }
}
```
- 使用此工作流的时候, 会默认使用以上参数
- 例: prompt nahida (默认cfg_scale 7.5, 图像高度 512, 图像宽度 768, 迭代步数 35)
- 但是, 如果你手动指定, 优先级会更高, 例: prompt nahida --steps 28, 最后的参数是(cfg_scale 7.5, 图像高度 512, 图像宽度 768, 迭代步数 28)

## note
- 备注, 在查看工作流  命令中显示工作流的备注.
```json
{
  "note": "这是一个基础工作流"
}
```

## media
- 标记此工作流的输出类型(是图像(image), 文字(text), 还是视频(video)), 不填写的话默认图片
- 不推荐使用, 可以看看上面(output)讲到的混合输出模式
```json
{
  "media": "text"
}
```
- 例如这个打标工作流

![emb](../image/tagger.png)

## command
- 将此工作流注册为命令, 我们还是以上面的tagger工作流为例子
- 看! 我们将tagger这个工作流注册为了"打标"命令, 我们使用"打标"命令的时候会自动调用这个工作流
- 注册为命令之后, 其他的参数依然是生效的, 例如 "prompt --steps 28", "打标 --steps 28" 也是可以的(举个例子)
```json
{
  "media": "text",
  "output": 87,
  "command": "打标",
  "load_image": 85
}

```
- 我们可以使用别名, 例如
```json
{
  "media": "text",
  "output": 87,
  "command": ["打标", "tagger", "分析"],
  "load_image": 85
}
```
![emb](../image/command.png)
![emb](../image/command2.png)

## reg_args  (难点! 敲黑板!)
- 我们将工作流注册为命令之后, 我们还可以将为注册的命令添加自定义参数哦!
- 就比如接下来的例子, 一个flux fill扩图工作流
- 注意, type使用python的数据类型(int, str, float, bool, etc...)
``` yaml
{
  "load_image": 17,
  "output": 9,
  "command": "扩图",
  "note": "flux-fill扩图, 建议扩图分辨率不要超过200",
  # 重点关注下面! 
  "reg_args": {
    "44": {
      "args":
        [
          {
            "name_or_flags": ["-opl"],
            "type": "int",
            "dest": "left_unique",
            "help": "向左扩图",
            "default": 0,
            "dest_to_value": {"left_unique": "left"}
          },
          {
            "name_or_flags": ["-opr"],
            "type": "int",
            "dest": "right",
            "help": "向右扩图",
            "default": 0
          },
          {
            "name_or_flags": ["-opt"],
            "type": "int",
            "dest": "top",
            "help": "向上扩图",
            "default": 128
          },
          {
            "name_or_flags": ["-opb"],
            "type": "int",
            "dest": "bottom",
            "help": "向下扩图",
            "default": 128
          },
          {
            "name_or_flags": ["-ft"],
            "type": "int",
            "dest": "feathering",
            "help": "羽化半径",
            "default": 30
          }
        ]
    }
  }
}
```
- 请看图
![emb](../image/reg.png)
![emb](../image/reg2.png)

## 自定义预设参数
- 为了方便自定义参数, 本插件内置了一个自定义参数映射功能
- 添加到reg_args内, 这样我们可以使用 -cn low, 来将控制强度设定为0.5
- 思路打开, 我们可用注册很多参数, 比如说快速更换提示词和模型
```json
{
  "reg_args": {
    "21": {
      "args": [
        {
          "name_or_flags": [
            "-cn"
          ],
          "type": "float",
          "dest": "strength",
          "help": "控制强度",
          "default": 0.8,
          "preset": {
            "default": 0.8,
            "low": 0.5,
            "mid": 0.8,
            "high": 1.0
          }
        }
      ]
    }
  }
}
```


## 后端-工作流可用性
- 在多后端工作模式中, 有些工作流可能有些后端无法调用, 故提供此覆写操作
- 比如说, 1号后端才拥有工作流A所需要的模型, 2号后端使用工作流A就会报错, 故插件更新了以下特性
- 当能执行此工作流的后端不在线的时候, 能抛出异常提醒
- 当能手动选择不能执行此工作流的后端的时候, 能自动选择到能执行的后端
```json
{
  "available": [0, 1]
}
```
- 如果你的 comfyui_url_list 为 [http://127.0.0.1:8188, http://127.0.0.1:8288, http://127.0.0.1:8388]
- 那么, 0号后端就是 http://127.0.0.1:8188, 1号后端就是 http://127.0.0.1:8288, 此工作流能在这两个后端上面执行

## 限制工作流每日调用次数
- 某些工作流消耗时间太长, 为了避免用户一直调用此工作流, 可以使用此设置
```json
{
  "daylimit": 2
}
```
- 意为着此工作流每天只能调用2次

## 多后端情况下请求API统一问题
- 在多后端工作模式中, 有些工作流可能没有需要调用的模型(或者类似参数)
- 使用场景示例: 比如说, 1号后端拥有noob1.safetensors模型, 2号后端有noob_eps_1.safetensors
- 他们实际上是同一个模型, 只是名称不一样, 但是使用api json去请求, 会报错找不到模型
- 故提供以下操作
```json
{
"reflex": {
    "0" : {"4":  {"ckpt_name":  "NoobXL-EPS-v1.1.safetensors"}
    }
  }
}
```
- 意为, 当此工作流请求到0号后端的时候, 为4号节点的ckpt_name参数应用NoobXL-EPS-v1.1.safetensors

## 自动加载lora
- 请注意, 使用本功能节点id会累加(第一个lora#11, 第二个#12, 以此类推), 如果和其他节点id冲突会报错, 所以可以把节点id改的比较大一些
- 配合comfyui_auto_lora使用, 当comfyui_auto_lora启动的时候, 此项目才有效
- 支持两种配置模式
- 导出的工作流需要拥有一个lora加载节点, 直接填写其对应的id即可
- prompt "\<lora:nikki:1.1>, \<lora:chenbin:1.1>" (自动加载nikki和chenbin lora模型)
```json
{
"lora": 11
}
```
- 第二种方法比较灵活也比较麻烦
- 导出的工作流**不需要**, **不需要**, **不需要**lora加载节点
- prompt "\<lora:nikki:1.1>, \<lora:chenbin:1.1>" (自动加载nikki和chenbin lora模型)
- 比较复杂, 看图
- ![emb](../image/lora.png)
```
{
  "lora": [
    {  
      "11" # 手动为它分配一个节点id 11: {
        "from": {
          "model": 4,
          "clip": 4
        },
        "to": {
          "model": [3],
          "clip": [6,7]
        }
      }
    }
  ]
}
```

## 限制某个工作流只能被管理员使用
- 使用此参数之后，只有管理员用户才能使用此工作流
```json
{
"admin": true
}
```

## 限制某个工作流只在某群使用
- 使用此参数之后，只有在列表中的群才能使用此工作流
- 值为整数
```json
{
"group": [114514, 200224]
}
```
# 高级节点覆写操作

## append_prompt / append_negative_prompt
- 将工作流中本身带有的提示词/负面提示词加入到绘图参数中
```json
{
  "negative_prompt": {"7": {"override": {"text": "append_negative_prompt"}}},
  "output": 85,
  "prompt": {"83": {"override": {"text": "append_prompt"}}}
}
```
```json
{
  "negative_prompt": {
    "400": {"override": {"text": "append_negative_prompt"}}
  },
  "seed": [291, 127, 276],
  "image_size": {
    "395": {}, 
    "292": {"override": {"width": "upscale_0.75", "height": "upscale_0.75"}}
  },
  "output": 458,
  "prompt": {
    "399": {"override": {"text": "append_prompt"}}
  }
}
```
![emb](../image/append_prompt.png)
![emb](../image/append_prompt2.png)

## replace_prompt / replace_negative_prompt
- 将输入提示词替换到工作流中的{prompt}中
```json
{
  "prompt": {
    "25": {
      "override": {
        "text": "replace_prompt"
      }
    }
  }
}
```
![emb](../image/replace.png)
## image
- 需要输入多个图片的工作流
```json
{
  "image": {
    "50": {
      "override": {
        "image": "image_0"
      }
    },
    "52": {
      "override": {
        "image": "image_1"
      }
    }
  }
}
```
- 为50节点选择第一张图片, 52节点第二张