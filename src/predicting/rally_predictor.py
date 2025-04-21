import json
import logging
import random
from pathlib import Path

import numpy as np
import torch
from datasets.tad_dataset import build_dataset
from easydict import EasyDict
from huggingface_hub import hf_hub_download
from models import build_model
from predicting.segment_merger import SegmentMerger
from tools.youtube_downloader import VideoInfo
from torch.utils.data.dataloader import DataLoader
from torch.utils.data.sampler import SequentialSampler
from util.misc import collate_fn
from util.video_util import get_video_duration_in_seconds, get_fps, get_num_frames

from util.persistent_stqdm import PersistentSTQDM

logger = logging.getLogger(__name__)


def read_config_and_fix_randomness() -> EasyDict:
    from configs.opts import cfg
    if cfg.disable_cuda:
        cfg.act_reg = False
    seed = 42
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    return cfg


def create_info_file(video_info: VideoInfo, num_extracted_frames, duration_in_seconds):
    data = {
        f"{video_info.title}": {
            "feature_length": num_extracted_frames,
            "feature_second": duration_in_seconds,
            "feature_fps": 10
        }
    }
    file_path = Path().cwd() / "data" / f"{video_info.title}" / "input" / "badminton_img10fps_info.json"
    with open(file_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    logger.info(f"Created file {file_path}")


def create_anno_file(video_info: VideoInfo, origin_fps, duration_in_seconds):
    # TODO: investigate why it do not work without at least a pseudo segment
    data = {
        "database": {
            f"{video_info.title}": {
                "subset": "test",
                "annotations": [
                    {
                        "segment": [
                            555,
                            666
                        ],
                        "label": "rally"
                    }
                ],
                "fps": origin_fps,
                "duration": duration_in_seconds
            }
        }
    }
    file_path = Path().cwd() / "data" / f"{video_info.title}" / "input" / "badminton_annotations_with_fps_duration.json"
    with open(file_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    logger.info(f"Created file {file_path}")


class RallyPredictor:
    def __init__(self):
        self.cfg = read_config_and_fix_randomness()
        self.device = torch.device("cpu")
        self.model, self.postprocessors = self.load_model_and_postprocessors(self.cfg)

    def load_model_and_postprocessors(self, cfg: EasyDict):
        model, postprocessors = build_model(cfg)
        model.backbone.backbone.load_pretrained_weight(cfg.pretrained_model)
        model.to(self.device)
        checkpoint_path = hf_hub_download(repo_id="phubinhdang/badminton-video-trimmer", filename="model_best.pth")
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
        model.load_state_dict(checkpoint["model"], strict=False)
        n_parameters = sum(p.numel() for p in model.parameters())
        logger.info("number of params: {}".format(n_parameters))
        return model, postprocessors

    def create_additional_json_files(self, video_info: VideoInfo):
        duration_in_seconds = get_video_duration_in_seconds(video_info.video_path)
        origin_fps = get_fps(video_info.video_path)
        num_extracted_frames = get_num_frames(video_info.title)
        create_info_file(video_info, num_extracted_frames, duration_in_seconds)
        create_anno_file(video_info, origin_fps, duration_in_seconds)

    def predict(self, video_info: VideoInfo):
        match_dir = Path().cwd() / "data" / f"{video_info.title}"
        self.create_additional_json_files(video_info)
        dataset_val = build_dataset(match_dir)
        sampler_val = SequentialSampler(dataset_val)
        data_loader = DataLoader(
            dataset_val,
            self.cfg.batch_size,
            sampler=sampler_val,
            drop_last=False,
            collate_fn=collate_fn,
            num_workers=self.cfg.num_workers,
            pin_memory=False,
        )
        base_ds = dataset_val.video_dict
        # model, postprocessor, data_loader, base_ds, device, output_dir, act_reg
        # create dataset
        self.model.eval()
        segment_merger = SegmentMerger(base_ds)

        logger.info(f"Predicting rallies for video {video_info.video_path}")
        for samples, targets in PersistentSTQDM(data_loader, total=len(data_loader)):
            samples = samples.to(self.device)
            outputs = self.model((samples.tensors, samples.mask))

            # raw_res.append((outputs, targets))
            video_duration = torch.FloatTensor([t["video_duration"] for t in targets]).to(
                self.device
            )
            results = self.postprocessors(outputs, video_duration, fuse_score=self.cfg.act_reg)

            res = {target["video_id"]: output for target, output in zip(targets, results)}
            if segment_merger is not None:
                segment_merger.update(res)
        output_dir = Path().cwd() / "data" / f"{video_info.title}" / "output"
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "raw_detection.csv"
        segment_merger.dump_detection_to_json(output_path)
        logger.info(f"Wrote inference result to {output_path}")
