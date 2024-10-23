import logging

import streamlit as st

from tools.frame_extractor import FrameExtractor
from tools.youtube_downloader import YoutubeDownloader

APP_LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=APP_LOGGING_FORMAT, level=logging.INFO)

frame_extractor = FrameExtractor()
youtube_downloader = YoutubeDownloader()


def trim_video(video_url: str):
    video_info = youtube_downloader.download(video_url)
    frame_extractor.extract_frames(video_info)


st.title("Let's generate a badminton summary video")
video_url = st.text_input("Enter YouTube Badminton Video URL:")
if video_url:
    # display the preview of the video url
    st.video(video_url)
if st.button("Start Trimming"):
    trim_video(video_url)
