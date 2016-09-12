FROM grahamdumpleton/mod-wsgi-docker:python-2.7-onbuild
CMD [ "app.py" ]
#ADD . /quickvote
#WORKDIR /quickvote
#RUN pip install -r requirements.txt

