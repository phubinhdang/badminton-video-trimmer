import logging
import shutil
import time
from pathlib import Path
from typing import List

import pandas as pd
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.io.VideoFileClip import VideoFileClip

from tools.youtube_downloader import VideoInfo
from util.moviepy_bar_logger import MoviepyBarLogger
from util.persistent_stqdm import PersistentSTQDM
from util.video_util import get_video_duration_in_seconds

logger = logging.getLogger("__name__")


class SummaryGenerator:

    def extract_subclips(self, video_title: str, clip_csv_path: str) -> List[str]:
        input_video = str(Path().cwd() / "data" / video_title / "input" / "video.mp4")
        subclip_dir = Path().cwd() / "data" / video_title / "output" / "subclips"
        if subclip_dir.exists():
            shutil.rmtree(subclip_dir)
            logger.info("Removed existing subclips before creating new ones")
        subclip_dir.mkdir(parents=True, exist_ok=True)
        df = pd.read_csv(clip_csv_path)
        subclip_paths = []
        for i, (s, e) in enumerate(PersistentSTQDM(zip(df["start"], df["end"]), total=len(df))):
            output_video = f"{subclip_dir}/{i}.mp4"
            self.extract_clip(input_video, s, e, output_video)
            subclip_paths.append(output_video)
        logger.info("Finished extracting subclips")
        return subclip_paths

    def extract_clip(self, input_video, start_time, end_time, output_video):
        # Load the video
        video = VideoFileClip(input_video)

        # Extract the subclip (moviepy uses seconds, so we convert hh:mm:ss to seconds)
        subclip = video.subclip(start_time, end_time)

        # Write the result to a file
        subclip.write_videofile(output_video, codec="libx264")

    def combine_clips(self, video_title, clip_paths):
        # List to store VideoFileClip objects
        video_clips = [VideoFileClip(clip_path) for clip_path in clip_paths]

        # Concatenate the list of video clips
        final_clip = concatenate_videoclips(video_clips, method="compose")

        # Write the final video to an output file
        output_video = str(Path().cwd() / "data" / video_title / "output" / "summary.mp4")
        moviepy_bar_logger = MoviepyBarLogger(PersistentSTQDM(), time.time())
        final_clip.write_videofile(output_video, codec="libx264", logger=moviepy_bar_logger)

        # Close all the clips
        for clip in video_clips:
            clip.close()
        logger.info("Finished combining clips to summary video")
        return output_video

    def ss_to_hhmmss(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def raw_detection_to_clips(self, video_info: VideoInfo, score_threshold=0.6):
        video_title = video_info.title
        raw_detection_path = Path().cwd() / "data" / video_title / "output" / "raw_detection.csv"
        if not raw_detection_path.exists():
            logger.error(f"{raw_detection_path} does not exist")
            raise FileNotFoundError(raw_detection_path)
        df = pd.read_csv(raw_detection_path)
        # clip the start and end of the out-of-range predicted rallies
        video_len = get_video_duration_in_seconds(video_info.video_path)
        df.loc[df['start'] < 0, 'start'] = 0
        df.loc[df['start'] > video_len, 'start'] = video_len

        df.loc[df['end'] < 0, 'end'] = 0
        df.loc[df['end'] > video_len, 'end'] = video_len
        # keep only rallies with start < end
        df = df[df['start'] < df['end']]
        df.reset_index(inplace=True)

        # keep only rallies with scores > threshold
        logger.info(f"Use score threshold = {score_threshold} to filter raw rally detections")
        df = df[df['score'] > score_threshold]
        if len(df) == 0:
            raise ValueError("No detections found after clipping and filtering")

        # merge overlapping intervals
        merged_intervals = []
        current_start = df['start'].values[0]
        current_end = df['end'].values[0]
        # Iterate through the DataFrame rows
        logger.info(f"Merging overlapping raw rally detections in {raw_detection_path}")
        for i in range(1, len(df)):
            row_start = df.iloc[i]['start']
            row_end = df.iloc[i]['end']
            # If the current interval overlaps with the previous one, merge them
            if row_start <= current_end:
                current_end = max(current_end, row_end)  # Update the end of the merged interval
            else:
                # No overlap, add the previous interval and start a new one
                merged_intervals.append([current_start, current_end])
                current_start = row_start
                current_end = row_end

        # Append the last interval
        merged_intervals.append([current_start, current_end])
        # converting second to hh:mm:ss
        df_clips = pd.DataFrame(merged_intervals, columns=['start', 'end'])
        df_clips = df_clips.assign(start=df_clips['start'].apply(self.ss_to_hhmmss))
        df_clips = df_clips.assign(end=df_clips['end'].apply(self.ss_to_hhmmss))
        clips_csv_path = Path().cwd() / "data" / video_title / "output" / "clips.csv"
        df_clips.to_csv(clips_csv_path, index=False)
        logger.info(f"Wrote merged rallies to {clips_csv_path}")
        return clips_csv_path
