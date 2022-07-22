from django.conf import settings as conf_settings
from rest_framework.response import Response
from rest_framework.views import APIView

from .render import MultiPartRelatedRender, AltoParser
from .utils import get_content

from alto.server.path_vector.service import PathVectorService

pv = PathVectorService(conf_settings.MININET_HOST)

class AltoView(APIView):
    renderer_classes = [MultiPartRelatedRender]
    parser_classes = [AltoParser]

    def get(self, request, path_vector):
        print('get')
        print(request.headers)
        return Response({

        })

    def post(self, request, path_vector):
        post_data = dict(request.data)
        content_type = self.renderer_classes[0]().get_context_type()
        host_name = request.get_host()

        service_name = path_vector
        content = get_content(pv, post_data, service_name, host_name)
        return Response(content, content_type=content_type)
