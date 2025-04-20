FROM ubuntu:22.04


RUN apt-get update && apt-get install -y \
build-essential \
curl \
software-properties-common \
libgl1 \
ffmpeg \
&& rm -rf /var/lib/apt/lists/*


# Install uv python package manager
# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh
# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh
# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"


WORKDIR /app
COPY . . 

RUN uv venv --python 3.8
RUN uv clean && uv sync --extra cpu
EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# refer to https://docs.streamlit.io/deploy/tutorials/docker
ENTRYPOINT ["uv", "run", "streamlit", "run", "src/main.py", "--server.port=8501", "--server.address=0.0.0.0"]