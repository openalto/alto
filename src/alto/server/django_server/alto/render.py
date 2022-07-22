import codecs
import json

from django.conf import settings
from django.utils.encoding import force_bytes
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser
from rest_framework.renderers import MultiPartRenderer

from rest_framework.parsers import JSONParser

HEADER_CTYPE = 'Content-Type'
HEADER_ID = 'Content-ID'
ALTO_CONTENT_TYPE_ECS = 'application/alto-endpointcost+json'
ALTO_CONTENT_TYPE_PROPMAP = 'application/alto-propmap+json'
ALTO_PARAMETER_TYPE = 'application/alto-endpointcostparams+json'


class MultiPartRelatedRender(MultiPartRenderer):
    # accept
    media_type = 'multipart/related'
    # multipart_related = 'multipart/related'
    # content-type
    type = ALTO_CONTENT_TYPE_ECS
    format = 'multipart'
    charset = 'utf-8'
    BOUNDARY = 'Alto'

    def __init__(self):
        super(MultiPartRelatedRender, self).__init__()

    def render(self, data, accepted_media_type=None, renderer_context=None):

        return self.encode_multipart(data)

    def encode_multipart(self, data):
        def to_bytes(s):
            return force_bytes(s, settings.DEFAULT_CHARSET)

        lines = []
        print(data)

        for item in data:
            try:
                lines.extend(
                    to_bytes(val)
                    for val in [
                        "--%s" % self.BOUNDARY,
                        '{}: {}'.format(HEADER_CTYPE, item.get(HEADER_CTYPE)),
                        "{}: {}".format(HEADER_ID, item.get(HEADER_ID)),
                        "",
                        json.dumps(item.get('data')),
                    ]
                )
            except:
                return to_bytes(data.get('detail'))

        lines.extend(
            [
                to_bytes("--%s--" % self.BOUNDARY),
                b"",
            ]
        )
        return b"\r\n".join(lines)

    def get_context_type(self):
        return '{media_type}; boundary={boundary}; type={type}; charset={charset};'.format(
            media_type=self.media_type,
            boundary=self.BOUNDARY,
            type=self.type,
            charset=self.charset
        )


class AltoParser(JSONParser):
    media_type = ALTO_PARAMETER_TYPE
