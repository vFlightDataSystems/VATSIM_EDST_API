import re
from math import radians, sin, cos, sqrt, atan2

def matches_airway_format(s: str) -> bool:
    return bool(re.match(r'^[A-Z]{1,2}\d+$', s))


def matches_sid_star_format(s: str) -> bool:
    return bool(re.match(r'^[A-Z]{3,}\d[A-Z]?$', s))


def matches_any_route_segment_format(s: str) -> bool:
    return matches_airway_format(s) or matches_sid_star_format(s)


def matches_any_fix_format(s: str) -> bool:
    return bool(re.match(r'[A-Z]{2,5}|[A,Z]{2}\d{3}$', s)) or matches_any_custom_fix_format(s)


def matches_frd_format(s: str) -> bool:
    return bool(re.match(r'^[A-Z]{2,5}\d{6}$', s))


def matches_deg_only_lat_lon_format(s: str) -> bool:
    return bool(re.match(r'^\d\d[NS]\d\d\d[EW]$', s))


def matches_deg_min_lat_lon_format(s: str) -> bool:
    return bool(re.match(r'^\d{4}[NS]?/\d{5}[EW]?$', s))


def matches_any_custom_fix_format(s: str) -> bool:
    return matches_frd_format(s) or matches_deg_only_lat_lon_format(s) or matches_deg_min_lat_lon_format(s)

def haversine_distance(lat1, lon1, lat2, lon2):
  R = 3440.065  # Earth radius in nautical miles
  lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
  dlat = lat2 - lat1
  dlon = lon2 - lon1
  a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
  c = 2 * atan2(sqrt(a), sqrt(1-a))
  return R * c
