import itertools
import logging
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
import libs.aar_lib
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


def get_ctr_fav_data(artcc):
    client: MongoClient = g.mongo_reader_client
    fav_data = list(client[artcc.lower()].ctr_fav.find({}, {'_id': False}))
    return fav_data


def get_app_fav_data(artcc):
    client: MongoClient = g.mongo_reader_client
    fav_data = list(client[artcc.lower()].app_fav.find({}, {'_id': False}))
    return fav_data


def get_ctr_profiles(artcc):
    client: MongoClient = g.mongo_reader_client
    profiles = list(client[artcc.lower()].ctr_profiles.find({}, {'_id': False}))
    return profiles


def update_edst_data():
    client: MongoClient = mongo_client.get_edst_client()
    reader_client: MongoClient = mongo_client.reader_client
    edst_entries = {d['callsign']: d for d in client.edst.data.find({}, {'_id': False})}
    used_cid_list = [d['cid'] for d in edst_entries.values()]
    codes_in_use = [d['beacon'] for d in edst_entries.values()]
    prefroutes = defaultdict(None)
    for vatsim_callsign, vatsim_fp in libs.lib.get_all_flightplans().items():
        if not ((20 < float(vatsim_fp.lat) < 55) and (-135 < float(vatsim_fp.lon) < -40)):
            continue
        dep = vatsim_fp.departure
        dest = vatsim_fp.arrival
        if vatsim_callsign in edst_entries.keys():
            new_edst_entry = edst_entries[vatsim_callsign]
            update_time = new_edst_entry['update_time']
            if datetime.strptime(update_time, time_mask) > datetime.utcnow() - timedelta(minutes=30) \
                    and new_edst_entry['dep'] == dep and new_edst_entry['dest'] == dest:
                # if no manual amendments have been made in the last minute, update the flightplan
                if 'manual_update_time' not in new_edst_entry.keys() \
                        or datetime.strptime(new_edst_entry['manual_update_time'],
                                             time_mask) > datetime.utcnow() - timedelta(minutes=1):
                    if vatsim_fp.route != new_edst_entry['flightplan']['route']:
                        new_edst_entry['route'] = libs.lib.format_route(vatsim_fp.route)
                        expanded_route = libs.lib.expand_route(new_edst_entry['route'], [dep, dest])
                        new_edst_entry['route_data'] = get_route_data(expanded_route)
                    new_edst_entry['altitude'] = str(int(vatsim_fp.altitude)).zfill(3)
                new_edst_entry['flightplan'] = vars(vatsim_fp)
                new_edst_entry['update_time'] = datetime.utcnow().strftime(time_mask)
                client.edst.data.update_one({'callsign': vatsim_callsign}, {'$set': new_edst_entry})
                continue
        # if brand new or outdated or dep/dest changed
        dep_info = reader_client.navdata.airports.find_one({'icao': dep.upper()}, {'_id': False, 'procedures': False})
        dest_info = reader_client.navdata.airports.find_one({'icao': dest.upper()}, {'_id': False, 'procedures': False})
        if not dep_info and not dest_info:
            continue
        # TODO: cid class
        cid = get_cid(used_cid_list)
        used_cid_list.append(cid)
        # TODO: beacon class
        beacon = assign_beacon(vatsim_fp, codes_in_use) or '0000'
        # if beacon is None:
        #     artcc = dep_info['artcc'].upper() if dep_info else dest_info['artcc'].upper()
        #     beacon = get_beacon(artcc, codes_in_use)
        codes_in_use.append(beacon)
        vatsim_route = vatsim_fp.route
        aircraft_faa = vatsim_fp.aircraft_faa.split('/')
        try:
            equipment = (aircraft_faa[-1])[0] if len(aircraft_faa) > 1 else ''
        except IndexError:
            equipment = ''
        # airways = libs.lib.get_airways_on_route(fp.route)
        expanded_route = libs.lib.expand_route(libs.lib.format_route(vatsim_route), [dep, dest])
        route_key = f'{dep}_{dest}'
        # write formatted route and route_data for prefroutes into database
        if route_key not in prefroutes.keys():
            local_dep = re.sub(r'^K?', '', dep)
            local_dest = re.sub(r'^K?', '', dest)
            cdr = list(reader_client.flightdata.faa_cdr.find({'dep': dep, 'dest': dest}, {'_id': False}))
            prd = list(reader_client.flightdata.faa_prd.find({'dep': local_dep, 'dest': local_dest}, {'_id': False}))
            for r in cdr:
                r['route_data'] = get_route_data(libs.lib.expand_route(' '.join(r['route'].split('.')), [dep, dest]))
                r['route'] = libs.lib.format_route(re.sub(rf'{dep}|{dest}', '', r['route']))
            for r in prd:
                r['route_data'] = get_route_data(libs.lib.expand_route(r['route'], [dep, dest]))
            prefroutes[route_key] = cdr + prd
        adr = libs.adr_lib.get_adr(vatsim_fp)
        for a in adr:
            amendment = libs.adr_lib.amend_adr(vatsim_route, a)
            a['amendment'] = amendment
        adar = libs.adar_lib.get_adar(vatsim_fp)
        for a in adar:
            a['route_data'] = get_route_data(a['route_fixes'])
            a['route'] = libs.lib.format_route(a['route'])
        new_edst_entry = {'callsign': vatsim_callsign, 'type': vatsim_fp.aircraft_short, 'equipment': equipment,
                          'beacon': beacon, 'dep': dep,
                          'dep_info': dep_info, 'dest': dest, 'dest_info': dest_info,
                          'route': libs.lib.format_route(vatsim_route),
                          'route_data': get_route_data(expanded_route),
                          'altitude': str(int(vatsim_fp.altitude)).zfill(3),
                          'interim': None, 'hdg': None, 'spd': None, 'hold_fix': None, 'hold_hdg': None,
                          'hold_spd': None,
                          'remarks': vatsim_fp.remarks, 'cid': cid, 'scratchpad': '', 'flightplan': vars(vatsim_fp),
                          'adr': adr, 'adar': adar,
                          'routes': prefroutes[route_key], 'update_time': datetime.utcnow().strftime(time_mask)}
        client.edst.data.update_one({'callsign': vatsim_callsign}, {'$set': new_edst_entry}, upsert=True)
    # remove outdated entries
    for callsign, edst_entry in edst_entries.items():
        update_time = edst_entry['update_time']
        if datetime.strptime(update_time, time_mask) < datetime.utcnow() - timedelta(minutes=30):
            client.edst.data.delete_one({'callsign': callsign})
    client.close()


