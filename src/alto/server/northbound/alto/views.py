import uuid
from django.conf import settings as conf_settings
from rest_framework.response import Response
from rest_framework.views import APIView

from .render import (IRDRender,
                     NetworkMapRender,
                     CostMapRender,
                     MultiPartRelatedRender,
                     EndpointCostRender,
                     EntityPropRender,
                     TIPSRender,
                     EndpointCostParser,
                     EntityPropParser,
                     TIPSParser)

from alto.server.components.backend import (IRDService,
                                            PathVectorService,
                                            TIPSControlService,
                                            MockService)
from alto.config import Config
from alto.utils import load_class, setup_debug_db
from alto.common.constants import (ALTO_CONTENT_TYPE_ERROR,
                                   ALTO_CONTENT_TYPE_IRD,
                                   ALTO_CONTENT_TYPE_NM,
                                   ALTO_CONTENT_TYPE_CM,
                                   ALTO_CONTENT_TYPE_ECS,
                                   ALTO_CONTENT_TYPE_TIPS,
                                   ALTO_CONTENT_TYPE_TIPS_VIEW,
                                   ALTO_CONTENT_TYPE_PROPMAP)


config = Config()


if conf_settings.DEBUG:
    setup_debug_db(config)


class IRDView(APIView):
    """
    ALTO view for information resource directory (IRD).
    """
    renderer_classes = [IRDRender]

    algorithm = IRDService('default-ird')
    resource_id = ''
    content_type = ALTO_CONTENT_TYPE_IRD

    def get(self, request):
        base_uri = request.build_absolute_uri('/')
        content = self.algorithm.list_resources(self.resource_id, default_base_uri=base_uri)
        return Response(content, content_type=self.content_type)


class NetworkMapView(APIView):
    """
    ALTO view for network map.
    """
    renderer_classes = [NetworkMapRender]

    algorithm = MockService()
    resource_id = ''
    content_type = ALTO_CONTENT_TYPE_NM

    def get(self, request):
        # TODO: Implement view for network map
        content = self.algorithm.lookup()
        return Response(content, content_type=self.content_type)


class CostMapView(APIView):
    """
    ALTO view for cost map.
    """
    renderer_classes = [CostMapRender]

    algorithm = MockService()
    resource_id = ''
    content_type = ALTO_CONTENT_TYPE_CM

    def get(self, request):
        # TODO: Implement view for network map
        content = self.algorithm.lookup()
        return Response(content, content_type=self.content_type)


class EntityPropertyView(APIView):
    """
    ALTO view for entity property map.
    """
    renderer_classes = [EntityPropRender]
    parser_classes = [EntityPropParser]

    algorithm = None
    resource_id = ''
    content_type = ALTO_CONTENT_TYPE_PROPMAP

    def post(self, request):
        entities = request.data['entities']
        content = self.algorithm.lookup(entities)
        return Response(content, content_type=self.content_type)


class EndpointCostView(APIView):
    """
    ALTO view for endpoint cost.
    """
    renderer_classes = [EndpointCostRender]
    parser_classes = [EndpointCostParser]

    algorithm = None
    resource_id = ''
    content_type = ALTO_CONTENT_TYPE_ECS

    def safe_check(self, cost_type):
        # TODO: Check if cost type is supported
        return True

    def apply_constraints(self, ecmap, constraints):
        # TODO: apply constraints to filter endpoint cost map
        return ecmap

    def post(self, request):
        endpoint_filter = request.data['endpoints']
        srcs = endpoint_filter['srcs']
        dsts = endpoint_filter['dsts']
        cost_type = request.data.get('cost-type')
        if cost_type:
            self.safe_check(cost_type)
        content = self.algorithm.lookup(srcs, dsts, cost_type)
        constraints = request.data.get('constraints')
        if constraints:
            content = self.apply_constraints(content, constraints)
        return Response(content, content_type=self.content_type)


