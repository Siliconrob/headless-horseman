FROM ubuntu:latest
LABEL authors="siliconrob"

FROM python:3.12

WORKDIR /src

ADD ./ /src

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install && playwright install-deps

EXPOSE 8080

CMD ["python", "main.py"]