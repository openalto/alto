from alto.common.error import NotSupportedError


class GeoipAgent:

    def __init__(self, db_path=None, account_id=None, license_key=None,
                 geolite=True):
        self.access_type = None
        self.geolite = geolite
        if db_path:
            from geoip2.database import Reader
            self.db_path = db_path
            self.access_type = 'database'
            self.client = Reader(self.db_path)
        elif account_id and license_key:
            from geoip2.webservice import Client
            self.account_id = account_id
            self.licence_key = license_key
            self.access_type = 'webservice'
            kwargs = dict()
            if self.geolite:
                kwargs['host'] = 'geolite.info'
            self.client = Client(self.account_id, self.licence_key, **kwargs)
        else:
            raise NotSupportedError("Either 'db_path' or ('account_id', 'license_key') should present.")

    def lookup(self, endpoints):
        geomap = dict()
        for endpoint in endpoints:
            geoinfo = self.client.city(endpoint)
            geomap[endpoint] = (geoinfo.location.latitude, geoinfo.location.longtitude)
        return geomap
