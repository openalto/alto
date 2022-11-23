import importlib
import logging
import time
from service import Service

from alto.server.components.datasource import DBInfo
from alto.common.logging import fail_with_msg
from alto.utils import load_class

class AgentService(Service):

    def __init__(self, agent_name, pid_dir, agent_instance=None):
        super().__init__(agent_name, pid_dir)
        self.agent = agent_instance

    def run(self):
        while True:
            try:
                self.agent.run()
            except Exception as e:
                logging.info('Agent service stopped by an exception: {}'.format(e))
                logging.info('Restarting the agent service after 10 sec...')
                time.sleep(10)


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
            cls = load_class(agent_class)
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
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)
            from alto.config import Config
            from alto.utils import setup_debug_db
            config = Config()
            setup_debug_db(config)

        agent = cls(dbinfo, args.agent_name, namespace, **cfg)
        logging.info('Starting %s Agent...' % (args.agent_name))
        service = AgentService(args.agent_name, pid_dir, agent)

        if args.daemonized:
            service.start()
        else:
            try:
                agent.run()
            except KeyboardInterrupt:
                pass
    else:
        logging.info('Stopping %s Agent...' % (args.agent_name))
        service = AgentService(args.agent_name, pid_dir)

        service.stop()
