FROM python:3.10.7

COPY . /tmp/alto
RUN rm -rf /tmp/alto/.git && \
    pip install redis geoip2 kazoo -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install /tmp/alto -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    rm -rf /tmp/alto

EXPOSE 8000

