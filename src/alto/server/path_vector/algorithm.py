COST_MAP_MEDIA_TYPE = 'application/alto-costmap+json'

class ALTOInformationResource:

    def __init__(self, media_type):
        self.media_type = media_type

class ALTOCostMap(ALTOInformationResource):

    def __init__(self, cost_mode, cost_metric):
        ALTOInformationResource.__init__(self, COST_MAP_MEDIA_TYPE)
        self.cost_mode = cost_mode
        self.cost_metric = cost_metric