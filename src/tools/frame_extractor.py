import logging
from pathlib import Path

import ffpb
from tools.youtube_downloader import VideoInfo
from util.persistent_stqdm import PersistentSTQDM

logger = logging.getLogger(__name__)


class FrameExtractor:
    def __init__(self, fps: int = 10):
        self.fps = fps

    def extract_frames(self, video: VideoInfo):
        logger.info(f"Extracting frames from downloaded video: {video.video_path}")
        video_frames_dir = Path.cwd() / "data" / f"{video.title}" / "input" / f"img{self.fps}fps"
        video_frames_dir.mkdir(parents=True, exist_ok=True)
        argv = ["-i", f"{video.video_path}", "-filter:v", f"fps=fps={self.fps}", f"{video_frames_dir}/img_%07d.jpg"]
        try:
            ffpb.main(argv=argv, tqdm=PersistentSTQDM)
            logger.info(f"Finished extracting frames to {video_frames_dir}")
        except Exception as e:
            logger.error(f"Command ffmpeg {' '.join(argv)} caused error {e}")
