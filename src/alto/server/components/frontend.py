from .db import data_broker_manager

class PathVectorService:

    def __init__(self, namespace, autoreload=True) -> None:
        """
        """
        self.ns = namespace
        self.fib = data_broker_manager.get(self.ns, db_type='forwarding')
        self.eb = data_broker_manager.get(self.ns, db_type='endpoint')

    def parse_flow(self, flow):
        """
        Extract attributes of a flow object.

        Parameters
        ----------
        flow : object

        Return
        ------
        A tuple of attributes.
        """
        return '0.0.0.0/32', flow[0], flow[1]

    def lookup(self, flows, property_names):
        """
        Parameters
        ----------
        flows : list
            A list of flow objects.

        Returns
        -------
        paths : list
            A list of ane paths.
        propery_map : dict
            Mapping from ane to properties.
        """
        if self.autoreload:
            self.fib.build_cache()
            self.eb.build_cache()
        paths = dict()
        as_path_dict = dict()
        as_path_idx = 0
        nh_dict = dict()
        nh_idx = 0
        property_map = dict()
        for flow in flows:
            ingress, src, dst = self.parse_flow(flow)
            src_prop = self.eb.lookup(src)
            if src_prop is None:
                continue
            if not src_prop.get('is_local'):
                continue

            if src not in paths:
                paths[src] = dict()
            path = list()

            dst_prop = self.eb.lookup(dst)
            if dst_prop is None:
                continue

            ingress_prop = self.eb.lookup(ingress, ['dpid', 'in_port'])
            dpid = ingress_prop.get('dpid')
            if not dpid:
                continue
            in_port = ingress_prop.get('in_port')
            if not in_port:
                in_port = '0'

            action = self.fib.lookup(dpid, dst, in_port=in_port)
            if not action.next_hop:
                continue

            nh = action.next_hop
            if nh not in nh_dict:
                nh_ane = 'ane:L_%d' % nh_idx
                nh_idx += 1
                nh_dict[nh] = nh_ane
                property_map[nh_ane] = dict()
                if property_names is not None and 'next_hop' in property_names:
                    property_map[nh_ane]['next_hop'] = nh
            nh_ane = nh_dict[nh]
            path.append(nh_ane)

            as_path = ' '.join(action.get('as_path', [])[:-1])
            if as_path not in as_path_dict:
                as_path_ane = 'ane:P_%d' % as_path_idx
                as_path_idx += 1
                as_path_dict[as_path] = as_path_ane
                property_map[as_path_ane] = dict()
                if property_names is not None and 'as_path' in property_names:
                    property_map[as_path_ane]['as_path'] = as_path
            as_path_ane = as_path_dict[as_path]
            path.append(as_path_ane)

            paths[src][dst] = path
        return paths, property_map
