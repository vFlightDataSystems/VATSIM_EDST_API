class AdaptationProfile:

    def __init__(self, profile=None):
        self.climbout_options = profile['climbout_options'] if 'climbout_options' in profile.keys() else []
        self.climbvia_options = profile['climbvia_options'] if 'climbvia_options' in profile.keys() else []
        self.initial_altitude_options = profile['initial_alt_options']\
            if 'initial_alt_options' in profile.keys() else []
        self.expect_cruise_options = profile['expect_options'] \
            if 'expect_options' in profile.keys() else []
        self.dep_freq_options = profile['dep_freq_options'] if 'dep_freq_options' in profile.keys() else []
        self.contact_info_options = profile['contact_info_options'] if 'contact_info_options' in profile.keys() else []
        self.local_info_options = profile['local_info_options'] if 'local_info_options' in profile.keys() else []
        self.facility = profile['facility'] if 'facility' in profile.keys() else ''
        self.profile_name = profile['profile_name'] if 'profile_name' in profile.keys() else ''
        self.username = profile['username'] if 'username' in profile.keys() else ''
