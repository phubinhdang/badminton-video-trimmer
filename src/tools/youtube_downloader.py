import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pytubefix import YouTube
from util.persistent_stqdm import PersistentSTQDM
import os

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    url: str
    title: str
    video_path: str
    audio_path: str


class YoutubeDownloader:
    def __init__(self, show_progress_in_backend=True, video_only=False):
        self.show_progress_in_backend = show_progress_in_backend
        self.streamlit_tqdm = None
        self.video_only = video_only

    def on_progress(self, stream, chunk, bytes_remaining):
        # Calculate the percentage of the download completed
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        # Update the tqdm progress bar
        if self.streamlit_tqdm is not None:
            self.streamlit_tqdm.n = bytes_downloaded
            self.streamlit_tqdm.refresh()

    def download(self, video_url) -> VideoInfo:
        download_res = os.getenv("DOWNLOAD_RESOLUTION", "720p")
        yt = YouTube(video_url, on_progress_callback=self.on_progress)
        title = self.clean_title(yt.title)
        video_file_path = None
        audio_file_path = None
        try:
            video_file_path = self.download_video(yt, title, resolution=download_res)
        except Exception as e:
            logger.error(f"Error while downloading video from {video_url}: {e}")
        if not self.video_only:
            try:
                audio_file_path = self.download_audio(yt, title)
            except Exception as e:
                logger.error(f"Error while downloading audio from {video_url}: {e}")

        return VideoInfo(
            url=video_url,
            title=title,
            video_path=video_file_path,
            audio_path=audio_file_path,
        )

    def download_audio(self, yt: YouTube, title: str) -> str:
        try:
            audio_stream = yt.streams.filter(progressive=False, type="audio").first()
            download_path = Path.cwd() / "data" / f"{title}" / "input"
            download_path.mkdir(parents=True, exist_ok=True)
            self.streamlit_tqdm = PersistentSTQDM(
                total=audio_stream.filesize,
                unit="B",
                unit_scale=True,
                desc="Downloading AUDIO",
                backend=self.show_progress_in_backend,
            )
            audio_file_path = audio_stream.download(
                output_path=str(download_path),
                filename="audio.mp3",
                skip_existing=False,
            )
            if not audio_file_path:
                raise Exception()
            return audio_file_path
        except Exception as e:
            raise e

    def clean_title(self, title) -> str:
        title = re.sub(r"[^A-Za-z0-9\s]", "", title)
        return re.sub(r"\s+", "_", title)

    def download_video(self, yt: YouTube, title, resolution="720p") -> str:
        try:
            video_streams = (
                yt.streams.filter(progressive=False, type="video")
                .order_by("resolution")
                .desc()
            )
            video_stream = video_streams.filter(resolution=resolution).first()
            if not video_stream:
                video_stream = video_streams.first()
                logger.info(
                    f"Stream of resolution {resolution} not found, download stream of {video_stream.resolution} instead"
                )
            # Create a Streamlit progress bar widget
            download_path = Path.cwd() / "data" / f"{title}" / "input"
            download_path.mkdir(parents=True, exist_ok=True)
            self.streamlit_tqdm = PersistentSTQDM(
                total=video_stream.filesize,
                unit="B",
                unit_scale=True,
                desc="Downloading VIDEO",
                backend=self.show_progress_in_backend,
            )
            video_file_path = video_stream.download(
                output_path=str(download_path),
                filename="video.mp4",
                skip_existing=False,
            )
            return video_file_path
        except Exception as e:
            raise e
