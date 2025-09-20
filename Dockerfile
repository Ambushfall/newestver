FROM python:3.11.2

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y --no-install-recommends ffmpeg
RUN mkdir /usr/src/app
COPY . /usr/src/app
WORKDIR /usr/src/app


VOLUME [ "/usr/src/app/dl" ]
VOLUME [ "/usr/src/app/cfg" ]


ENV VIRTUAL_ENV="/bot-env"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


RUN pip install -r requirements
CMD ["python", "./pybot.py"]