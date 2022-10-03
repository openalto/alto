import uuid
import hashlib
import json

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
        # key_hash = hashlib.sha256()
        # key_hash.update(json.dumps(kwargs, sort_keys=True).encode())
        full_key = '{}:{}'.format(self.ns, key)
        return self._backend.get(full_key)

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


class ForwardingDB(DataBroker):
    """
    Class of the data broker maintaining forwarding information.
    """

    def __init__(self, namespace='default', backend='redis', **kwargs):
        self.type = 'forwarding'
        self._base = dict()
        super().__init__(namespace=namespace, backend=backend, **kwargs)

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
        dst_trie = self._base.get(dpid)
        if not dst_trie:
            return Action()
        ingress_trie = dst_trie.get(dst_ip)
        if not ingress_trie:
            return Action()
        hash_key = ingress_trie.get(in_port)
        if not hash_key:
            return Action()
        action_dict = self._lookup(hash_key)
        return Action(**action_dict)

    def new_transaction(self):
        return ForwardingTransaction(self)


class Transaction:
    """
    Base class of a database transaction operation.
    """

    def __init__(self, db):
        self.db = db
        # TODO: decouple database backend with high-level transaction
        # abstraction
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
        self._base = dict()
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
        self._dpids.add(dpid)
        if dpid not in self._base:
            self._base[dpid] = PyTricia(128)
        dst_prefix = rule.pkt_match.dst_prefix
        if dst_prefix not in self._base[dpid]:
            self._base[dpid][dst_prefix] = dict()
        in_port = rule.pkt_match.in_port
        if not in_port:
            in_port = '0'
        key = rule.pkt_match.to_hash()
        self._base[dpid][dst_prefix][in_port] = key

        full_key = '{}:{}'.format(self.db.ns, key)
        self._pipe.set(full_key, rule.action.to_dict())

    def commit(self):
        for dpid in self._dpids:
            self.db._base[dpid] = self._base[dpid]
        self._pipe.execute()


class EndpointDB(DataBroker):
    """
    Class of the data broker maintaining properties associated with endpoints.
    """

    def __init__(self, namespace='default', backend='redis', **kwargs):
        self.type = 'endpoint'
        self._base = dict()
        super().__init__(namespace=namespace, backend=backend, **kwargs)

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
            prop_trie = self._base.get(prop_name)
            if prop_trie:
                hash_key = prop_trie.get(endpoint)
                if hash_key:
                    properties[prop_name] = self._lookup(hash_key)
        return properties

    def new_transaction(self):
        return EndpointTransaction(self)


class EndpointTransaction(Transaction):
    """
    Class of the trasaction for endpoint database.
    """
    def __init__(self, db):
        super().__init__(db)
        self._base = dict()

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
            if prop_name not in self._base:
                self._base[prop_name] = PyTricia(128)
            h = hashlib.sha256()
            h.update('{} - {}'.format(prop_name, endpoint).encode())
            key = h.hexdigest()
            self._base[prop_name][endpoint] = key

        full_key = '{}:{}'.format(self.db.ns, key)
        self._pipe.set(full_key, prop_val)

    def commit(self):
        for prop_name in self._base.keys():
            self.db._base[prop_name] = self._base[prop_name]
        self._pipe.execute()
