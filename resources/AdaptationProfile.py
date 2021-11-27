class AdaptationProfile:

    def __init__(self, profile=None):
        self.climbout_options = profile['climbout_options'] if 'climbout_options' in profile.keys() else []
        self.climbvia_options = profile['climbvia_options'] if 'climbvia_options' in profile.keys() else []
        self.initial_altitude_options = profile['initial_altitude_options']\
            if 'initial_altitude_options' in profile.keys() else []
        self.expect_cruise_options = profile['expect_cruise_options'] \
            if 'expect_cruise_options' in profile.keys() else []
        self.dep_freq_options = profile['dep_freq_options'] if 'dep_freq_options' in profile.keys() else []
        self.facility = profile['facility'] if 'facility' in profile.keys() else ''
        self.name = profile['name'] if 'name' in profile.keys() else ''
