import hashlib
import json
import uuid

from pytricia import PyTricia


class DataBrokerManager(object):
    """
    Data broker manager singleton.
    """

    pool = dict()

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(DataBrokerManager, cls).__new__(cls)
        return cls.instance

    def register(self, namespace, db_type, db):
        """
        Register a data broker to the pool.

        Parameters
        ----------
        namespace : str
            Namespace of the data broker.
        db_type : str
            Type of the data broker. Currently supported types:
                - forwarding
                - endpoint
        db : DataBroker
            A data broker instance.
        """
        if namespace not in self.pool:
            self.pool[namespace] = dict()
        self.pool[namespace][db_type] = db

    def get(self, namespace, db_type):
        """
        Get a registered data broker.

        Parameters
        ----------
        namespace : str
            Namespace of the data broker.
        db_type : str
            Type of the data broker. Currently supported types:
                - forwarding
                - endpoint

        Returns
        -------
        DataBroker
        """
        return self.pool.get(namespace, dict()).get(db_type)


data_broker_manager = DataBrokerManager()


class LocalDB:
    """
    The implemetation of a simple local database backend.

    Support basic key-value store update, lookup, and transaction.
    """

    def __init__(self, **kwargs):
        self._base = dict()

    def get(self, key):
        return self._base.get(key)

    def set(self, key, val):
        self._base[key] = val

    def pipeline(self):
        return LocalPipe(self)


class LocalPipe:
    """
    The implementation of a simple transaction for LocalDB.

    Simulate the basic Redis pipeline API.
    """

    def __init__(self, db):
        self.db = db
        self._base = self.db._base.copy()

    def set(self, key, val):
        self._base[key] = val

    def execute(self):
        self.db._base = self._base


class DataBroker:
    """
    Base class of the data broker.

    Parameters
    ----------
    namespace : str
        Namespace of the data broker.
    backend : str
        Backend database. Currently supported backends:
            - local
            - redis
    """

    def __init__(self, namespace='default', backend='redis', **kwargs):
        self.ns = namespace
        self.backend = backend
        if backend == 'local':
            self._backend = LocalDB(**kwargs)
        elif backend == 'redis':
            import redis
            self._backend = redis.Redis(**kwargs)
        else:
            # TODO: define common errors for ALTO DB
            raise NotImplementedError
        data_broker_manager.register(self.ns, self.type, self)

    def _lookup(self, key):
        """
        Lookup value by key.

        Parameters
        ----------
        key : str
            The hash string used to lookup the value. The data broker will
            combine the key with the prefix `namespace` as the full key to query
            the backend database.

        Returns
        -------
        Value
        """
        if type(key) is bytes:
            key = key.decode()
        full_key = '{}:{}'.format(self.ns, key)
        return self._backend.get(full_key)

    def _parse_key(self, key):
        componets = key.split(b':')
        return b':'.join(componets[2:-1]), b':'.join(componets[1:])

    def build_cache(self):
        """
        Build local cache of remote database for efficient lookup.
        """
        # TODO: Separate read capability (`build_cache` and `lookup`) and write
        # capability (`new_transaction`) into different classes
        # TODO: Use pubsub feature to trigger `build_cache` method
        raise NotImplementedError()

    def new_transaction(self):
        """
        Start a new transaction.

        Returns
        -------
        Transaction
        """
        return Transaction(self)


class Match(object):
    """
    Class of the packet match.
    """

    def __init__(self, dst_prefix, in_port=None, **pktattr):
        self.dst_prefix = dst_prefix
        self.in_port = in_port
        self.optional_attr = pktattr

    def to_dict(self):
        m = dict()
        m['dst_prefix'] = self.dst_prefix
        if self.in_port:
            m['in_port'] = self.in_port
        for k, v in self.optional_attr:
            m[k] = v
        return m

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True)

    def to_hash(self):
        h = hashlib.sha256()
        h.update(self.to_json().encode())
        return h.hexdigest()


class Action(object):
    """
    Class of the forwarding action.
    """

    def __init__(self, next_hop=None, protocol=None, **actions):
        self.next_hop = next_hop
        self.protocol = protocol
        self.actions = actions

    def to_dict(self):
        action = dict()
        if self.next_hop:
            action['next_hop'] = self.next_hop
        if self.protocol:
            action['protocol'] = self.protocol
        for k, v in self.actions.items():
            action[k] = v
        return action


class ForwardingRule(object):
    """
    Class of the forwarding rule.
    """

    def __init__(self, pkt_match: Match, action: Action):
        self.pkt_match = pkt_match
        self.action = action

    def to_dict(self):
        rule = dict()
        rule['match'] = self.pkt_match.to_dict()
        rule['action'] = self.action.to_dict()
        return rule

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True)


