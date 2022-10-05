FROM python:3.10.7

COPY / /tmp/alto
RUN rm -rf /tmp/alto/.git && \
    pip install redis && \
    pip install /tmp/alto && \
    rm -rf /tmp/alto

EXPOSE 8000

