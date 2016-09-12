FROM python:2.7
ADD . /quickvote
WORKDIR /quickvote
RUN pip install -r requirements.txt

