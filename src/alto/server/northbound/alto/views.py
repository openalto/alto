from django.conf import settings as conf_settings
from rest_framework.response import Response
from rest_framework.views import APIView

from .render import MultiPartRelatedRender, EntityPropRender, EndpointCostParser, EntityPropParser
from .utils import get_content

from alto.server.components.backend import PathVectorService
from alto.config import Config
from alto.utils import load_class


config = Config()


def setup_debug_db():
    from alto.server.components.db import data_broker_manager, ForwardingDB, EndpointDB, DelegateDB

    for ns, ns_config in config.get_db_config().items():
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


class IRDView(APIView):
    """
    ALTO view for information resource directory (IRD).
    """

    algorithm = None
    resource_id = ''
    content_type = 'application/alto-directory+json'

    def get(self):
        pass


class EntityPropertyView(APIView):
    """
    ALTO view for entity property map.
    """
    renderer_classes = [EntityPropRender]
    parser_classes = [EntityPropParser]

    algorithm = None
    resource_id = ''
    content_type = 'application/alto-endpointprop+json'

    def post(self, request):
        entities = request.data['entities']
        content = self.algorithm.lookup(entities)
        return Response(content, content_type=self.content_type)


class PathVectorView(APIView):
    """
    ALTO view for ECS with path vector extension.
    """
    renderer_classes = [MultiPartRelatedRender]
    parser_classes = [EndpointCostParser]

    algorithm = PathVectorService(config.get_default_namespace())
    resource_id = ''

    def post(self, request):
        post_data = dict(request.data)
        content_type = self.renderer_classes[0]().get_context_type()
        host_name = request.get_host()

        content = get_content(algorithm, post_data, resource_id, host_name)
        return Response(content, content_type=content_type)


def get_view(resource_type, resource_id, namespace, algorithm=None, params=dict()):
    if resource_type == 'path-vector':
        view_cls =  PathVectorView
    elif resource_type == 'entity-prop':
        view_cls = EntityPropertyView
    else:
        return
    if algorithm:
        alg_cls = load_class(algorithm)
        alg = alg_cls(namespace, **params)
        return view_cls.as_view(resource_id=resource_id, algorithm=alg)
    else:
        return view_cls.as_view(resource_id=resource_id)
