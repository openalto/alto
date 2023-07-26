import importlib


def load_class(class_path):
    pkg_name, cls_name = class_path.rsplit('.', 1)
    pkg = importlib.import_module(pkg_name)
    return pkg.__getattribute__(cls_name)

def setup_debug_db(config):
    from alto.server.components.db import data_broker_manager, ForwardingDB, EndpointDB, DelegateDB

    for ns, ns_config in config.get_db_config().items():
        for db_type, db_config in ns_config.items():
            db = data_broker_manager.get(ns, db_type)
            if db is None:
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
