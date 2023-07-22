import json
import hashlib

from django.conf import settings
from django.utils.encoding import force_bytes
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer, MultiPartRenderer

from alto.common.constants import (ALTO_CONTENT_TYPE_IRD,
                                   ALTO_CONTENT_TYPE_NM,
                                   ALTO_CONTENT_TYPE_CM,
                                   ALTO_CONTENT_TYPE_ECS,
                                   ALTO_CONTENT_TYPE_EPS,
                                   ALTO_CONTENT_TYPE_PROPMAP,
                                   ALTO_CONTENT_TYPE_TIPS,
                                   ALTO_PARAMETER_TYPE_ECS,
                                   ALTO_PARAMETER_TYPE_EPS,
                                   ALTO_PARAMETER_TYPE_PROPMAP,
                                   ALTO_PARAMETER_TYPE_TIPS)


################################
# Renders for ALTO related views
################################
class IRDRender(JSONRenderer):
    """
    Render for Information Resource Directory.
    """

    media_type = ALTO_CONTENT_TYPE_IRD

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return super(IRDRender, self).render(data, accepted_media_type, renderer_context)


class NetworkMapRender(JSONRenderer):
    """
    Render for Network Map.
    """

    media_type = ALTO_CONTENT_TYPE_NM

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return super(NetworkMapRender, self).render(data, accepted_media_type, renderer_context)


class CostMapRender(JSONRenderer):
    """
    Render for Cost Map.
    """

    media_type = ALTO_CONTENT_TYPE_CM

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return super(CostMapRender, self).render(data, accepted_media_type, renderer_context)


class EndpointCostRender(JSONRenderer):
    """
    Render for Endpoint Cost Service.
    """

    media_type = ALTO_CONTENT_TYPE_ECS

    def render(self, ecmap, accepted_media_type=None, renderer_context=None):
        data = dict()
        data['meta'] = ecmap['meta']
        data['endpoint-cost-map'] = ecmap['endpoint-cost-map']
        return super(EndpointCostRender, self).render(data, accepted_media_type,
                                                      renderer_context)


class EndpointPropRender(JSONRenderer):
    """
    Render for Entity Property Map.
    """

    media_type = ALTO_CONTENT_TYPE_EPS

    def render(self, propmap, accepted_media_type=None, renderer_context=None):
        data = dict()
        data['endpoint-properties'] = propmap
        return super(EntityPropRender, self).render(data, accepted_media_type,
                                                    renderer_context)


class EntityPropRender(JSONRenderer):
    """
    Render for Entity Property Map.
    """

    media_type = ALTO_CONTENT_TYPE_PROPMAP

    def render(self, propmap, accepted_media_type=None, renderer_context=None):
        data = dict()
        data['property-map'] = propmap
        return super(EntityPropRender, self).render(data, accepted_media_type,
                                                    renderer_context)


class MultiPartRelatedRender(MultiPartRenderer):
    # accept
    media_type = 'multipart/related'
    # multipart_related = 'multipart/related'
    # content-type
    type = ALTO_CONTENT_TYPE_ECS
    format = 'multipart'
    charset = 'utf-8'
    # FIXME: `_boundary` shouldn't be fixed. Compute boundary by hash check of content at runtime
    BOUNDARY = hashlib.md5().hexdigest()

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
                        '{}: {}'.format('Content-Type', item.get('Content-Type')),
                        "{}: {}".format('Content-ID', item.get('Content-ID')),
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
        return '{media_type}; boundary={boundary}; type={type}; charset={charset}'.format(
            media_type=self.media_type,
            boundary=self.BOUNDARY,
            type=self.type,
            charset=self.charset
        )


class TIPSRender(JSONRenderer):
    """
    Render for ALTO Transport Information Publication Service (TIPS).
    """

    media_type = ALTO_CONTENT_TYPE_TIPS

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return super(TIPSRender, self).render(data, accepted_media_type,
                                                    renderer_context)


###################################
# Parsers for ALTO related requests
###################################
class EndpointCostParser(JSONParser):
    media_type = ALTO_PARAMETER_TYPE_ECS


class EndpointPropParser(JSONParser):
    media_type = ALTO_PARAMETER_TYPE_EPS


class EntityPropParser(JSONParser):
    media_type = ALTO_PARAMETER_TYPE_PROPMAP


class TIPSParser(JSONParser):
    media_type = ALTO_PARAMETER_TYPE_TIPS
