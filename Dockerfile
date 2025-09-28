# syntax=docker/dockerfile:1
FROM python:3.11.2-slim-bullseye AS builder
RUN --mount=type=cache,target=/root/.cache/pip pip install pyyaml

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y --no-install-recommends ffmpeg
RUN mkdir /usr/src/app
COPY . /usr/src/app
WORKDIR /usr/src/app


VOLUME [ "/usr/src/app/dl" ]
VOLUME [ "/usr/src/app/cfg" ]


ENV VIRTUAL_ENV="/bot-env"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


RUN pip install -r requirements.txt
RUN python -m pip install -U "yt-dlp[default]"
CMD ["python", "./pybot.py"]