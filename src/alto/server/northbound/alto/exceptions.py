# -*- coding: utf-8 -*-
# The MIT License (MIT)
#
# Copyright (c) 2023 OpenALTO Community
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Authors:
# - Jensen Zhang <jingxuan.n.zhang@gmail.com>

import sys
import traceback
from urllib.parse import quote

from django.http import JsonResponse
from rest_framework import status
from rest_framework.views import exception_handler

from alto.common.constants import ALTO_CONTENT_TYPE_ERROR


def alto_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.content_type = ALTO_CONTENT_TYPE_ERROR
        if 'meta' not in response.data:
            response.data['meta'] = dict()
        response.data['meta']['code'] = 'E_GENERIC_HTTP'
    return response


def not_found(request, exception, *args, **kwargs):
    """
    Generic 404 error handler.
    """
    exception_repr = exception.__class__.__name__
    try:
        message = exception.args[0]
    except (AttributeError, IndexError):
        pass
    else:
        if isinstance(message, str):
            exception_repr = message
    data = {
        'meta': {
            'code': 'E_GENERIC_HTTP_404_NOT_FOUND'
        },
        'context': {
            "request_path": quote(request.path),
            "exception": exception_repr,
        }
    }
    return JsonResponse(data, status=status.HTTP_404_NOT_FOUND, content_type=ALTO_CONTENT_TYPE_ERROR)


def server_error(request, *args, **kwargs):
    """
    Generic 500 error handler.
    """
    exception_repr = traceback.format_exception(*sys.exc_info())
    data = {
        'meta': {
            'code': 'E_GENERIC_HTTP_500_INTERNAL_SERVER_ERROR'
        },
        'context': {
            "request_path": quote(request.path),
            "exception": exception_repr,
        }
    }
    return JsonResponse(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR, content_type=ALTO_CONTENT_TYPE_ERROR)

