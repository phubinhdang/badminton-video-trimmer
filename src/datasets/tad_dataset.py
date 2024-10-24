# ------------------------------------------------------------------------
# TadTR: End-to-end Temporal Action Detection with Transformer
# Copyright (c) 2021 - 2022. Xiaolong Liu.
# ------------------------------------------------------------------------

"""Universal TAD Dataset loader."""

import json
import logging
import os.path as osp

import h5py
import numpy as np
import torch
import torch.utils.data

from util.segment_ops import segment_t1t2_to_cw
from .data_utils import get_dataset_dict, load_feature
from .e2e_lib import make_img_transform, load_video_frames


from datasets.e2e_lib.videotransforms import (
    GroupResizeShorterSide,
    GroupResize,
    GroupCenterCrop,
    GroupNormalize,
)

# from util.config import cfg


class TADDataset(torch.utils.data.Dataset):
    def __init__(
        self,
        subset,
        mode,
        feature_info,
        ann_file,
        ft_info_file,
        transforms,
        mem_cache=False,
        online_slice=False,
        slice_len=None,
        slice_overlap=0,
        binary=False,
        padding=True,
        input_type="feature",
        img_stride=1,
    ):
        """TADDataset
        Parameters:
            subset: train/val/test
            mode: train, or test
            feature_info: basic info of video features, e.g. path, file format, filename template
            ann_file: path to the ground truth file
            ft_info_file: path to the file that describe other information of each video
            transforms: which transform to use
            mem_cache: cache features of the whole dataset into memory.
            binary: transform all gt to binary classes. This is required for training a class-agnostic detector
            padding: whether to pad the input feature to `slice_len`

        """

        super().__init__()
        self.feature_info = feature_info
        self.ann_file = ann_file
        self.ft_info_file = ft_info_file
        self.subset = subset
        self.online_slice = online_slice
        self.slice_len = slice_len
        self.slice_overlap = slice_overlap
        self.padding = padding
        self.mode = mode
        self.transforms = transforms
        print("Use data transform {}".format(self.transforms))
        self.binary = binary
        self.is_image_input = input_type == "image"
        self.mem_cache = mem_cache
        self.img_stride = img_stride

        self._prepare()

    def _get_classes(self, anno_dict):
        """get class list from the annotation dict"""
        if "classes" in anno_dict:
            classes = anno_dict["classes"]
        else:
            database = anno_dict["database"]
            all_gts = []
            for vid in database:
                all_gts += database[vid]["annotations"]
            classes = list(sorted({x["label"] for x in all_gts}))
        return classes

    def _prepare(self):
        """parse annotation file"""
        anno_dict = json.load(open(self.ann_file))
        # classes = ['rally]
        self.classes = self._get_classes(anno_dict)

        self.video_dict, self.video_list = get_dataset_dict(
            self.ft_info_file,
            self.ann_file,
            self.subset,
            mode=self.mode,
            online_slice=self.online_slice,
            slice_len=self.slice_len,
            slice_overlap=self.slice_overlap,
            ignore_empty=self.mode == "train",
            return_id_list=True,
        )

        # video_list = self.video_dict.keys()
        # self.video_list = list(sorted(video_list))

        logging.info(
            "{} subset video numbers: {}".format(self.subset, len(self.video_list))
        )
        self.anno_dict = anno_dict

        self.cached_data = {}

        # if the features of all videos is saved in one hdf5 file (all in one), e.g. TSP features
        self.all_video_data = {}
        feature_info = self.feature_info
        fn_templ = feature_info["fn_templ"]
        src_video_list = {self.video_dict[k]["src_vid_name"] for k in self.video_list}
        #
        if feature_info.get("all_in_one", False):
            data = h5py.File(feature_info["local_path"][self.subset])
            for k in src_video_list:
                self.all_video_data[k] = np.array(data[fn_templ % k]).T
            if not self.online_slice:
                self.cached_data = self.all_video_data

    def __len__(self):
        return len(self.video_list)

    def _get_video_data(self, index):
        if self.is_image_input:
            return self._get_img_data(index)
        else:
            return self._get_feature_data(index)

    def _get_feature_data(self, index):
        video_name = self.video_list[index]
        # directly fetch from memory
        if video_name in self.cached_data:
            video_data = self.cached_data[video_name]
            return torch.Tensor(video_data).float().contiguous()

        src_vid_name = self.video_dict[video_name]["src_vid_name"]
        # retrieve feature info
        feature_info = self.feature_info
        # "ft" is short for "feature"
        local_ft_dir = feature_info["local_path"]
        ft_format = feature_info["format"]
        local_ft_path = local_ft_dir if local_ft_dir else None
        # the shape of feature sequence, can be TxC (in most cases) or CxT
        shape = feature_info.get("shape", "TC")

        if src_vid_name in self.all_video_data:
            feature_data = self.all_video_data[src_vid_name].T

        else:
            feature_data = load_feature(local_ft_path, ft_format, shape)

        feature_data = feature_data.T  # T x C to C x T.

        if self.online_slice:
            slice_start, slice_end = [int(x) for x in video_name.split("_")[-2:]]
            assert slice_end > slice_start
            assert slice_start < feature_data.shape[1]
            feature_data = feature_data[:, slice_start:slice_end]

            if self.padding and feature_data.shape[1] < self.slice_len:
                diff = self.slice_len - feature_data.shape[1]
                feature_data = np.pad(
                    feature_data, ((0, 0), (0, diff)), mode="constant"
                )

                # IMPORATANT: if padded is done, the length info must be modified
                self.video_dict[video_name]["feature_length"] = self.slice_len
                self.video_dict[video_name]["feature_second"] = (
                    self.slice_len / self.video_dict[video_name]["feature_fps"]
                )

        if self.mem_cache and video_name not in self.cached_data:
            self.cached_data[video_name] = feature_data

        feature_data = torch.Tensor(feature_data).float().contiguous()
        return feature_data

    def _get_img_data(self, index):
        video_name = self.video_list[index]

        feature_info = self.feature_info

        frame_dir = feature_info["local_path"]

        if self.online_slice:
            # for THUMOS14
            slice_start, slice_end = [int(x) for x in video_name.split("_")[-2:]]
            start_idx = slice_start

            # clip_length = end_frame_index - start_frame_index + 1. It counts skipped frames when img_stride > 1
            dst_clip_length = self.slice_len
            # clip_length: the argument passed to the img loader
            clip_length = slice_end - slice_start

            imgs = load_video_frames(
                frame_dir, start_idx + 1, clip_length, self.img_stride
            )
            assert len(imgs) != 0

            # the actual number of frames
            dst_sample_frames = dst_clip_length // self.img_stride

            if len(imgs) < dst_sample_frames:
                # try:
                imgs = np.pad(
                    imgs,
                    ((0, dst_sample_frames - len(imgs)), (0, 0), (0, 0), (0, 0)),
                    mode="constant",
                    constant_values=128,
                )
                # except:
                #     pdb.set_trace()
                self.video_dict[video_name]["feature_length"] = self.slice_len
                self.video_dict[video_name]["feature_second"] = (
                    self.slice_len / self.video_dict[video_name]["feature_fps"]
                )
        else:
            start_idx = 0
            video_length = self.video_dict[video_name]["feature_length"]
            dst_clip_length = feature_info.get("num_frames", None)
            clip_length = (
                min(video_length, dst_clip_length)
                if dst_clip_length is not None
                else video_length
            )

            imgs = load_video_frames(
                frame_dir, start_idx + 1, clip_length, self.img_stride
            )

            # On ActivityNet/HACS, we use ffmpeg to decode a video into fixed number of frames.
            # However, the actual number of decoded frames may differ from the desired number.

            if dst_clip_length:
                dst_sample_frames = dst_clip_length // self.img_stride

                if len(imgs) < dst_sample_frames:
                    imgs = np.pad(
                        imgs,
                        ((0, dst_sample_frames - len(imgs)), (0, 0), (0, 0), (0, 0)),
                        mode="constant",
                        constant_values=128,
                    )

                else:
                    imgs = imgs[:dst_sample_frames, ...]
        try:
            imgs = self.transforms(imgs)
        except Exception as e:
            # traceback.print_exc()
            raise IOError(
                "failed to transform {} from {}".format(video_name, frame_dir)
            )

        imgs = torch.from_numpy(
            np.ascontiguousarray(imgs.transpose([3, 0, 1, 2]))
        ).float()  # thwc -> cthw
        return imgs

    def _get_train_label(self, video_name):
        """get normalized target"""
        video_info = self.video_dict[video_name]
        video_labels = video_info["annotations"]
        feature_second = video_info["feature_second"]

        target = {
            "segments": [],
            "labels": [],
            "orig_labels": [],
            "video_id": video_name,
            "video_duration": feature_second,  # only used in inference
            "feature_fps": video_info["feature_fps"],
        }
        for j in range(len(video_labels)):
            tmp_info = video_labels[j]

            segment = tmp_info["segment"]
            # special rule for thumos14, treat ambiguous instances as negatives
            if tmp_info["label"] not in self.classes:
                continue
            # the label id of first forground class is 0
            label_id = self.classes.index(tmp_info["label"])
            target["orig_labels"].append(label_id)

            if self.binary:
                label_id = 0
            target["segments"].append(segment)
            target["labels"].append(label_id)

        # normalized the coordinate
        target["segments"] = np.array(target["segments"]) / feature_second

        if len(target["segments"]) > 0:
            target["segments"] = segment_t1t2_to_cw(target["segments"])

            # convert to torch format
            for k, dtype in zip(["segments", "labels"], ["float32", "int64"]):
                if not isinstance(target[k], torch.Tensor):
                    target[k] = torch.from_numpy(np.array(target[k], dtype=dtype))

        return target

    def __getitem__(self, index):
        # index = index % len(self.video_list)
        video_data = self._get_video_data(index)
        video_name = self.video_list[index]

        target = self._get_train_label(video_name)

        return video_data, target