class ForwardingDB(DataBroker):
    """
    Class of the data broker maintaining forwarding information.
    """

    def __init__(self, namespace='default', backend='redis', **kwargs):
        self.type = 'forwarding'
        self._base = dict()
        super().__init__(namespace=namespace, backend=backend, **kwargs)

    def build_cache(self):
        _base = dict()
        if self.backend == 'redis':
            keys = self._backend.scan_iter(match='{}:{}:*'.format(self.ns, self.type))
        else:
            raise NotImplementedError()
        for key in keys:
            dpid, suffix_key = self._parse_key(key)
            rule_json = self._backend.get(key)
            rule_dict = json.loads(rule_json)
            match_dict = rule_dict.get('match', dict())

            if dpid not in _base:
                _base[dpid] = PyTricia(128)
            dst_prefix = match_dict.get('dst_prefix')
            if dst_prefix not in _base[dpid]:
                _base[dpid][dst_prefix] = dict()
            in_port = match_dict.get('in_port')
            if not in_port:
                in_port = '0'
            _base[dpid][dst_prefix][in_port] = suffix_key
        for dpid in _base.keys():
            self._base[dpid] = _base[dpid]

    def lookup(self, dpid, dst_ip, in_port='0', **pktattr):
        """
        Get a forwarding entry by packet filter.

        Parameters
        ----------
        dpid : str
            Datapath ID to reference a logical forwarding device.
        dst_ip : str
            Destination IP address.
        in_port : str
            Name of the incoming interface.
        pktattr : dict
            optional packet attributes to filter forwarding entries.

        Returns
        -------
        Action
        """
        if type(dpid) is str:
            dpid = dpid.encode()
        dst_trie = self._base.get(dpid)
        if not dst_trie:
            return Action()
        ingress_trie = dst_trie.get(dst_ip)
        if not ingress_trie:
            return Action()
        hash_key = ingress_trie.get(in_port)
        if not hash_key:
            return Action()
        rule_json = self._lookup(hash_key)
        rule_dict = json.loads(rule_json)
        action_dict = rule_dict.get('action', dict())
        return Action(**action_dict)

    def new_transaction(self):
        return ForwardingTransaction(self)


class Transaction:
    """
    Base class of a database transaction operation.
    """

    def __init__(self, db):
        self.db = db
        self._pipe = self.db._backend.pipeline()

    def commit(self):
        """
        Commit this transaction to the backend database.
        """
        self._pipe.execute()


class ForwardingTransaction(Transaction):
    """
    Class of the trasaction for forwarding database.
    """

    def __init__(self, db):
        super().__init__(db)
        self._dpids = set()

    def add_rule(self, dpid, rule: ForwardingRule):
        """
        Add a forwarding rule into the database.

        Parameters
        ----------
        dpid : str
            Datapath ID.
        rule : ForwardingRule
            A forwarding rule.
        """
        if dpid not in self._dpids:
            self._dpids.add(dpid)
            if self.db.backend == 'redis':
                keys = list(self.db._backend.scan_iter(match='{}:{}:{}:*'.format(self.db.ns, self.db.type, dpid)))
            else:
                raise NotImplementedError()
            if len(keys) > 0:
                self._pipe.delete(*keys)
        full_key = '{}:{}:{}:{}'.format(self.db.ns, self.db.type, dpid, uuid.uuid1())
        self._pipe.set(full_key, rule.to_json())

    def commit(self):
        self._pipe.execute()


class EndpointDB(DataBroker):
    """
    Class of the data broker maintaining properties associated with endpoints.
    """

    def __init__(self, namespace='default', backend='redis', **kwargs):
        self.type = 'endpoint'
        self._base = dict()
        super().__init__(namespace=namespace, backend=backend, **kwargs)

    def build_cache(self):
        _base = dict()
        if self.backend == 'redis':
            keys = self._backend.scan_iter(match='{}:{}:*'.format(self.ns, self.type))
        else:
            raise NotImplementedError()
        for key in keys:
            prop_name, suffix_key = self._parse_key(key)
            prop_json = self._backend.get(key)
            prop_dict = json.loads(prop_json)
            endpoint = prop_dict.get('endpoint')
            if not endpoint:
                continue

            if prop_name not in _base:
                _base[prop_name] = PyTricia(128)
            _base[prop_name][endpoint] = suffix_key
        for prop_name in _base.keys():
            self._base[prop_name] = _base[prop_name]

    def lookup(self, endpoint, property_names=None):
        """
        Get properties associated with an endpoint.

        Parameters
        ----------
        endpoint : str
            IP address or prefix of an endpoint.
        property_names : list
            A list of property names to query.

        Returns
        -------
        properties : dict
            A dictionary of properties for the given endpoint.
        """
        properties = dict()
        if property_names is None:
            property_names = self._base.keys()
        for prop_name in property_names:
            if type(prop_name) is str:
                prop_name = prop_name.encode()
            prop_trie = self._base.get(prop_name)
            if prop_trie:
                hash_key = prop_trie.get(endpoint)
                if hash_key:
                    prop_json = self._lookup(hash_key)
                    prop_dict = json.loads(prop_json)
                    properties[prop_name.decode()] = prop_dict.get('val')
        return properties

    def new_transaction(self):
        return EndpointTransaction(self)


class EndpointTransaction(Transaction):
    """
    Class of the trasaction for endpoint database.
    """
    def __init__(self, db):
        super().__init__(db)
        self.prop_names = set()

    def add_property(self, endpoint, properties):
        """
        Add properties for an endpoint.

        Parameters
        ----------
        endpoint : src
            IP address or prefix.
        proprties : dict
            Properties of the given endpoint.
        """
        for prop_name, prop_val in properties.items():
            if prop_name not in self.prop_names:
                self.prop_names.add(prop_name)
                if self.db.backend == 'redis':
                    keys = list(self.db._backend.scan_iter(match='{}:{}:{}:*'.format(self.db.ns, self.db.type, prop_name)))
                else:
                    raise NotImplementedError()
                if len(keys) > 0:
                    self._pipe.delete(*keys)

            full_key = '{}:{}:{}:{}'.format(self.db.ns, self.db.type, prop_name, uuid.uuid1())
            prop_obj = dict()
            prop_obj['endpoint'] = endpoint
            prop_obj['val'] = prop_val
            self._pipe.set(full_key, json.dumps(prop_obj, sort_keys=True))

    def commit(self):
        self._pipe.execute()
