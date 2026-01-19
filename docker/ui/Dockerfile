FROM python:3.12-slim

RUN mkdir /servers-dashboard
WORKDIR /servers-dashboard

#copy requirements from ui
COPY ./src/ui/requirements.txt /servers-dashboard/requirements.txt
RUN pip install  --upgrade pip --no-cache-dir --timeout 1000 --retries 5 -r requirements.txt

#tmp use requirements from app
COPY ./src/app/requirements.txt /servers-dashboard/requirements2.txt
RUN pip install  --upgrade pip --no-cache-dir --timeout 1000 --retries 5 -r requirements2.txt


RUN mkdir /servers-dashboard/data
RUN mkdir /servers-dashboard/data/source

RUN mkdir /servers-dashboard/src
RUN mkdir /servers-dashboard/src/ui
RUN mkdir /servers-dashboard/src/ui/assets
RUN mkdir /servers-dashboard/src/ui/components
RUN mkdir /servers-dashboard/src/ui/pages
RUN mkdir /servers-dashboard/src/ui/utils

RUN mkdir /servers-dashboard/ETL

#tmp use app, later it is a separate service
RUN mkdir /servers-dashboard/src/app

COPY ./data/source/all_vm.xlsx /servers-dashboard/data/source/all_vm.xlsx

COPY ./src/ui/*.py /servers-dashboard/src/ui
COPY ./src/ui/assets/*.* /servers-dashboard/src/ui/assets
COPY ./src/ui/components/*.py /servers-dashboard/src/ui/components
COPY ./src/ui/pages/*.py /servers-dashboard/src/ui/pages
COPY ./src/ui/utils/*.py /servers-dashboard/src/ui/utils

COPY ./ETL/*.py /servers-dashboard/ETL

#tmp use app, later it is a separate service
COPY ./src/app/*.py /servers-dashboard/src/app


COPY ./base_logger.py /servers-dashboard

WORKDIR /servers-dashboard/src/ui

CMD ["streamlit", "run", "main.py"]
