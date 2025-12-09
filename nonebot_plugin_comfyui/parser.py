import argparse

from .config import config
from nonebot.rule import ArgumentParser
from nonebot import logger

comfyui_parser = ArgumentParser()

comfyui_parser.add_argument("prompt", nargs="*", help="正面提示词 example:prompt 1girl", type=str)
comfyui_parser.add_argument("-u", "-负面", nargs="*", dest="negative_prompt example:prompt -u '低质量'", type=str,
                            help="负面提示词")
comfyui_parser.add_argument("-ar", "-画面比例", dest="accept_ratio", type=str,
                            help="画幅比例 example:prompt -ar 16:9")
comfyui_parser.add_argument("-s", "-种子", dest="seed", type=int, help="种子 example:prompt -s 200224")
comfyui_parser.add_argument("-t", "-步数", dest="steps", type=int, help="迭代步数 example:prompt -t 28 ")
comfyui_parser.add_argument("-cfg", dest="cfg_scale", type=float, help="CFG scale example:prompt -cfg 7.5")
comfyui_parser.add_argument("-n", "-去噪", dest="denoise_strength", type=float,
                            help="降噪强度 example:prompt -n 1.0")
comfyui_parser.add_argument("-高", "--height", dest="height", type=int, help="图片的高度 example:prompt -高1216")
comfyui_parser.add_argument("-宽", "--width", dest="width", type=int, help="图片的宽度 example:prompt -宽832")
comfyui_parser.add_argument("-o", dest="override", action="store_true",
                            help="不使用预设的正面提示词 example:prompt -o")
comfyui_parser.add_argument("-on", dest="override_ng", action="store_true",
                            help="不使用预设的负面提示词 example:prompt -on")
comfyui_parser.add_argument("-wf", "-工作流", dest="work_flows", type=str,
                                help="选择工作流 example:prompt -wf 1 / prompt -wf flux", default=config.comfyui_default_workflows)
comfyui_parser.add_argument("-sp", "-采样器", dest="sampler", type=str, help="采样器 example:prompt -sp euler")
comfyui_parser.add_argument("-sch", "-调度器", dest="scheduler", type=str, help="调度器 example:prompt -sch normal")
comfyui_parser.add_argument("-b", "-数量", dest="batch_size", type=int, help="每批数量 example:prompt -b 1",
                            default=1)
comfyui_parser.add_argument("-bc", "-批数", dest="batch_count", type=int, help="批数 example:prompt -bc 1",
                            default=1)
comfyui_parser.add_argument("-m", "-模型", dest="model", type=str, help="模型 example:prompt -m sdbase.ckpt")
comfyui_parser.add_argument("-be", "-后端", dest="backend", type=str,
                            help="后端索引或者url example:prompt -be 0 / prompt -be 'http://127.0.0.1:8388'")
comfyui_parser.add_argument("-f", "-转发", dest="forward", action="store_true",
                            help="使用转发消息 example:prompt -f")
comfyui_parser.add_argument("-gif", dest="gif", action="store_true",
                            help="使用gif图片进行图片输入 example:prompt -gif")
comfyui_parser.add_argument("-con", "-并发", dest="concurrency", action="store_true",
                            help="并发使用多后端生图,和-bc一起使用 example:prompt -con -bc 3")
comfyui_parser.add_argument("-r", "-shape", "-分辨率", dest="shape", type=str,
                            help="自定义分辨率的比例字符串 example:prompt -r p / prompt -r 960x1920")
comfyui_parser.add_argument("-sil", "-静默", dest="silent", action="store_true",
                            help="不返回各种提示消息 example:prompt -sil")
comfyui_parser.add_argument("-notice", "-通知", dest="notice", action="store_true",
                            help="工作流执行完成的时候私聊通知, 适用于长工作流 example:prompt -notice")
comfyui_parser.add_argument("-nt", "-不翻译", dest="no_trans", action="store_true",
                            help="不翻译中文输入 example:prompt -nt")
comfyui_parser.add_argument("-llm预设", "-llm", dest="llm_preset", type=int, help="通过llm处理prompt时使用的提示词预设 example:prompt -llm 1",
                            default=1)

queue_parser = ArgumentParser()

