import logging
import os
from pathlib import Path

import ffpb
from tqdm import tqdm

from src.tools.youtube_downloader import VideoInfo

logger = logging.getLogger(__name__)


class FrameExtractor:
    def __init__(self, fps: int = 10):
        user_home_dir = os.path.expanduser("~")
        self.img_dir = Path(user_home_dir) / "tad" / f"img{fps}fps"
        self.fps = fps

    def extract_frames(self, video: VideoInfo):
        logger.info(f"Extracting frames from downloaded video: {video.video_path}")
        video_img_dir = self.img_dir / video.title
        if not video_img_dir.exists():
            video_img_dir.mkdir(parents=True, exist_ok=True)
        argv = ["-i", f"{video.video_path}", "-filter:v", f"fps=fps={self.fps}", f"{video_img_dir}/img_%07d.jpg"]
        try:
            ffpb.main(argv=argv, tqdm=tqdm)
            logger.info(f"Finished extracting frames to {video_img_dir}")
        except Exception as e:
            logger.error(f"Command ffmpeg {' '.join(argv)} caused error {e}")
