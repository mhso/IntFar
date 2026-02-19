FROM python:3.14-trixie
WORKDIR /intfar

# Expose the provided port for Flask
EXPOSE $PORT

# Create user to run everything as
RUN useradd -m intfar && chown intfar /intfar -R

# Install root system dependencies
RUN curl -sSL https://github.com/dyc3/steamguard-cli/releases/download/v0.17.1/steamguard-cli_0.17.1-0.deb -o ./steamguard-cli.deb \
    && apt update \
    && apt install -y ./steamguard-cli.deb \
    && apt install -y ffmpeg

USER intfar

# Set environment variables
ENV PDM_HOME=/home/intfar/.local/bin
ENV DENO_INSTALL=/home/intfar/.local
ENV PATH=/home/intfar/.local/bin:$PATH

# Create missing directories
RUN mkdir /home/intfar/.local \
    && mkdir /home/intfar/.local/bin \
    && mkdir /home/intfar/.config \
    && mkdir /home/intfar/.config/steamguard-cli

# Install user dependencies
RUN curl -sSL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /home/intfar/.local/bin/yt-dlp \
    && chmod +x /home/intfar/.local/bin/yt-dlp \
    && curl -fsSL https://deno.land/install.sh | bash

# Copy pyproject.toml
COPY --chown=intfar pyproject.toml pdm.lock ./

# Download PDM and install requirements
RUN curl -sSL https://pdm-project.org/install.sh | bash && pdm install

# Copy code and resources
COPY --chown=intfar maFiles /home/intfar/.config/steamguard-cli/maFiles
COPY --chown=intfar src ./src
COPY --chown=intfar resources ./resources

# Run the server
WORKDIR /intfar/src
CMD ["pdm", "run", "main.py", "-p", "${PORT}"]