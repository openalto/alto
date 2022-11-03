from django.conf import settings as conf_settings
from rest_framework.response import Response
from rest_framework.views import APIView

from .render import MultiPartRelatedRender, AltoParser
from .utils import get_content

from alto.server.components.backend import PathVectorService


def setup_debug_db():
    import alto.server.django_server.django_server.settings as conf_settings
    from alto.server.components.db import data_broker_manager, ForwardingDB, EndpointDB, DelegateDB

    for ns, ns_config in conf_settings.DB_CONFIG.items():
        for db_type, db_config in ns_config.items():
            if db_type == 'forwarding':
                db = ForwardingDB(namespace=ns, **db_config)
            elif db_type == 'endpoint':
                db = EndpointDB(namespace=ns, **db_config)
            elif db_type == 'delegate':
                db = DelegateDB(namespace=ns, **db_config)
            else:
                db = None
            if db:
                data_broker_manager.register(ns, db_type, db)


if conf_settings.DEBUG:
    setup_debug_db()

pv = PathVectorService(conf_settings.DEFAULT_NAMESPACE)

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
