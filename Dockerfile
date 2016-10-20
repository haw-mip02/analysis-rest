FROM python:latest

MAINTAINER Niklas Voss version: 0.1

ADD ./requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

ADD ./rest.py /opt/rest.py
CMD ["python3", "/opt/rest.py"]

EXPOSE 5000