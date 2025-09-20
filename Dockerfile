FROM python:3.11.2

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y --no-install-recommends ffmpeg
RUN mkdir /usr/src/app
COPY . /usr/src/app
WORKDIR /usr/src/app


VOLUME [ "/usr/src/app/dl" ]

ENV VIRTUAL_ENV="/bot-env"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV BOT_TOKEN=""
ENV BOT_PREFIX=.
ENV BOT_COLOR=ff0000
ENV YTDL_FORMAT=bestaudio
ENV PRINT_STACK_TRACE=true
ENV BOT_REPORT_COMMAND_NOT_FOUND=true
ENV BOT_REPORT_DL_ERROR=true

RUN pip install -r requirements
CMD ["python", "./pybot.py"]