queue_parser.add_argument("--track", "-t", "-追踪", "--track_task", dest="track", action="store_true", help="后端当前的任务")
queue_parser.add_argument("-d", "--delete", dest="delete", type=str, help="从队列中清除指定的任务")
queue_parser.add_argument("-c", "--clear", "-clear", dest="clear", action="store_true", help="清除后端上的所有任务")
queue_parser.add_argument("-stop", "--stop", dest="stop", action="store_true", help="停止当前生成")

queue_parser.add_argument("-be", "--后端", dest="backend", type=str, help="后端索引或者url", default="0")
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

    comfyui_parser.add_argument("prompt", nargs="*", help="正面提示词 example:prompt 1girl", type=str)
    comfyui_parser.add_argument("-u", "-负面", nargs="*", dest="negative_prompt", type=str ,help="负面提示词 example:prompt -u ")
    comfyui_parser.add_argument("-ar", "-画面比例", dest="accept_ratio", type=str,
                                help="画幅比例 example:prompt -ar 16:9")
    comfyui_parser.add_argument("-s", "-种子", dest="seed", type=int, help="种子 example:prompt -s 200224")
    comfyui_parser.add_argument("-t", "-步数", dest="steps", type=int, help="迭代步数 example:prompt -t 28 ")
    comfyui_parser.add_argument("-cfg", dest="cfg_scale", type=float, help="CFG scale example:prompt -cfg 7.5")
    comfyui_parser.add_argument("-n", "-去噪", dest="denoise_strength", type=float,
                                help="降噪强度 example:prompt -n 1.0")
    comfyui_parser.add_argument("-高", "--height", dest="height", type=int, help="图片的高度 example:prompt -高1216")
    comfyui_parser.add_argument("-宽", "--width", dest="width", type=int, help="图片的宽度 example:prompt -宽832")
    comfyui_parser.add_argument("-o", dest="override", action="store_true",
                                help="不使用预设的正面提示词 example:prompt -o")
    comfyui_parser.add_argument("-on", dest="override_ng", action="store_true",
                                help="不使用预设的负面提示词 example:prompt -on")
    comfyui_parser.add_argument("-wf", "-工作流", dest="work_flows", type=str,
                                help="选择工作流 example:prompt -wf 1 / prompt -wf flux", default=wf)
    comfyui_parser.add_argument("-sp", "-采样器", dest="sampler", type=str, help="采样器 example:prompt -sp euler")
    comfyui_parser.add_argument("-sch", "-调度器", dest="scheduler", type=str, help="调度器 example:prompt -sch normal")
    comfyui_parser.add_argument("-b", "-数量", dest="batch_size", type=int, help="每批数量 example:prompt -b 1",
                                default=1)
    comfyui_parser.add_argument("-bc", "-批数", dest="batch_count", type=int, help="批数 example:prompt -bc 1",
                                default=1)
    comfyui_parser.add_argument("-m", "-模型", dest="model", type=str, help="模型 example:prompt -m sdbase.ckpt")
    comfyui_parser.add_argument("-be", "-后端", dest="backend", type=str,
                                help="后端索引或者url example:prompt -be 0 / prompt -be 'http://127.0.0.1:8388'")
    comfyui_parser.add_argument("-f", "-转发", dest="forward", action="store_true",
                                help="使用转发消息 example:prompt -f")
    comfyui_parser.add_argument("-gif", dest="gif", action="store_true",
                                help="使用gif图片进行图片输入 example:prompt -gif")
    comfyui_parser.add_argument("-con", "-并发", dest="concurrency", action="store_true",
                                help="并发使用多后端生图,和-bc一起使用 example:prompt -con -bc 3")
    comfyui_parser.add_argument("-r", "-shape", "-分辨率", dest="shape", type=str,
                                help="自定义分辨率的比例字符串 example:prompt -r p / prompt -r 960x1920")
    comfyui_parser.add_argument("-sil", "-静默", dest="silent", action="store_true",
                                help="不返回各种提示消息 example:prompt -sil")
    comfyui_parser.add_argument("-nt", "-不翻译", dest="no_trans", action="store_true",
                                help="不翻译中文输入 example:prompt -nt")
    comfyui_parser.add_argument("-notice", "-通知", dest="notice", action="store_true",
                                help="工作流执行完成的时候私聊通知, 适用于长工作流 example:prompt -notice")
    comfyui_parser.add_argument("-llm预设", "-llm", dest="llm_preset", type=int,
                                help="通过llm处理prompt时使用的提示词预设 example:prompt -llm 1",
                                default=1)

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

