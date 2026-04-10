FROM python:3.12-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN useradd -m -u 1000 langlab
RUN mkdir -p /app/data && chown -R langlab:langlab /app

COPY --chown=langlab:langlab . .

USER langlab

EXPOSE 8080

CMD ["python3", "server.py"]
