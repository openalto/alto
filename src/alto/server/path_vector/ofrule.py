import ipaddress

# url_format % (address, vSwitch)
import requests

TABLE_URL_FORMAT = "http://%s:8181/restconf/operational/opendaylight-inventory:nodes/node/openflow:%s/table/0"

class Switch:
    """
    name - name of the switch
    ports - a list of ports
    """

    def __init__(self, name, domain, opf_version, ports):
        self._name = name
        self._domain = domain
        self._controller = self._domain.split(":")[1]
        self._opf_version = opf_version
        self._ports = ports
        self._rules = []
        self.get_rules()

    def add_rules(self, rules):
        for r in rules:
            self._rules.append(self.Rule(**r))

    def get_rules(self):
        table = requests.get(TABLE_URL_FORMAT % (self._controller, self._name[1:])).json()
        for flow in table['flow-node-inventory:table'][0]['flow']:
            match = {}
            for k in flow['match'].keys():
                if k == 'in-port':
                    match.update({'ingress': self._name + "-eth" + flow['match'][k]})
                elif k == 'ipv4-source':
                    match.update({'sip': flow['match'][k]})
                elif k == 'ipv4-destination':
                    match.update({'dip': flow['match'][k]})
            priority = flow['priority']
            actions = []
            for action in flow['instructions']['instruction'][0]['apply-actions']['action']:
                actions.append(self._name + "-eth" + action['output-action']['output-node-connector'])
            self._rules.append(self.Rule(match, priority, actions))

    def find_matching_rule(self, ingress=None, sip=None, dip=None):
        rules = sorted(self._rules, key=lambda r: r.priority, reverse=True)
        for r in rules:
            if r.match(ingress, sip, dip):
                return r.get_actions()
        return []

    @property
    def name(self):
        return self._name

    @property
    def controller(self):
        return self._controller

    @property
    def opf_version(self):
        return self._opf_version

    class Rule:
        """
        match - a dict of (field -> value)
        priority - an interger
        actions - a list of egress ports
        """

        def __init__(self, match, priority, actions):
            self._match = match
            self._priority = priority
            self._actions = actions

        def _match_ipv4(self, ip_str, net_str):
            net = ipaddress.IPv4Network(net_str)
            addr = ipaddress.ip_address(ip_str)
            return addr in net

        def match(self, ingress=None, sip=None, dip=None):
            if 'ingress' in self._match:
                if ingress is None:
                    return False
                if ingress != self._match['ingress']:
                    return False
            if 'sip' in self._match:
                if sip is None:
                    return False
                if not self._match_ipv4(sip, self._match['sip']):
                    return False
            if 'dip' in self._match:
                if dip is None:
                    return False
                if not self._match_ipv4(dip, self._match['dip']):
                    return False
            return True

        def get_actions(self):
            return self._actions

        @property
        def priority(self):
            return self._priority