class PathVectorView(APIView):
    """
    ALTO view for ECS with path vector extension.
    """
    renderer_classes = [MultiPartRelatedRender]
    parser_classes = [EndpointCostParser]

    algorithm = PathVectorService(config.get_default_namespace())
    resource_id = ''

    def get_flows(self, srcs, dsts):
        """
        Get full mesh flows of srcs x dsts.

        Parameters
        ----------
        srcs : list
            List of source endpoints.
        dsts : list
            List of destination endpoints.

        Returns
        -------
        flows : list
            List of `(src, dst)` pairs for full mesh of srcs x dsts.
        """
        flows = set()
        for src in srcs:
            src_type, src_addr = src.split(':', 1)
            if src_type not in ['ipv4', 'ipv6']:
                continue
            for dst in dsts:
                dst_type, dst_addr = dst.split(':', 1)
                if dst_type not in ['ipv4', 'ipv6']:
                    continue
                flows.add((src_addr, dst_addr))
        return flows

    def get_params(self, post_data):
        """
        Get accept input parameters from HTTP post data.

        Parameters
        ----------
        post_data : dict
            The ECS request in dictionary format.

        Returns
        -------
        flows : list
            List of `(src, dst)` pairs.
        prop_names : list
            List of property names.
        cost_type : dict
            Cost type in the dictionary format.
        """
        if 'endpoints' in post_data:
            srcs = post_data['endpoints']['srcs']
            dsts = post_data['endpoints']['dsts']
            flows = self.get_flows(srcs, dsts)
        elif 'endpoint-flows' in post_data:
            flows = set()
            for spec in post_data['endpoint-flows']:
                srcs, dsts = spec['srcs'], spec['dsts']
                flows |= self.get_flows(srcs, dsts)

        assert 'cost-type' in post_data
        cost_type = post_data['cost-type']
        assert cost_type['cost-mode'] == 'array'
        assert cost_type['cost-metric'] == 'ane-path'

        if 'ane-property-names' in post_data:
            prop_names = post_data['ane-property-names']
        else:
            prop_names = []

        return flows, prop_names, cost_type

    def get_content(self, flows, prop_names, cost_type, host_name):
        """
        Call path vector algorithm to compute path vectors and properties.

        Parameters
        ----------
        flows : list
            List of `(src, dst)` pairs.
        prop_names : list
            List of property names.
        cost_type : dict
            Cost type in the dictionary format.
        host_name : str
            Host name of the ALTO server.

        Returns
        -------
        ecs_part : dict
            Dictionary for the `endpoint-cost-map` response.
        prop_part : dict
            Dictionary for the `property-map` response.
        """
        paths, link_map = self.algorithm.lookup(flows, prop_names)

        # prepare the ECS part
        ecs_part = {}
        ecs_part['Content-Type'] = ALTO_CONTENT_TYPE_ECS
        ecs_part['Content-ID'] = "<ecs@%s>" % (host_name)
        ecs_rid = '%s.ecs' % self.resource_id

        tag = uuid.uuid4().hex
        vtag = { 'resource-id': ecs_rid, 'tag': tag }
        data = {}
        data['meta'] = { 'vtag': vtag, 'cost-type': cost_type }
        data['endpoint-cost-map'] = paths
        ecs_part['data'] = data

        # prepare the property map part
        prop_part = {}
        prop_part['Content-Type'] = ALTO_CONTENT_TYPE_PROPMAP
        prop_part['Content-ID'] = "<propmap@%s>" % (host_name)
        prop_rid = '%s.propmap' % self.resource_id

        data = {}
        data['meta'] = {'dependent-vtags': [ vtag ]}
        property_map = {}
        for ane in link_map:
            ane_name = '.ane:%s' % (ane)
            ane_props = link_map[ane]
            props = prop_names if len(prop_names) > 0 else ane_props.keys()
            print(props)
            property_map[ane_name] = {pn: ane_props[pn] for pn in props if ane_props.get(pn) is not None}
        data['property-map'] = property_map

        prop_part['data'] = data

        return [ ecs_part, prop_part ]

    def post(self, request):
        post_data = dict(request.data)
        content_type = self.renderer_classes[0]().get_context_type()
        host_name = request.get_host()

        flows, prop_names, cost_type = self.get_params(post_data)

        content = self.get_content(flows, prop_names, cost_type, host_name)
        return Response(content, content_type=content_type)


