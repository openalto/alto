FROM batfish/allinone:latest

COPY . /tmp/alto
COPY ./docker-batfish/start.sh start.sh
RUN chmod +x start.sh
RUN apt-get install -y python3 python3-pip
RUN rm -rf /tmp/alto/.git && \
    pip install redis geoip2 pybatfish && \
    pip install /tmp/alto && \
    rm -rf /tmp/alto

EXPOSE 8000

ENTRYPOINT [ "./start.sh" ]
