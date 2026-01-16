FROM python:3.12-slim

RUN mkdir /work

WORKDIR /work

COPY ./src/app/requirements.txt /work
RUN pip install --no-cache-dir --timeout 1000 --retries 5 -r requirements.txt


RUN mkdir /work/app


COPY ./src/app/*.py /work/app


COPY ./base_logger.py /work

WORKDIR /work/app

CMD ["uvicorn", "main:app"]
