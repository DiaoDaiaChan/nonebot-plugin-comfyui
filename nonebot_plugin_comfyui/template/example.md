# 本章节你能通过一些实际的命令来学习使用本插件

## 基础生图命令/基础知识
- 插件基础命令 prompt [正面提示词] [参数] [参数值]
- 支持的参数会显示在帮助菜单上
- 例如 prompt 1girl -t 114
- ⚠️ 默认不支持中文提示词
- ⚠️ 提示词中如果包含单引号, 需要用双引号括起来, 例如 prompt "girl's" 

## 😋查看工作流/使用不同的工作流进行生成
- 命令: 查看工作流  来查看插件已经加载的工作流
- 之后, 我们就可以使用 -wf (工作流的编号/名称, 支持模糊匹配) 来调用工作流了!
```
prompt 1girl -wf 1  / prompt 1girl -wf flux
```
- 有的时候工作流可以被注册为命令! (使用对应的命令会自动调用工作流)
- 在查看工作流命令返回的图片以及帮助菜单中均有提到
- 假如注册了以下命令
```
打标 [图片] (自动调用打标工作流)
sdxl 1girl -r 1024x1024 (注册了一个sdxl命令, 同时, 各种参数都是生效的)
```

## 🥰调整图片的分辨率
- 调整图片的分辨率有三种参数
- 在没有输入的时候, 默认使用 832x1216
- 使用 -ar 图片宽:高 , 这个参数会根据输入的宽高比, 根据设置的基础分辨率来调整图片宽高, 例如:
```
prompt 1girl -ar 1:2 (生成1:2的宽图)
```
- 使用 -高 832 -宽 1216, 使用这两个参数来决定, 例如 
```
prompt 1girl -高 1024 -宽 1024
```
- 使用 -r (预设的分辨率组合/宽x高), 例如 prompt 1girl -r 1024x1024, 以及 prompt 1girl -r l (使用预设的l分辨率landscape, 默认是1216x832, 支持怎样的预设可以在帮助菜单上看到)
```
prompt 1girl -r 1024x1024
prompt 1girl -r l
```

## 🤤一次生成多张图片(小馋猫)
- 插件支持你一次生成多张图片
- 使用 -b 数量, 来决定一次生成几张图片(一般设置这个不要太贪心, 容易爆显存, 推荐使用 -bc参数)
- 使用 -bc 数量, 来决定总共生成几次图片(推荐使用)
- 推荐使用 -f (图片转转发消息) -con (多后端同时生图) 组合技
```
prompt 1girl -b 2 -bc 10 -f -con  (生成10次图片, 每次两张, 转发消息, 并发生图)
```

## 😡你是高级玩家? 使用自己的提示词和负面提示词
- 有时候为了默认生图效果, 插件会默认自带正面以及负面提示词
- 使用 -o 不使用默认的正面提示词
- 使用 -on 不使用默认的负面提示词
```
prompt 1girl -o (不使用默认正面提示词)
prompt 1girl -o -on (不使用默认正面以及负面提示词) 
```

## 😊任务id的作用?
- 使用插件进行生成的时候会返回命令id, 它能追踪的进度/获取任务的结果
- 要获取获取任务进度, 我们需要任务id以及后端索引
```
queue -i 70bfe5d6-837a-471a-9ff1-e8e98370696d -be 0 (返回如下)

任务70bfe5d6-837a-471a-9ff1-e8e98370696d: 
状态：生成中
是否完成: 否
```
- 获取任务结果
```
queue -get 任务id -be 后端索引
```
- 任务执行太久被卡住了?
```
queue -stop -be 后端索引 (停止指定后端的当前任务生成)
```
- 清楚所有任务队列 (未执行的命令)
```
queue -c -be 后端索引 (停止指定后端的所有任务列表, 不影响正在生成的)
```
- 把某个任务从队列中删除 (删除未执行的任务队列)
```
queue -d 任务id -be 后端索引
```
- 获取后端上的所有任务id
```
queue -v -be 后端索引 (默认查看前10个)
queue -v -index 0-20 -be 后端索引 (查看第0-20个)
```