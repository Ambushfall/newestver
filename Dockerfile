FROM python:3.11.2

# Set build arguments for target platform information
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

# Display information about the target platform during the build
RUN echo "Building for TARGETPLATFORM=${TARGETPLATFORM}, TARGETARCH=${TARGETARCH}, TARGETVARIANT=${TARGETVARIANT}"

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y --no-install-recommends ffmpeg
RUN mkdir /usr/src/app
COPY . /usr/src/app
WORKDIR /usr/src/app


VOLUME [ "/usr/src/app/dl" ]
VOLUME [ "/usr/src/app/cfg" ]


ENV VIRTUAL_ENV="/bot-env"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


RUN pip install -r requirements.txt
CMD ["python", "./pybot.py"]