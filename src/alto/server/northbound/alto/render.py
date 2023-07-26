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
                                   ALTO_CONTENT_TYPE_ERROR,
                                   ALTO_PARAMETER_TYPE_ECS,
                                   ALTO_PARAMETER_TYPE_EPS,
                                   ALTO_PARAMETER_TYPE_PROPMAP,
                                   ALTO_PARAMETER_TYPE_TIPS)


################################
# Renders for ALTO related views
################################
class ALTOBaseRender(JSONRenderer):
    """
    Base render for ALTO information resources.
    """

    media_type = ALTO_CONTENT_TYPE_ERROR

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if not renderer_context or 'response' not in renderer_context or not renderer_context['response'].exception:
            return self._render(data, accepted_media_type, renderer_context)
        return super(ALTOBaseRender, self).render(data, accepted_media_type, renderer_context)

    def _render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Override by render for specific information resource.
        """
        return super(ALTOBaseRender, self).render(data, accepted_media_type, renderer_context)


class IRDRender(ALTOBaseRender):
    """
    Render for Information Resource Directory.
    """

    media_type = ALTO_CONTENT_TYPE_IRD

    def _render(self, data, accepted_media_type=None, renderer_context=None):
        return super(ALTOBaseRender, self).render(data, accepted_media_type, renderer_context)


class NetworkMapRender(ALTOBaseRender):
    """
    Render for Network Map.
    """

    media_type = ALTO_CONTENT_TYPE_NM

    def _render(self, data, accepted_media_type=None, renderer_context=None):
        return super(ALTOBaseRender, self).render(data, accepted_media_type, renderer_context)


class CostMapRender(ALTOBaseRender):
    """
    Render for Cost Map.
    """

    media_type = ALTO_CONTENT_TYPE_CM

    def _render(self, data, accepted_media_type=None, renderer_context=None):
        return super(ALTOBaseRender, self).render(data, accepted_media_type, renderer_context)


class EndpointCostRender(ALTOBaseRender):
    """
    Render for Endpoint Cost Service.
    """

    media_type = ALTO_CONTENT_TYPE_ECS

    def _render(self, ecmap, accepted_media_type=None, renderer_context=None):
        data = dict()
        data['meta'] = ecmap['meta']
        data['endpoint-cost-map'] = ecmap['endpoint-cost-map']
        return super(ALTOBaseRender, self).render(data, accepted_media_type,
                                                      renderer_context)


class EndpointPropRender(ALTOBaseRender):
    """
    Render for Endpoint Property Map.
    """

    media_type = ALTO_CONTENT_TYPE_EPS

    def _render(self, propmap, accepted_media_type=None, renderer_context=None):
        data = dict()
        data['endpoint-properties'] = propmap
        return super(ALTOBaseRender, self).render(data, accepted_media_type,
                                                    renderer_context)


class EntityPropRender(ALTOBaseRender):
    """
    Render for Entity Property Map.
    """

    media_type = ALTO_CONTENT_TYPE_PROPMAP

    def _render(self, propmap, accepted_media_type=None, renderer_context=None):
        data = dict()
        data['property-map'] = propmap
        return super(ALTOBaseRender, self).render(data, accepted_media_type,
                                                    renderer_context)


class MultiPartRelatedRender(ALTOBaseRender):
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

    def _render(self, data, accepted_media_type=None, renderer_context=None):

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


class TIPSRender(ALTOBaseRender):
    """
    Render for ALTO Transport Information Publication Service (TIPS).
    """

    media_type = ALTO_CONTENT_TYPE_TIPS

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return super(ALTOBaseRender, self).render(data, accepted_media_type,
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
