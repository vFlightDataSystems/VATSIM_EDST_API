import itertools
import re
import random
from collections import defaultdict
from typing import Optional

# import geopandas
# import geopy.distance
# from shapely.geometry import Point, shape

from flask import g
from pymongo import MongoClient
from datetime import datetime, timedelta

import mongo_client
import libs.lib
import libs.adr_lib
import libs.adar_lib
from resources.Flightplan import Flightplan

CID_OVERFLOW_RANGE = list('CFNPTVWY')  # list(string.ascii_lowercase)
NM_CONVERSION_FACTOR = 0.86898
KM_NM_CONVERSION_FACTOR = 0.53996

time_mask = '%Y-%m-%d %H:%M:%S.%f'
cid_list = set(f'{a}{b}{c}' for a, b, c in itertools.product(range(10), range(10), range(10)))
cid_overflow_list = set(f'{a}{b}{c}' for a, b, c in itertools.product(range(10), range(10), CID_OVERFLOW_RANGE))


def get_cid(used_cid_list) -> str:
    candidates = list(cid_list - set(used_cid_list))
    if not candidates:
        candidates = list(cid_overflow_list - set(used_cid_list))
    return random.choice(candidates)


def get_edst_data():
    client: MongoClient = g.mongo_edst_client
    return list(client.edst.data.find({}, {'_id': False}))


def get_boundary_data(artcc):
    client: MongoClient = g.mongo_reader_client
    boundary_data = client[artcc.lower()].boundary_data.find_one({}, {'_id': False})
    return boundary_data


# def get_artcc_edst_data(artcc):
#     client: MongoClient = g.mongo_reader_client
#     edst_data = client.edst.data.find({}, {'_id': False})
#     boundary_data = client[artcc.lower()].boundary_data.find_one({}, {'_id': False})
#     geometry = geopandas.GeoSeries(shape(boundary_data['geometry'])).set_crs(epsg=4326).to_crs("EPSG:3857")
#     artcc_data = []
#     # geometry.plot()
#     # plt.savefig(f'{artcc}_boundary_plot.jpg')
#     flightplans = libs.lib.get_all_flightplans().keys()
#     for e in edst_data:
#         if e['callsign'] not in flightplans:
#             continue
#         pos = geopandas.GeoSeries([Point(e['flightplan']['lon'], e['flightplan']['lat'])]) \
#             .set_crs(epsg=4326).to_crs("EPSG:3857")
#         dist = (float(geometry.distance(pos)) / 1000) * KM_NM_CONVERSION_FACTOR
#         if dist < 150:
#             artcc_data.append(e)
#     return artcc_data


