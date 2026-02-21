FROM python:3.14-trixie
WORKDIR /intfar

# Expose the provided port for Flask
EXPOSE $PORT

# Install root system dependencies
RUN curl -sSL https://github.com/dyc3/steamguard-cli/releases/download/v0.17.1/steamguard-cli_0.17.1-0.deb -o ./steamguard-cli.deb \
    && apt update \
    && apt install -y ./steamguard-cli.deb \
    && apt install -y ffmpeg \
    && apt install -y golang

# Set environment variables
ENV PDM_HOME=/bin
ENV DENO_INSTALL=/usr

# Install user dependencies
RUN curl -sSL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /bin/yt-dlp \
    && chmod +x /bin/yt-dlp \
    && curl -fsSL https://deno.land/install.sh | bash

# Copy pyproject.toml
COPY pyproject.toml pdm.lock ./

# Download PDM and install requirements
RUN curl -sSL https://pdm-project.org/install.sh | bash && pdm install

# Copy code and resources
COPY src ./src
COPY resources ./resources

# Run the server
WORKDIR /intfar/src
CMD ["pdm", "run", "main.py", "-p", "${PORT}"]