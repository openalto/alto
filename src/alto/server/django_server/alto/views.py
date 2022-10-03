from django.conf import settings as conf_settings
from rest_framework.response import Response
from rest_framework.views import APIView

from .render import MultiPartRelatedRender, AltoParser
from .utils import get_content

# from alto.server.path_vector.service import PathVectorService
from alto.server.components.db import data_broker_manager, ForwardingDB, EndpointDB
from alto.server.components.frontend import PathVectorService
from alto.server.components.datasource import LookingGlassAgent, CRICAgent

# if conf_settings.BACKEND == 'lhcone':
#     cric = CRIC(conf_settings.CRIC_DB_PATH)
#     lg = LookingGlass(conf_settings.LOOKING_GLASS_URI,
#                       default_router=conf_settings.DEFAULT_LOOKING_GLASS_ROUTER)
#     pv = LhconeALTOService(cric, lg, local_asn=conf_settings.LOCAL_ASN)
# else:
#     pv = PathVectorService(conf_settings.MININET_URL, conf_settings.OPENDAYLIGHT_CREDENTIALS)

for ns, ns_config in conf_settings.DB_CONFIG.items():
    for db_type, db_config in ns_config.items():
        if db_type == 'forwarding':
            db = ForwardingDB(namespace=ns, **db_config)
        elif db_type == 'endpoint':
            db = EndpointDB(namespace=ns, **db_config)
        if db:
            data_broker_manager.register(ns, db_type, db)

if conf_settings.LOOKING_GLASS_AGENT_CONFIG:
    lg_agent = LookingGlassAgent(**conf_settings.LOOKING_GLASS_AGENT_CONFIG)
    lg_agent.update()

if conf_settings.CRIC_AGENT_CONFIG:
    cric_agent = CRICAgent(**conf_settings.CRIC_AGENT_CONFIG)
    cric_agent.update()

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
