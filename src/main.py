import logging
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from predicting.rally_predictor import RallyPredictor
from summary_generator.summary_generator import SummaryGenerator
from tools.frame_extractor import FrameExtractor
from tools.youtube_downloader import YoutubeDownloader, VideoInfo

APP_LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=APP_LOGGING_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)

youtube_downloader = YoutubeDownloader()
frame_extractor = FrameExtractor()
predictor = RallyPredictor()
generator = SummaryGenerator()

chunk_size = 5 * 1024 * 1024  # 5 MB per chunk
def get_video_chunk(file_path, start, end):
    """Retrieve a segment of the video file from start to end bytes."""
    with open(file_path, 'rb') as f:
        f.seek(start)
        return f.read(end - start)

def stream_video_to_temp_file(file_path, chunk_size=2**20):
    """Write video file chunks to a temporary file and return the temp file path."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    with open(temp_file.name, 'wb') as temp_video:
        file_size = Path(file_path).stat().st_size
        start = 0
        while start < file_size:
            end = min(start + chunk_size, file_size)
            temp_video.write(get_video_chunk(file_path, start, end))
            start = end
    return temp_file.name

def trim_video(video_url: str):
    st.sidebar.markdown("### Downloading Video (Step 1/5)")
    video_info = youtube_downloader.download(video_url)
    logger.info(video_info)
    st.sidebar.markdown("### Extracting Frames (Step 2/5)")
    frame_extractor.extract_frames(video_info)

    st.sidebar.markdown("### Predicting Rallies (Step 3/5)")
    predictor.predict(video_info)

    clips_csv_path = generator.raw_detection_to_clips(video_info, 0.8)
    st.sidebar.markdown("### Extracting predicted rallies (Step 4/5)")
    subclip_paths = generator.extract_subclips(video_info.title, clips_csv_path)

    st.sidebar.markdown("### Generating Summary Video (Step 5/5)")
    video_path = generator.combine_clips(video_info.title, subclip_paths)
    temp_video_path = stream_video_to_temp_file(video_path, chunk_size)
    st.video(temp_video_path)
    # show_video_download_button(video_path)

    df = pd.read_csv(clips_csv_path)
    # Display first few lines of the CSV file
    st.write("Preview of the predicted rallies:")
    st.dataframe(df.head(5))
    # Convert DataFrame to CSV format for download
    csv = df.to_csv(index=False).encode('utf-8')
    show_csv_download_button(csv)


@st.fragment
def show_video_download_button(video_path):
    # Add a download button for the video
    with open(video_path, "rb") as f:
        st.download_button("Download Video", f, file_name="summary.mp4", mime="video/mp4")


@st.fragment
def show_csv_download_button(csv):
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="clips.csv",
        mime="text/csv",
        key="download_csv"
    )


st.title("Let's generate a badminton summary video")
video_url = st.text_input("Enter YouTube Badminton Video URL:")
if video_url:
    # display the preview of the video url
    st.video(video_url)
if video_url and st.button("Start Trimming"):
    trim_video(video_url)
