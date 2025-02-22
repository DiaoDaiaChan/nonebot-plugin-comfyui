import argparse

from nonebot.rule import ArgumentParser
from nonebot import logger

comfyui_parser = ArgumentParser()

comfyui_parser.add_argument("prompt", nargs="*", help="标签", type=str)
comfyui_parser.add_argument("-u", "-U", nargs="*", dest="negative_prompt", type=str, help="Negative prompt")
comfyui_parser.add_argument("--ar", "-ar", dest="accept_ratio", type=str, help="Accept ratio")
comfyui_parser.add_argument("--s", "-s", dest="seed", type=int, help="Seed")
comfyui_parser.add_argument("--steps", "-steps", "-t", dest="steps", type=int, help="Steps")
comfyui_parser.add_argument("--cfg", "-cfg", dest="cfg_scale", type=float, help="CFG scale")
comfyui_parser.add_argument("-n", "--n", dest="denoise_strength", type=float, help="Denoise strength")
comfyui_parser.add_argument("-高", "--height", dest="height", type=int, help="Height")
comfyui_parser.add_argument("-宽", "--width", dest="width", type=int, help="Width")
comfyui_parser.add_argument("-v", dest="video", action="store_true", help="Video output flag")
comfyui_parser.add_argument("-o", dest="override", action="store_true", help="不使用预设的正面")
comfyui_parser.add_argument("-on", dest="override_ng", action="store_true", help="不使用预设的负面提示词")
comfyui_parser.add_argument("-wf", "--work-flows", dest="work_flows", type=str, help="Workflows")
comfyui_parser.add_argument("-sp", "--sampler", dest="sampler", type=str, help="采样器")
comfyui_parser.add_argument("-sch", "--scheduler", dest="scheduler", type=str, help="调度器")
comfyui_parser.add_argument("-b", "--batch_size", dest="batch_size", type=int, help="每批数量", default=1)
comfyui_parser.add_argument("-bc", "--batch_count", dest="batch_count", type=int, help="批数", default=1)
comfyui_parser.add_argument("-m", "--model", dest="model", type=str, help="模型")
comfyui_parser.add_argument("-be", "--backend", dest="backend", type=str, help="后端索引或者url")
comfyui_parser.add_argument("-f", dest="forward", action="store_true", help="使用转发消息")
comfyui_parser.add_argument("-gif", dest="gif", action="store_true", help="使用gif图片进行图片输入")
comfyui_parser.add_argument("-con", "-并发", dest="concurrency", action="store_true", help="并发使用多后端生图")
comfyui_parser.add_argument("-r", "-shape", dest="shape", type=str, help="自定义的比例字符串")

queue_parser = ArgumentParser()

queue_parser.add_argument("--track", "-t", "-追踪", "--track_task", dest="track", action="store_true", help="后端当前的任务")
queue_parser.add_argument("-d", "--delete", dest="delete", type=str, help="从队列中清除指定的任务")
queue_parser.add_argument("-c", "--clear", "-clear", dest="clear", action="store_true", help="清除后端上的所有任务")
queue_parser.add_argument("-stop", "--stop", dest="stop", action="store_true", help="停止当前生成")

queue_parser.add_argument("-be", "--backend", dest="backend", type=str, help="后端索引或者url", default="0")
queue_parser.add_argument("-i", "--id", dest="task_id", type=str, help="需要查询的任务id")
queue_parser.add_argument("-v", "--view", dest="view", action="store_true", help="查看历史任务")

queue_parser.add_argument("-g", "--get", "-get", dest="get_task", type=str, help="需要获取具体信息的任务")
queue_parser.add_argument("-index", "--index", dest="index", type=str, help="需要获取的任务id范围", default="0-10")
# queue_parser.add_argument("-m", "--media", dest="media_type", type=str, help="需要获取具体信息的任务的输出类型", default='image')