class TIPSView(APIView):
    """
    ALTO view for Transport Information Publication Service (TIPS).
    """
    renderer_classes = [TIPSRender]
    parser_classes = [TIPSParser]

    algorithm = None # TIPSControlService(config.get_default_namespace())
    resource_id = ''
    content_type = ALTO_CONTENT_TYPE_TIPS

    def post(self, request):
        post_data = dict(request.data)
        client_id = 'public'
        if request.user.is_authenticated:
            client_id = request.user.get_username()
        content = self.algorithm.subscribe(post_data, client_id=client_id)
        if content is None:
            return Response(dict(), status=404, content_type=ALTO_CONTENT_TYPE_ERROR)
        return Response(content, content_type=self.content_type)


class TIPSMetadataView(APIView):
    """
    ALTO view for TIPS view metadata directory service.
    """
    renderer_classes = [TIPSRender]

    algorithm = None # TIPSControlService(config.get_default_namespace())
    resource_id = ''
    content_type = ALTO_CONTENT_TYPE_TIPS_VIEW

    def get(self, request, resource_id=None, digest=None, ug_only=False, start_seq=None, end_seq=None):
        content = self.algorithm.get_tips_view(resource_id, digest, ug_only, start_seq, end_seq)
        if content is None:
            return Response(dict(), status=404, content_type=ALTO_CONTENT_TYPE_ERROR)
        return Response(content, content_type=self.content_type)

    def delete(self, request, resource_id=None, digest=None):
        client_id = 'public'
        if request.user.is_authenticated:
            client_id = request.user.get_username()
        success = self.algorithm.unsubscribe(resource_id, digest, client_id=client_id)
        if not success:
            return Response(dict(), status=404, content_type=ALTO_CONTENT_TYPE_ERROR)
        return Response(content_type=self.content_type)


class TIPSDataTransferView(APIView):
    """
    ALTO view for TIPS data transfer service.
    """
    renderer_classes = [TIPSRender]

    algorithm = None # TIPSControlService(config.get_default_namespace())
    resource_id = ''
    content_type = ALTO_CONTENT_TYPE_TIPS

    def get(self, request, resource_id=None, digest=None, start_seq=None, end_seq=None):
        content, media_type = self.algorithm.get_tips_data(resource_id, digest, start_seq, end_seq)
        if content is None:
            return Response(dict(), status=404, content_type=ALTO_CONTENT_TYPE_ERROR)
        return Response(content, content_type=media_type)


def get_view(resource_type, resource_id, namespace, algorithm=None, params=dict()):
    if resource_type == 'ird':
        view_cls = IRDView
    elif resource_type == 'network-map':
        # TODO: Implement view for network map
        view_cls = NetworkMapView
    elif resource_type == 'cost-map':
        # TODO: Implement view for cost map
        view_cls = CostMapView
    elif resource_type == 'endpoint-cost':
        view_cls = EndpointCostView
    elif resource_type == 'path-vector':
        view_cls = PathVectorView
    elif resource_type == 'entity-prop':
        view_cls = EntityPropertyView
    elif resource_type == 'tips':
        view_cls = TIPSView
        params['tips_resource_id'] = resource_id
    elif resource_type == 'tips-view':
        view_cls = TIPSMetadataView
        params['tips_resource_id'] = resource_id
    elif resource_type == 'tips-data':
        view_cls = TIPSDataTransferView
        params['tips_resource_id'] = resource_id
    else:
        return
    if algorithm:
        alg_cls = load_class(algorithm)
        params['resource_id'] = resource_id
        alg = alg_cls(namespace, **params)
        return view_cls.as_view(resource_id=resource_id, algorithm=alg)
    else:
        return view_cls.as_view(resource_id=resource_id)
