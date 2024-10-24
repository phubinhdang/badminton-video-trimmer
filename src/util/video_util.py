import os
import subprocess
from pathlib import Path


def get_video_duration_in_seconds(video_path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return float(result.stdout.strip())


def get_fps(video_path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # extracting, for example 30 from 30/1
    return int(result.stdout.split("/")[0])


def get_num_frames(video_title) -> int:
    frames_dir = Path().cwd() / "data" / video_title / 'input' / "img10fps"
    return len(os.listdir(str(frames_dir)))
