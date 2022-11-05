from django.urls import path

from alto.config import Config

from . import views


def generate_northbound_routes():
    config = Config()
    default_namespace = config.get_default_namespace()
    resources = config.get_configured_resources()

    urlpatterns = []
    for resource_id, resource_config in resources.items():
        base_path = resource_config.get('path')
        namespace = resource_config.get('namespace', default_namespace)
        algorithm = resource_config.get('algorithm')
        params = resource_config.get('params', dict())
        view = views.get_view(resource_config.get('type'), resource_id, namespace, algorithm, params)
        if view:
            urlpatterns.append(path('{}/{}'.format(base_path, resource_id), view, name=resource_id))
    return urlpatterns


urlpatterns = generate_northbound_routes()