api_parser = ArgumentParser()
api_parser.add_argument("-g", "--get", "-get", dest="get", type=str, help="获取所有节点", default="all")
api_parser.add_argument("-be", "--backend", dest="backend", type=str, help="后端索引或者url", default="0")


async def rebuild_parser(wf, reg_args: dict | None = None):

    comfyui_parser = ArgumentParser()

    comfyui_parser.add_argument("prompt", nargs="*", help="标签", type=str)
    comfyui_parser.add_argument("-u", "-U", nargs="*", dest="negative_prompt", type=str, help="Negative prompt")
    comfyui_parser.add_argument("--ar", "-ar", dest="accept_ratio", type=str, help="Accept ratio")
    comfyui_parser.add_argument("--s", "-s", dest="seed", type=int, help="Seed")
    comfyui_parser.add_argument("--steps", "-steps", "-t", dest="steps", type=int, help="Steps")
    comfyui_parser.add_argument("--cfg", "-cfg", dest="cfg_scale", type=float, help="CFG scale")
    comfyui_parser.add_argument("-n", "--n", dest="denoise_strength", type=float, help="Denoise strength")
    comfyui_parser.add_argument("-高", "--height", dest="height", type=int, help="Height")
    comfyui_parser.add_argument("-宽", "--width", dest="width", type=int, help="Width")
    comfyui_parser.add_argument("-v", dest="video", action="store_true", help="Video output flag")
    comfyui_parser.add_argument("-o", dest="override", action="store_true", help="不使用预设的正面")
    comfyui_parser.add_argument("-on", dest="override_ng", action="store_true", help="不使用预设的负面提示词")
    comfyui_parser.add_argument("-wf", "--work-flows", dest="work_flows", type=str, help="Workflows",
                                default=wf)
    comfyui_parser.add_argument("-sp", "--sampler", dest="sampler", type=str, help="采样器")
    comfyui_parser.add_argument("-sch", "--scheduler", dest="scheduler", type=str, help="调度器")
    comfyui_parser.add_argument("-b", "--batch_size", dest="batch_size", type=int, help="每批数量", default=1)
    comfyui_parser.add_argument("-bc", "--batch_count", dest="batch_count", type=int, help="每批数量",
                                default=1)
    comfyui_parser.add_argument("-m", "--model", dest="model", type=str, help="模型")
    comfyui_parser.add_argument("-be", "--backend", dest="backend", type=str, help="后端索引或者url")
    comfyui_parser.add_argument("-f", dest="forward", action="store_true", help="使用转发消息")
    comfyui_parser.add_argument("-gif", dest="gif", action="store_true", help="使用gif图片进行图片输入")
    comfyui_parser.add_argument("-con", "-并发", dest="concurrency", action="store_true",
                                help="并发使用多后端生图")
    comfyui_parser.add_argument("-r", "-shape", dest="shape", type=str, help="自定义的比例字符串")

    if reg_args:

        type_mapping = {
            "int": int,
            "str": str,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
        }

        for node_arg in list(reg_args.values()):

            for arg in node_arg['args']:
                if arg["type"] in type_mapping:
                    arg["type"] = type_mapping[arg["type"]]
                    flags = arg["name_or_flags"]

                    del arg["name_or_flags"]
                    if "dest_to_value" in arg:
                        del arg["dest_to_value"]

                    if "preset" in arg:
                        arg["type"] = str
                        del arg["preset"]

                    try:
                        comfyui_parser.add_argument(*flags, **arg)
                        logger.info(f"成功注册命令参数: {arg['dest']}")
                    except argparse.ArgumentError as e:
                        logger.warning(f"检测到参数冲突: {e}. 尝试移除冲突的参数并重新添加.")

                        for flag in flags:
                            if flag.startswith('-'):
                                comfyui_parser._remove_action(comfyui_parser._option_string_actions.pop(flag))

                        comfyui_parser.add_argument(*flags, **arg)
                        logger.info(f"成功注册命令参数: {arg['dest']} (冲突已解决)")

    return comfyui_parser

