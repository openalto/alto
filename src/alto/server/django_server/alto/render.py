import codecs
import json

from django.conf import settings
from django.utils.encoding import force_bytes
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser
from rest_framework.renderers import MultiPartRenderer

# from  rest_framework.parsers import MultiPartParser
# ALTO_MEDIA_TYPE = 'application/alto-endpointcost+json'
ALTO_MEDIA_TYPE = 'application/alto-endpointcostparams+json'


class MultiPartRelatedRender(MultiPartRenderer):
    # accept
    media_type = 'multipart/related'
    # multipart_related = 'multipart/related'
    # content-type
    type = ALTO_MEDIA_TYPE
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
                        'content-type: {}'.format(item.get('content-type')),
                        "content-id: {}".format(item.get('content-id')),
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


class AltoParser(BaseParser):
    media_type = ALTO_MEDIA_TYPE
    renderer_class = MultiPartRelatedRender

    def parse(self, stream, media_type=None, parser_context=None):
        """
                Parses the incoming bytestream as JSON and returns the resulting data.
        """
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', settings.DEFAULT_CHARSET)

        try:
            decoded_stream = codecs.getreader(encoding)(stream)
            parse_constant = json.strict_constant if self.strict else None
            return json.load(decoded_stream, parse_constant=parse_constant)
        except ValueError as exc:
            raise ParseError('JSON parse error - %s' % str(exc))
