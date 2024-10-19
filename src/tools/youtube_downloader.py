import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from pytubefix import YouTube
from tqdm import tqdm

logger = logging.getLogger(__name__)

progress_bar = None


def custom_on_progress(stream, chunk, bytes_remaining):
    global progress_bar
    filesize = stream.filesize
    bytes_received = filesize - bytes_remaining

    # Update progress bar with absolute number of bytes received
    progress_bar.n = bytes_received
    progress_bar.refresh()


@dataclass
class VideoInfo:
    url: str
    title: str
    video_path: str
    audio_path: str


class YoutubeDownloader:
    def __init__(self):
        user_home_dir = os.path.expanduser("~")
        self.download_dir = Path(user_home_dir) / "tad" / "downloads"
        if not self.download_dir.exists():
            self.download_dir.mkdir(parents=True, exist_ok=True)

    def download(self, video_url, resolution="720p") -> VideoInfo:
        global progress_bar
        try:
            yt = YouTube(video_url, on_progress_callback=custom_on_progress)
            title = yt.title
            title = re.sub(r'[^A-Za-z0-9\s]', '', title)
            title = re.sub(r'\s+', '_', title)
            logger.info(yt)
            # progressive=True mean audio and video in a same stream, but it only available at 360p
            # so we have to download those separately
            streams = yt.streams.filter(progressive=False).order_by('resolution').desc()
            available_resolutions = [s.resolution for s in streams]
            if resolution in available_resolutions:
                res = resolution
            elif not available_resolutions:
                res = available_resolutions[0]
            video_stream = yt.streams.filter(resolution=res, progressive=False).first()
            video_file_name = f"{title}.mp4"

            progress_bar = tqdm(total=video_stream.filesize, unit="B", unit_scale=True, desc="Downloading video")

            video_file_path = video_stream.download(output_path=str(self.download_dir), filename=video_file_name,
                                                    skip_existing=True)
            progress_bar.close()

            if video_file_path:
                logger.info(f"Downloaded video from {video_url} with resolution of {video_stream.resolution}")
            else:
                logger.error(
                    f"Error while downloading video from {video_url} with resolution of {video_stream.resolution}")
            audio_stream = yt.streams.filter(progressive=True).first()
            progress_bar = tqdm(total=audio_stream.filesize, unit="B", unit_scale=True, desc="Downloading audio")
            audio_file_name = f"{title}_audio.mp3"
            audio_file_path = audio_stream.download(output_path=str(self.download_dir), filename=audio_file_name,
                                                    skip_existing=True)
            if audio_file_path:
                logger.info(f"Downloaded audio from {video_url}")
            else:
                logger.warning(
                    f"Error while downloading audio from {video_url}")
            return VideoInfo(url=video_url,
                             title=title,
                             video_path=video_file_path,
                             audio_path=audio_file_path)
        except Exception as e:
            logger.error(f"Error occurred while downloading {video_url}: {e}")
