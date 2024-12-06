import os

from nonebot import Bot
from nonebot.adapters import Event
from nonebot.params import ShellCommandArgs
from argparse import Namespace
from itertools import islice

from .backend import ComfyUI, ComfyuiTaskQueue


async def queue_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()):

    queue_instance = ComfyuiTaskQueue(bot, event, **vars(args))
    comfyui_instance = ComfyUI(**vars(args), nb_event=event, args=args, bot=bot)

    await queue_instance.get_history_task(queue_instance.backend_url)
    task_status_dict = await queue_instance.get_task(args.task_id)

    if args.task_id:

        if task_status_dict:

            task_status = task_status_dict['status']['status_str']
            is_task_completed = '是' if task_status_dict['status']['completed'] else '否'

        else:
            task_status = '生成中'
            is_task_completed = '否'

        comfyui_instance.unimessage += f"任务{args.task_id}: \n状态：{task_status}\n是否完成: {is_task_completed}"

    if args.get_task:
        task_status_dict = await queue_instance.get_task(args.get_task)
        outputs = task_status_dict['outputs']

        backend_url = queue_instance.backend_url

        images_url = comfyui_instance.media_url.get('image', [])
        video_url = comfyui_instance.media_url.get('video', [])

        for imgs in list(outputs.values()):
            if 'images' in imgs:
                for img in imgs['images']:

                    filename = img['filename']
                    _, file_format = os.path.splitext(filename)

                    if img['subfolder'] == "":
                        url = f"{backend_url}/view?filename={filename}"
                    else:
                        url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                    if img['type'] == "temp":
                        url = f"{backend_url}/view?filename={filename}&subfolder=&type=temp"

                    images_url.append({"url": url, "file_format": file_format})

            if 'gifs' in imgs:
                for img in imgs['gifs']:
                    filename = img['filename']
                    _, file_format = os.path.splitext(filename)

                    if img['subfolder'] == "":
                        url = f"{backend_url}/view?filename={filename}"
                    else:
                        url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                    video_url.append({"url": url, "file_format": file_format})

            if 'text' in imgs:

                for img in imgs['text']:
                    comfyui_instance.unimessage += img

        comfyui_instance.media_url['image'] = images_url
        comfyui_instance.media_url['video'] = video_url

        await comfyui_instance.download_img()

        comfyui_instance.unimessage = f"这是你要找的任务:\n" + comfyui_instance.unimessage

    if args.view:

        def get_keys_from_ranges(all_task_dict, ranges_str):
            selected_keys = []
            start, end = map(int, ranges_str.split('-'))
            selected_keys.extend(list(islice(all_task_dict.keys(), start, end)))

            return selected_keys

        keys = get_keys_from_ranges(queue_instance.all_task_dict, args.index)

        id_list_str = '\n'.join(list(keys))
        comfyui_instance.unimessage = f"此ComfyUI后端上共有: {len(queue_instance.all_task_dict.keys())}个任务,\n这是指定的任务的id:\n {id_list_str}" + comfyui_instance.unimessage

    await comfyui_instance.send_all_msg()










