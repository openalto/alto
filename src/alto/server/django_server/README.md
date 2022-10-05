# ALTO Northbound Framework

This submodule serves a web framework to provide northbound for ALTO protocol.

So far, it is based on Django rest framework.

> NOTE: This submodule needs to be cleaned up. The usage in the following
> sections may be deprecated soon.

## Installation

DO NOT install this submodule individually. All the requirements have been
included in the dependencies of the top-level package. Just go to the top
directory of this repo, and run:

```text
pip install .
```

## Usage

There are several options to start the ALTO server frontend.

Option 1: start the ALTO server using the `manage.py` app:

``` sh
python -m alto.server.django_server.manage runserver 0.0.0.0:8000
```

Option 2: start the ALTO server as a WSGI using gunicorn:

``` sh
gunicorn -b 0.0.0.0:8000 alto.server.django_server.django_server.wsgi
```

