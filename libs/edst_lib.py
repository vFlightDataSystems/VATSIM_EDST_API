import itertools
import re
import string
import random
from collections import defaultdict

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


def update_edst_data():
    client: MongoClient = mongo_client.get_edst_client()
    reader_client: MongoClient = mongo_client.get_reader_client()
    data = {d['callsign']: d for d in client.edst.data.find()}
    used_cid_list = [d['cid'] for d in data.values()]
    prefroutes = defaultdict(None)
    for callsign, fp in libs.lib.get_all_flightplans().items():
        dep = fp.departure
        dest = fp.arrival
        if callsign in data.keys():
            entry = data[callsign]
            update_time = entry['update_time']
            if datetime.strptime(update_time, time_mask) < datetime.utcnow() + timedelta(minutes=5) \
                    and entry['dep'] == dep and entry['dest'] == dest:
                entry['flightplan'] = vars(fp)
                entry['update_time'] = datetime.utcnow().strftime(time_mask)
                client.edst.data.update_one({'callsign': callsign}, {'$set': entry})
                continue
        if not reader_client.navdata.airports.find_one({'icao': dep.upper()}, {'_id': False}):
            continue
        cid = get_cid(used_cid_list)
        used_cid_list.append(cid)
        route = libs.lib.format_route(fp.route)
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
            'route': route,
            'expanded_route': expanded_route,
            'altitude': str(int(fp.altitude)).zfill(3),
            'interim': None,
            'hdg': None,
            'spd': None,
            'hold_hdg': None,
            'hold_spd': None,
            'lat': fp.lat,
            'lon': fp.lon,
            'remarks': fp.remarks,
            'cid': cid,
            'flightplan': vars(fp)
        }
        route_key = f'{dep}_{dest}'
        if route_key not in prefroutes.keys():
            local_dep = re.sub(r'^K?', '', dep)
            local_dest = re.sub(r'^K?', '', dest)
            prefroutes[route_key] = \
                list(reader_client.flightdata.faa_cdr.find({'dep': dep, 'dest': dest}, {'_id': False})) + \
                list(reader_client.flightdata.faa_prd.find({'dep': local_dep, 'dest': local_dest}, {'_id': False}))
        # entry['adr'] = libs.adr_lib.get_eligible_adr(fp)
        # entry['adar'] = libs.adar_lib.get_eligible_adar(fp)
        entry['routes'] = prefroutes[route_key]
        entry['update_time'] = datetime.utcnow().strftime(time_mask)
        client.edst.data.update_one({'callsign': callsign}, {'$set': entry}, upsert=True)
    for callsign, entry in data.items():
        update_time = entry['update_time']
        if datetime.strptime(update_time, time_mask) + timedelta(hours=1) < datetime.utcnow():
            client.edst.data.delete_one({'callsign': callsign})
    client.close()


def get_edst_entry(callsign: str):
    client: MongoClient = g.mongo_edst_client
    return client.edst.data.find_one({'callsign': callsign}, {'_id': False})


def update_edst_entry(callsign, data):
    client: MongoClient = g.mongo_edst_client
    client.edst.data.update_one({'callsign': callsign}, {'$set': data})
    return data
