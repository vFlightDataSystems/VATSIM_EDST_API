import itertools
import re
import random
from collections import defaultdict
from typing import Optional

import geopy.distance

from flask import g
from pymongo import MongoClient
from datetime import datetime, timedelta

import mongo_client
import libs.lib
import libs.adr_lib
import libs.adar_lib

CID_OVERFLOW_RANGE = list('CFNPTVWY')  # list(string.ascii_lowercase)

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


def format_remaining_route(entry, remaining_route_data):
    split_route = entry['raw_route'].split()
    remaining_fixes = [e['fix'] for e in remaining_route_data]
    if first_common_fix := next(iter([fix for fix in remaining_fixes if fix in split_route]), None):
        index = split_route.index(first_common_fix)
        split_route = split_route[index:]
        if first_common_fix not in split_route:
            split_route.insert(0, first_common_fix)
        return libs.lib.format_route(' '.join(split_route))
    else:
        return None


def update_edst_data():
    client: MongoClient = mongo_client.get_edst_client()
    reader_client: MongoClient = mongo_client.get_reader_client()
    data = {d['callsign']: d for d in client.edst.data.find({}, {'_id': False})}
    used_cid_list = [d['cid'] for d in data.values()]
    prefroutes = defaultdict(None)
    for callsign, fp in libs.lib.get_all_flightplans().items():
        dep = fp.departure
        dest = fp.arrival
        if callsign in data.keys():
            entry = data[callsign]
            update_time = entry['update_time']
            if datetime.strptime(update_time, time_mask) < datetime.utcnow() + timedelta(hours=1) \
                    and entry['dep'] == dep and entry['dest'] == dest:
                remaining_route_data = get_remaining_route_data(callsign)
                entry['flightplan'] = vars(fp)
                entry['update_time'] = datetime.utcnow().strftime(time_mask)
                entry['remaining_route_data'] = remaining_route_data
                entry['remaining_route'] = format_remaining_route(entry, remaining_route_data)
                client.edst.data.update_one({'callsign': callsign}, {'$set': entry})
                continue
        if not reader_client.navdata.airports.find_one({'icao': dep.upper()}, {'_id': False}):
            continue
        cid = get_cid(used_cid_list)
        used_cid_list.append(cid)
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
            'beacon': fp.assigned_transponder,
            'dep': dep,
            'dest': dest,
            'route': libs.lib.format_route(route),
            'raw_route': route,
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
            'free_text': '',
            'flightplan': vars(fp)
        }
        route_key = f'{dep}_{dest}'
        if route_key not in prefroutes.keys():
            local_dep = re.sub(r'^K?', '', dep)
            local_dest = re.sub(r'^K?', '', dest)
            cdr = list(reader_client.flightdata.faa_cdr.find({'dep': dep, 'dest': dest}, {'_id': False}))
            pdr = list(reader_client.flightdata.faa_prd.find({'dep': local_dep, 'dest': local_dest}, {'_id': False}))
            for r in cdr:
                r['route'] = libs.lib.format_route(re.sub(rf'{dep}|{dest}', '', r['route']))
            for r in pdr:
                r['route'] = libs.lib.format_route(r['route'])
            prefroutes[route_key] = cdr + pdr
        adr = libs.adr_lib.get_eligible_adr(fp)
        for a in adr:
            adr['route'] = libs.lib.format_route(a['route'])
        adar = libs.adar_lib.get_eligible_adar(fp)
        for a in adar:
            adar['route'] = libs.lib.format_route(a['route'])
        entry['adr'] = adr
        entry['adar'] = adar
        entry['routes'] = prefroutes[route_key]
        entry['update_time'] = datetime.utcnow().strftime(time_mask)
        client.edst.data.update_one({'callsign': callsign}, {'$set': entry}, upsert=True)
    for callsign, entry in data.items():
        update_time = entry['update_time']
        if datetime.strptime(update_time, time_mask) + timedelta(hours=1) < datetime.utcnow():
            client.edst.data.delete_one({'callsign': callsign})
    client.close()


def get_edst_entry(callsign: str) -> Optional[dict]:
    client: MongoClient = mongo_client.get_edst_client()
    return client.edst.data.find_one({'callsign': callsign.upper()}, {'_id': False})


def update_edst_entry(callsign, data):
    client: MongoClient = g.mongo_edst_client
    client.edst.data.update_one({'callsign': callsign}, {'$set': data})
    return data


def get_route_data(expanded_route) -> list:
    client: MongoClient = mongo_client.get_reader_client()
    points = []
    for fix in expanded_route.split():
        if fix_data := client.navdata.waypoints.find_one({'waypoint_id': fix}, {'_id': False}):
            points.append({'fix': fix, 'pos': (float(fix_data['lat']), float(fix_data['lon']))})
    return points


def get_remaining_route_data(callsign: str) -> Optional[list]:
    client: MongoClient = mongo_client.get_reader_client()
    if entry := get_edst_entry(callsign):
        route_data = entry['route_data']
        if route_data:
            dest = entry['dest']
            if dest_data := client.navdata.airports.find_one({'icao': dest}, {'_id': False}):
                route_data[dest] = [float(dest_data['lat']), float(dest_data['lon'])]
            if (fp := libs.lib.get_flightplan(callsign)) is None:
                return None
            pos = (float(fp.lat), float(fp.lon))
            fixes_sorted = sorted(
                [{'fix': e['fix'], 'distance': geopy.distance.distance(e['pos'], pos).miles} for e in route_data],
                key=lambda x: x['distance'])
            fix_distances = {e['fix']: e['distance'] for e in fixes_sorted}
            fixes = [e['fix'] for e in fixes_sorted]
            next_fix = None
            if len(fixes) == 1:
                next_fix = fixes_sorted[0]
            else:
                next_fix = fixes_sorted[0] \
                    if fixes.index(fixes_sorted[0]['fix']) > fixes.index(fixes_sorted[1]['fix']) \
                    else fixes_sorted[1]
            if next_fix is None:
                return None
            for i, e in list(route_data):
                if e['fix'] == next_fix['fix']:
                    break
                else:
                    route_data.remove(e)
            return [{'fix': e['fix'], 'pos': e['pos'], 'distance': fix_distances[e['fix']]} for e in route_data]
    return None
