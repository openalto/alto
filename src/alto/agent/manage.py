import importlib
import logging
from service import Service

from alto.server.components.datasource import DBInfo
from alto.common.logging import fail_with_msg

class AgentService(Service):

    def __init__(self, agent_name, pid_dir, agent_instance=None):
        super().__init__(agent_name, pid_dir)
        self.agent = agent_instance

    def run(self):
        self.agent.run()

def setup_debug_db():
    import alto.server.django_server.django_server.settings as conf_settings
    from alto.server.components.db import data_broker_manager, ForwardingDB, EndpointDB

    for ns, ns_config in conf_settings.DB_CONFIG.items():
        for db_type, db_config in ns_config.items():
            if db_type == 'forwarding':
                db = ForwardingDB(namespace=ns, **db_config)
            elif db_type == 'endpoint':
                db = EndpointDB(namespace=ns, **db_config)
            else:
                db = None
            if db:
                data_broker_manager.register(ns, db_type, db)

if __name__ == '__main__':
    import argparse
    import json

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='OpenALTO Agent Manager')
    subparsers = parser.add_subparsers(title='actions', dest='action')

    start_parser = subparsers.add_parser('start')
    stop_parser = subparsers.add_parser('stop')

    start_parser.add_argument('-c', '--config', dest='config',
                              help='path to the config file')
    start_parser.add_argument('-C', '--class', dest='agent_class',
                              help='python class name')
    start_parser.add_argument('-H', '--host', dest='host',
                              default=None,
                              help='host name of the data store')
    start_parser.add_argument('-p', '--port', dest='port', action='store_const',
                              default=None, const=int,
                              help='port of the data store')
    start_parser.add_argument('-n', '--namespace', dest='namespace',
                              default=None,
                              help='namespace of the agent')
    start_parser.add_argument('-d', '--daemonize', dest='daemonized',
                              action='store_true',
                              default=False,
                              help='daemonize the agent')
    start_parser.add_argument('-D', '--debug', dest='debug',
                              action='store_true',
                              default=False,
                              help='use the debug data broker')
    parser.add_argument('--pid', dest='pid_dir', default=None,
                        help='specify the PID path to be used')

    parser.add_argument('agent_name', metavar='NAME')

    args = parser.parse_args()

    pid_dir = '/var/log/openalto/'
    pid_dir = args.pid_dir if args.pid_dir is not None else pid_dir

    if args.action == 'start':
        with open(args.config, 'r') as f:
            cfg = json.load(f)

        agent_class = cfg.pop('agent_class', None)
        if args.agent_class is not None:
            agent_class = args.agent_class

        try:
            pkg_name, cls_name = agent_class.rsplit('.', 1)
            pkg = importlib.import_module(pkg_name)
            cls = pkg.__getattribute__(cls_name)
        except Exception as e:
            print(e)
            fail_with_msg(logging.CRITICAL, 'Failed to load class %s' % (agent_class))

        host = cfg.pop('host', 'localhost')
        if args.host is not None:
            host = args.host

        port = int(cfg.pop('port', 6793))
        if args.port is not None:
            port = int(args.port)

        namespace = cfg.pop('namespace', 'default')
        if args.namespace is not None:
            namespace = args.namespace

        dbinfo = DBInfo(host, port)
        logging.info('Initializing %s Agent...' % (args.agent_name))

        if args.debug:
            setup_debug_db()

        agent = cls(dbinfo, args.agent_name, namespace, **cfg)
        logging.info('Starting %s Agent...' % (args.agent_name))
        service = AgentService(args.agent_name, pid_dir, agent)

        if args.daemonized:
            service.start()
        else:
            agent.run()
    else:
        logging.info('Stopping %s Agent...' % (args.agent_name))
        service = AgentService(args.agent_name, pid_dir)

        service.stop()