def get_edst_entry(callsign: str) -> Optional[dict]:
    client: MongoClient = mongo_client.get_edst_client()
    return client.edst.data.find_one({'callsign': callsign.upper()}, {'_id': False})


def update_edst_entry(callsign: str, data: dict):
    client: MongoClient = g.mongo_edst_client
    keys = data.keys()
    if 'route' in keys and 'route_data' not in keys:
        data['route'] = libs.lib.format_route(data['route'])
        expanded_route = libs.lib.expand_route(data['route'], [data['dest']] if 'dest' in keys else None)
        data['route_data'] = get_route_data(expanded_route)
    data['manual_update_time'] = datetime.utcnow().strftime(time_mask)
    client.edst.data.update_one({'callsign': callsign}, {'$set': data})
    return client.edst.data.find_one({'callsign': callsign}, {'_id': False})


def get_amended_route(route: str = None,
                      route_data: list = None,
                      direct_fix: str = None,
                      frd: dict = None,
                      dest: str = None):
    if route and direct_fix:
        if route_data is None:
            route_data = get_route_data(libs.lib.expand_route(route, [dest] if dest else None))
        route_fixes = [e['name'] for e in route_data]
        frd_str = f'{frd["waypoint_id"]}{str(int(frd["bearing"])).zfill(3)}{str(int(frd["distance"])).zfill(3)}'
        if direct_fix in route_fixes:
            index = route_fixes.index(direct_fix)
            route_data = route_data[index:]
            for fix in reversed(route_fixes[:index + 1]):
                if fix in route:
                    route = route[route.index(fix) + len(fix):]
                    if not route[0].isdigit():
                        route = f'{frd_str}..{direct_fix}' + route
                    else:
                        route = f'{frd_str}..{direct_fix}.{fix}' + route
                    break
            if frd:
                frd_pos = libs.lib.get_frd_coordinates(float(frd["lat"]), float(frd["lon"]), float(frd["bearing"]),
                                                       float(frd["distance"]))
                route_data = [{'name': frd_str, 'pos': frd_pos}] + route_data
            amend_data = {'route': route, 'route_data': route_data}
            return amend_data
        else:
            return None
    elif route:
        if route_data is None:
            expanded_route = libs.lib.expand_route(route)
            route_data = get_route_data(expanded_route)
        if frd:
            frd = f'{frd["waypoint_id"]}{str(int(frd["bearing"])).zfill(3)}{str(int(frd["distance"])).zfill(3)}'
            route = f'{frd}..{route}'
        amend_data = {'route': libs.lib.format_route(route), 'route_data': route_data}
        return amend_data
    return None


