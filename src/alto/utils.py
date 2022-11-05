import importlib


def load_class(class_path):
    pkg_name, cls_name = class_path.rsplit('.', 1)
    pkg = importlib.import_module(pkg_name)
    return pkg.__getattribute__(cls_name)
