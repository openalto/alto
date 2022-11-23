.. These are examples of badges you might want to add to your README:
   please update the URLs accordingly

    .. image:: https://api.cirrus-ci.com/github/<USER>/alto.svg?branch=main
        :alt: Built Status
        :target: https://cirrus-ci.com/github/<USER>/alto
    .. image:: https://readthedocs.org/projects/alto/badge/?version=latest
        :alt: ReadTheDocs
        :target: https://alto.readthedocs.io/en/stable/
    .. image:: https://img.shields.io/coveralls/github/<USER>/alto/main.svg
        :alt: Coveralls
        :target: https://coveralls.io/r/<USER>/alto
    .. image:: https://img.shields.io/pypi/v/alto.svg
        :alt: PyPI-Server
        :target: https://pypi.org/project/alto/
    .. image:: https://img.shields.io/conda/vn/conda-forge/alto.svg
        :alt: Conda-Forge
        :target: https://anaconda.org/conda-forge/alto
    .. image:: https://pepy.tech/badge/alto/month
        :alt: Monthly Downloads
        :target: https://pepy.tech/project/alto
    .. image:: https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter
        :alt: Twitter
        :target: https://twitter.com/alto

.. image:: https://github.com/openalto/alto/actions/workflows/unittest.yml/badge.svg
    :alt: Unit Tests by GitHub Actions
    :target: https://github.com/openalto/alto/actions/workflows/unittest.yml
.. image:: https://codecov.io/gh/openalto/alto/branch/master/graph/badge.svg?token=bShFzsuWpy
    :alt: Code Coverage by Codecov
    :target: https://codecov.io/gh/openalto/alto

|

========
OpenALTO
========


    Standard Application-Layer Traffic Optimization (ALTO) Toolset.


Main Components
===============

This ALTO toolset includes the following basic components:

* ALTO Protocol Parser
* ALTO Client Library
* ALTO Client CLI
* OpenALTO Server Stack

  + OpenALTO Data Source Agent Framework
  + OpenALTO Data Broker Manager
  + OpenALTO Service Backend
  + OpenALTO Protocol Northbound


Server Deployment
=================

Quick set up with ``docker`` and ``docker-compose``:

.. code-block:: bash

    $ docker build -t openalto/alto .
    $ docker-compose up -d

To deploy openalto without docker, please make sure you have the following
required packages:

* Python >= 3.6.8
* Redis

.. code-block:: bash

    $ pip3 install .
    $ pip3 install redis
    $ gunicorn -b 0.0.0.0:8000 --reload --preload --capture-output --error-logfile /tmp/openalto-error.log --access-logfile /tmp/openalto-access.log alto.server.northbound.wsgi -D
    $ python3 -m alto.agent.manage --pid /tmp start -c etc/lg-agent.json -D cernlg
    $ python3 -m alto.agent.manage --pid /tmp start -c etc/cric-agent.json -D cric
    $ python3 -m alto.agent.manage --pid /tmp start -c etc/geoip-delegate-agent.json -D geoip

To deploy openalto in kubernetes:

    Coming soon...


Note
====

This project has been set up using PyScaffold 4.1.5. For details and usage
information on PyScaffold see https://pyscaffold.org/.