def make_img_transform(resize, crop, mean, std, keep_asr=True):
    from torchvision.transforms import Compose

    if isinstance(resize, (list, tuple)):
        resize_trans = GroupResize(resize)
    else:
        if keep_asr:
            assert isinstance(
                resize, int
            ), "if keep asr, resize must be a single integer"
            resize_trans = GroupResizeShorterSide(resize)
        else:
            resize_trans = GroupResize((resize, resize))

    transforms = [
        resize_trans,
        GroupCenterCrop(crop),
    ]
    transforms.append(GroupNormalize(mean, std, to_rgb=True))
    return Compose(transforms)


def build_dataset(match_dir):
    """build TADDataset"""
    # subset_mapping = {"train": "val", "val": "test"}
    subset = "test"
    mode = "test"
    feature_info = {
        "local_path": f"{match_dir}/input/img10fps",
        "format": "jpg",
        "fn_templ": "%s",
        "img_fn_templ": "/img_%07d.jpg",
    }
    ann_file = f"{match_dir}/input/badminton_annotations_with_fps_duration.json"
    ft_info_file = f"{match_dir}/input/badminton_img10fps_info.json"
    mean, std = ([123.675, 116.28, 103.53], [58.395, 57.12, 57.375])
    transforms = make_img_transform(
        mean=mean,
        std=std,
        resize=110,
        crop=96,
        keep_asr=True,
    )
    return TADDataset(
        subset,
        mode,
        feature_info,
        ann_file,
        ft_info_file,
        transforms,
        online_slice=True,
        slice_len=256,
        slice_overlap=0.25,
        binary=True,
        input_type="image",
    )
