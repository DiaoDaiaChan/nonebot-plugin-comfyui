import os
import base64

from typing import Tuple, List, Dict
from io import BytesIO
from PIL import Image

from pathlib import Path
from huggingface_hub import hf_hub_download
import pandas as pd
import numpy as np

use_cpu = True
tf_device_name = '/gpu:0' if not use_cpu else '/cpu:0'

# https://github.com/toriato/stable-diffusion-webui-wd14-tagger


class Interrogator:
    @staticmethod
    def postprocess_tags(
        tags: Dict[str, float],
        threshold=0.35,
        additional_tags: List[str] = [],
        exclude_tags: List[str] = [],
        sort_by_alphabetical_order=False,
        add_confident_as_weight=False,
        replace_underscore=False,
        replace_underscore_excludes: List[str] = [],
        escape_tag=False
    ) -> Dict[str, float]:
        for t in additional_tags:
            tags[t] = 1.0

        tags = {
            t: c
            for t, c in sorted(
                tags.items(),
                key=lambda i: i[0 if sort_by_alphabetical_order else 1],
                reverse=not sort_by_alphabetical_order
            )
            if (
                c >= threshold
                and t not in exclude_tags
            )
        }

        new_tags = []
        for tag in list(tags):
            new_tag = tag

            if replace_underscore and tag not in replace_underscore_excludes:
                new_tag = new_tag.replace('_', ' ')

            if escape_tag:
                new_tag = tag.replace('_', '\\_')

            if add_confident_as_weight:
                new_tag = f'({new_tag}:{tags[tag]})'

            new_tags.append((new_tag, tags[tag]))
        tags = dict(new_tags)

        return tags

    def __init__(self, name: str) -> None:
        self.name = name

    def load(self):
        raise NotImplementedError()

    def unload(self) -> bool:
        unloaded = False

        if hasattr(self, 'model') and self.model is not None:
            del self.model
            unloaded = True
            print(f'Unloaded {self.name}')

        if hasattr(self, 'tags'):
            del self.tags

        return unloaded

    def interrogate(
        self,
        image: Image
    ) -> Tuple[
        Dict[str, float],  # rating confidents
        Dict[str, float]  # tag confidents
    ]:
        raise NotImplementedError()


class WaifuDiffusionInterrogator(Interrogator):
    def __init__(
        self,
        name: str,
        model_path='model.onnx',
        tags_path='selected_tags.csv',
        **kwargs
    ) -> None:
        super().__init__(name)
        self.model_path = model_path
        self.tags_path = tags_path
        self.kwargs = kwargs

    def download(self) -> Tuple[os.PathLike, os.PathLike]:
        print(f"Loading {self.name} model file from {self.kwargs['repo_id']}")

        model_path = Path(hf_hub_download(
            **self.kwargs, filename=self.model_path))
        tags_path = Path(hf_hub_download(
            **self.kwargs, filename=self.tags_path))
        return model_path, tags_path

    def load(self) -> None:
        model_path, tags_path = self.download()

        from onnxruntime import InferenceSession

        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        if use_cpu:
            providers.pop(0)

        self.model = InferenceSession(str(model_path), providers=providers)

        print(f'Loaded {self.name} model from {model_path}')

        self.tags = pd.read_csv(tags_path)

    def interrogate(
        self,
        image: Image
    ) -> Tuple[
        Dict[str, float],  # rating confidents
        Dict[str, float]  # tag confidents
    ]:
        if not hasattr(self, 'model') or self.model is None:
            self.load()

        _, height, _, _ = self.model.get_inputs()[0].shape

        image = image.convert('RGBA')
        new_image = Image.new('RGBA', image.size, 'WHITE')
        new_image.paste(image, mask=image)
        image = new_image.convert('RGB')
        image = np.asarray(image)

        image = image[:, :, ::-1]

        # 模拟`dbimutils`的make_square和smart_resize功能
        image = self.make_square(image, height)
        image = self.smart_resize(image, height)
        image = image.astype(np.float32)
        image = np.expand_dims(image, 0)

        input_name = self.model.get_inputs()[0].name
        label_name = self.model.get_outputs()[0].name
        confidents = self.model.run([label_name], {input_name: image})[0]

        tags = self.tags[:][['name']]
        tags['confidents'] = confidents[0]

        ratings = dict(tags[:4].values)
        tags = dict(tags[4:].values)

        return ratings, tags

    @staticmethod
    def make_square(image, size):
        old_size = image.shape[:2]
        ratio = float(size) / max(old_size)
        new_size = tuple([int(x * ratio) for x in old_size])
        image = Image.fromarray(image)
        image = image.resize(new_size, Image.LANCZOS)
        new_image = Image.new("RGB", (size, size))
        new_image.paste(image, ((size - new_size[0]) // 2,
                                (size - new_size[1]) // 2))
        return np.array(new_image)

    @staticmethod
    def smart_resize(image, size):
        image = Image.fromarray(image)
        image = image.resize((size, size), Image.LANCZOS)
        return np.array(image)


def tagger_main(base64_img, threshold, wd_instance, ntags=[]):

    image_data = base64.b64decode(base64_img)
    image = Image.open(BytesIO(image_data))

    ratings, tags = wd_instance.interrogate(image)
    processed_tags = Interrogator.postprocess_tags(
        tags=tags,
        threshold=threshold,
        additional_tags=['best quality', 'highres'],
        exclude_tags=['lowres'] + ntags,
        sort_by_alphabetical_order=False,
        add_confident_as_weight=True,
        replace_underscore=True,
        replace_underscore_excludes=[],
        escape_tag=False
    )

    def process_dict(input_dict):
        processed_dict = {}
        for key, value in input_dict.items():
            cleaned_key = key.strip('()').split(':')[0]
            processed_dict[cleaned_key] = value
        return processed_dict

    processed_tags = process_dict(processed_tags)
    return ratings | processed_tags
