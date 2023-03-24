FROM python:3.10.7

COPY / /tmp/alto
RUN rm -rf /tmp/alto/.git && \
    pip install redis geoip2 kazoo && \
    pip install /tmp/alto && \
    rm -rf /tmp/alto

EXPOSE 8000