def update_edst_data():
    client: MongoClient = mongo_client.get_edst_client()
    reader_client: MongoClient = mongo_client.reader_client
    data = {d['callsign']: d for d in client.edst.data.find({}, {'_id': False})}
    used_cid_list = [d['cid'] for d in data.values()]
    codes_in_use = [d['beacon'] for d in data.values()]
    prefroutes = defaultdict(None)
    for callsign, fp in libs.lib.get_all_flightplans().items():
        if not ((20 < float(fp.lat) < 55) and (-135 < float(fp.lon) < -40)):
            continue
        dep = fp.departure
        dest = fp.arrival
        if callsign in data.keys():
            entry = data[callsign]
            update_time = entry['update_time']
            if datetime.strptime(update_time, time_mask) < datetime.utcnow() + timedelta(minutes=30) \
                    and entry['dep'] == dep and entry['dest'] == dest:
                entry['flightplan'] = vars(fp)
                entry['update_time'] = datetime.utcnow().strftime(time_mask)
                client.edst.data.update_one({'callsign': callsign}, {'$set': entry})
                continue
        dep_info = reader_client.navdata.airports.find_one({'icao': dep.upper()}, {'_id': False})
        if not (dep_info or reader_client.navdata.airports.find_one({'icao': dest.upper()}, {'_id': False})):
            continue
        cid = get_cid(used_cid_list)
        used_cid_list.append(cid)
        beacon = assign_beacon(fp, codes_in_use) or fp.assigned_transponder
        codes_in_use.append(beacon)
        route = fp.route
        aircraft_faa = fp.aircraft_faa.split('/')
        try:
            equipment = (aircraft_faa[-1])[0] if len(aircraft_faa) > 1 else ''
        except IndexError:
            equipment = ''
        # airways = libs.lib.get_airways_on_route(fp.route)
        expanded_route = libs.lib.expand_route(route)
        entry = {
            'callsign': callsign,
            'type': fp.aircraft_short,
            'equipment': equipment,
            'beacon': beacon,
            'dep': dep,
            'dep_info': dep_info,
            'dest': dest,
            'route': libs.lib.format_route(route),
            'route_data': get_route_data(expanded_route),
            'altitude': str(int(fp.altitude)).zfill(3),
            'interim': None,
            'hdg': None,
            'spd': None,
            'hold_fix': None,
            'hold_hdg': None,
            'hold_spd': None,
            'remarks': fp.remarks,
            'cid': cid,
            'scratchpad': '',
            'flightplan': vars(fp)
        }
        route_key = f'{dep}_{dest}'
        if route_key not in prefroutes.keys():
            local_dep = re.sub(r'^K?', '', dep)
            local_dest = re.sub(r'^K?', '', dest)
            cdr = list(reader_client.flightdata.faa_cdr.find({'dep': dep, 'dest': dest}, {'_id': False}))
            pdr = list(reader_client.flightdata.faa_prd.find({'dep': local_dep, 'dest': local_dest}, {'_id': False}))
            for r in cdr:
                r['route_data'] = get_route_data(libs.lib.expand_route(r['route']))
                r['route'] = libs.lib.format_route(re.sub(rf'{dep}|{dest}', '', r['route']))
            for r in pdr:
                r['route_data'] = get_route_data(libs.lib.expand_route(r['route']))
                r['route'] = libs.lib.format_route(r['route'])
            prefroutes[route_key] = cdr + pdr
        adr = libs.adr_lib.get_eligible_adr(fp)
        for a in adr:
            a['route'] = libs.lib.format_route(a['route'])
        adar = libs.adar_lib.get_eligible_adar(fp)
        for a in adar:
            a['route_data'] = get_route_data(libs.lib.expand_route(a['route']))
            a['route'] = libs.lib.format_route(a['route'])
        entry['adr'] = adr
        entry['adar'] = adar
        entry['routes'] = prefroutes[route_key]
        entry['update_time'] = datetime.utcnow().strftime(time_mask)
        client.edst.data.update_one({'callsign': callsign}, {'$set': entry}, upsert=True)
    for callsign, entry in data.items():
        update_time = entry['update_time']
        if datetime.strptime(update_time, time_mask) + timedelta(minutes=30) < datetime.utcnow():
            client.edst.data.delete_one({'callsign': callsign})
    client.close()


def get_edst_entry(callsign: str) -> Optional[dict]:
    client: MongoClient = mongo_client.get_edst_client()
    return client.edst.data.find_one({'callsign': callsign.upper()}, {'_id': False})


def update_edst_entry(callsign, data):
    client: MongoClient = g.mongo_edst_client
    if 'route' in data.keys() and 'route_data' not in data.keys():
        expanded_route = libs.lib.expand_route(re.sub(r'\.+', ' ', data['route']).strip())
        data['route_data'] = get_route_data(expanded_route)
    client.edst.data.update_one({'callsign': callsign}, {'$set': data})
    return client.edst.data.find_one({'callsign': callsign}, {'_id': False})


def get_route_data(expanded_route) -> list:
    client: MongoClient = mongo_client.reader_client
    points = []
    for fix in expanded_route.split():
        if fix_data := client.navdata.waypoints.find_one({'waypoint_id': fix}, {'_id': False}):
            points.append({'fix': fix, 'pos': (float(fix_data['lon']), float(fix_data['lat']))})
    return points


def assign_beacon(fp: Flightplan, codes_in_use) -> Optional[str]:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    code = None
    if fp and (dep_airport_info := client.navdata.airports.find_one({'icao': fp.departure}, {'_id': False})):
        arr_airport_info = client.navdata.airports.find_one({'icao': fp.arrival}, {'_id': False})
        dep_artcc = dep_airport_info['artcc']
        arr_artcc = arr_airport_info['artcc'] if arr_airport_info else None
        beacon_ranges = client.flightdata.beacons.find(
            {'artcc': dep_artcc, 'priority': {'$regex': r'I[PST]?-?\d*', '$options': 'i'}}, {'_id': False}) \
            if dep_artcc == arr_artcc else client.flightdata.beacons.find(
            {'artcc': dep_artcc, 'priority': {'$regex': r'E[PST]?-?\d*', '$options': 'i'}}, {'_id': False})
        for entry in sorted(beacon_ranges, key=lambda b: b['priority']):
            start = int(entry['range_start'], 8)
            end = int(entry['range_end'], 8)
            if beacon_range := list(set(range(start, end)) - set(codes_in_use)):
                code = f'{random.choice(beacon_range):o}'.zfill(4)
                break
    return code