def get_route_data(fixes: list) -> list:
    """

    :rtype: list
    """
    client: MongoClient = mongo_client.reader_client
    points = []
    for fix in fixes:
        try:
            if match := re.match(r'(\w+)(\d{3})(\d{3})', fix):
                fix, bearing, distance = match.groups()
                wpt = client.navdata.waypoints.find_one({'waypoint_id': fix}, {'_id': False})
                frd_pos = libs.lib.get_frd_coordinates(wpt["lat"], wpt["lon"], bearing, distance)
                points.append({'name': fix, 'pos': frd_pos})
        except Exception as e:
            print(e)
            logging.Logger(str(e))
        if fix_data := client.navdata.waypoints.find_one({'waypoint_id': fix}, {'_id': False}):
            points.append({'name': fix, 'pos': (float(fix_data['lon']), float(fix_data['lat']))})
    return points


def assign_beacon(fp: Flightplan, codes_in_use) -> Optional[str]:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    code = None
    if fp and (dep_airport_info := client.navdata.airports.find_one({'icao': fp.departure}, {'_id': False})):
        arr_airport_info = client.navdata.airports.find_one({'icao': fp.arrival}, {'_id': False})
        dep_artcc = dep_airport_info['artcc'].upper()
        arr_artcc = arr_airport_info['artcc'].upper() if arr_airport_info else None
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


def get_beacon(artcc, codes_in_use):
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    beacon_ranges = client.flightdata.beacons.find(
        {'artcc': artcc.upper(), 'priority': {'$regex': r'E[PST]?-?\d*', '$options': 'i'}}, {'_id': False})
    code = '0000'
    if beacon_ranges:
        for entry in sorted(beacon_ranges, key=lambda b: b['priority']):
            start = int(entry['range_start'], 8)
            end = int(entry['range_end'], 8)
            if beacon_range := list(set(range(start, end)) - set(codes_in_use)):
                code = f'{random.choice(beacon_range):o}'.zfill(4)
                break
    return code


def get_edst_aar(artcc: str, cid: str, route=None) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    edst_entry = client.edst.data.find_one({'cid': cid}, {'_id': False})
    if edst_entry is None:
        return []
    if route is None:
        route = edst_entry['route']
    aar_list = libs.aar_lib.get_aar(edst_entry, artcc, route=route)
    for aar in aar_list:
        aar['amendment'] = libs.aar_lib.amend_aar(route, aar)
    return aar_list
