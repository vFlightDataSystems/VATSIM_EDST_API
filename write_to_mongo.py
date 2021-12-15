# THIS SCRIPT IS USED TO PARSE FAA DATA AND WRITE IT TO THE MONGO DATABASE - THIS IS NOT USED FOR THE API ITSELF

import csv
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

from pymongo import MongoClient
from config import *
import mongo_users

NATTYPE_FILENAME = 'adrdata/ACCriteriaTypes.csv'
STARDP_FILENAME = 'navdata_parser/out/stardp.json'
AIRWAYS_FILENAME = 'navdata_parser/out/airways.csv'
APT_FILENAME = 'navdata_parser/out/aptdata.csv'
WAYPOINTS_FILENAME = 'navdata_parser/out/navdata_combined.csv'
NAVAIDS_FILENAME = 'navdata_parser/out/navaid_data.csv'
FIXES_FILENAME = 'navdata_parser/out/fixdata.csv'
FAA_PRD_FILENAME = 'navdata_parser/out/faa_prd.csv'
FAA_CDR_FILENAME = 'navdata_parser/out/cdr.csv'
CIFP_DATA_FILENAME = 'navdata_parser/out/cifp_data.json'

fd_db_name = 'flightdata'
nav_db_name = 'navdata'

adr_dbname = fd_db_name
adar_dbname = fd_db_name
nat_dbname = fd_db_name


def get_fd_mongo_client() -> MongoClient:
    return MongoClient(MONGO_URL,
                       username=MONGO_FD_USER,
                       password=MONGO_FD_PASS,
                       authSource='flightdata')


def get_mongo_client(user, password, dbname) -> MongoClient:
    return MongoClient(MONGO_URL,
                       username=user,
                       password=password,
                       authSource=dbname)


def get_nav_mongo_client() -> MongoClient:
    return MongoClient(MONGO_URL,
                       username=MONGO_NAV_USER,
                       password=MONGO_NAV_PASS,
                       authSource='navdata')


def get_admin_mongo_client() -> MongoClient:
    return MongoClient(MONGO_URL,
                       username=os.getenv('MONGO_ADMIN_USER'),
                       password=os.getenv('MONGO_ADMIN_PASS')
                       )


def write_beacons(dbname):
    with open('resources/beacon_codes.csv', 'r') as f:
        reader = csv.DictReader(f)
        client: MongoClient = get_fd_mongo_client()
        db = client[dbname]
        col = db['beacons']
        col.insert_many(list(reader))
        client.close()


def write_nattypes(filename, dbname):
    rows = []
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            if entry['Criteria Type'] == 'Include':
                aircraft_type = entry['Aircraft Type']
                nat_type = entry['Aircraft Class Criteria ID']
                owner = entry['Owning Facility']
                rows.append({'aircraft_type': aircraft_type, 'nat': nat_type, 'owner': owner})
    client: MongoClient = get_fd_mongo_client()
    db = client[dbname]
    col = db['nat_types']
    col.insert_many(rows)
    client.close()


def write_adar(filename, dp_data, star_data):
    rows = []
    artcc = re.search(r'z\S{2}', filename)[0].lower()
    with open(filename, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            alphas = entry['Auto Route Alphas'].split('\n')
            row = {
                'dep': entry['Dep Airports'].split(),
                'dest': entry['Arr Airports'].split(),
                'route': '',
                'dp': '',
                'star': '',
                'airways': [],
                'min_alt': entry['Lower Altitude'],
                'top_alt': entry['Upper Altitude'],
                'ierr': entry['IERR Criteria'].split(),
                'aircraft_class': entry['AC Class Criteria'].split(),
                'order': entry['Order'],
                'route_groups': entry['Route Groups'],
                'artcc': artcc
            }
            for e in alphas:
                if e[:13] == '(RouteString)':
                    row['route'] = re.sub(r'\.+', ' ', e[13:]).strip()
                if e[:9] == '(Airways)':
                    row['airways'] = e[9:].strip().split()
                if e[:6] == '(DpId)':
                    row['dp'] = e[6:].strip()
                if e[:8] == '(StarId)':
                    row['star'] = e[8:].strip()

            star = row['star']
            if star:
                star_id = ''.join([s for s in star if not s.isdigit()])
                if star_id in star_data.keys():
                    if not star == star_data[star_id]['procedure']:
                        current_star = star_data[star_id]['procedure']
                        row['star'] = current_star
                        row['route'] = row['route'].replace(star, current_star)
                else:
                    pass
                    # print(f'{star} not in nasr!')
            dp = row['dp']
            if dp:
                dp_id = ''.join([s for s in dp if not s.isdigit()])
                if dp_id in dp_data.keys():
                    if not dp == dp_data[dp_id]['procedure']:
                        current_dp = dp_data[dp_id]['procedure']
                        row['dp'] = current_dp
                        row['route'] = row['route'].replace(dp, current_dp)
                else:
                    pass
                    # print(f'{dp} not in nasr!')
            rows.append(row)

    user = f'{artcc}_admin'
    password = mongo_users.users[user]
    client: MongoClient = get_mongo_client(user, password, artcc)
    db = client[artcc]
    col = db[f'adar']
    col.insert_many(rows)
    client.close()


def write_adr(filename, dp_data):
    rows = []
    artcc = re.search(r'z\S{2}', filename)[0].lower()
    with open(filename, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            tfixes = []
            for tfix in entry['Transition Fixes Detail'].split():
                info = re.search(r'\((.*)\)', tfix).group(0)
                tfixes.append({
                    'tfix': tfix.replace(info, ''),
                    'info': info[1:-1]
                })
            alphas = entry['Auto Route Alphas'].split('\n')
            row = {
                'dep': entry['Airports'].split(),
                'route': '',
                'dp': '',
                'airways': '',
                'route_groups': entry['Route Groups'],
                'min_alt': entry['Lower Altitude'],
                'top_alt': entry['Upper Altitude'],
                'ierr': entry['IERR Criteria'].split(),
                'aircraft_class': entry['AC Class Criteria'].split(),
                'tfixes': tfixes,
                'order': entry['Order'],
                'xlines': entry['XLines']
            }
            for e in alphas:
                if e[:13] == '(RouteString)':
                    row['route'] = re.sub(r'\.+', ' ', e[13:]).strip()
                if e[:9] == '(Airways)':
                    row['airways'] = e[9:].strip()
                if e[:6] == '(DpId)':
                    row['dp'] = e[6:].strip()

            dp = row['dp']
            if dp:
                dp_id = ''.join([s for s in dp if not s.isdigit()])
                if dp_id in dp_data.keys():
                    if not dp == dp_data[dp_id]['procedure']:
                        current_dp = dp_data[dp_id]['procedure']
                        row['dp'] = current_dp
                        row['route'] = row['route'].replace(dp, current_dp)
                else:
                    pass
                    # print(f'{dp} not in nasr!')
            if row['route']:
                rows.append(row)

    user = f'{artcc}_admin'
    password = mongo_users.users[user]
    client: MongoClient = get_mongo_client(user, password, artcc)
    db = client[artcc]
    col = db[f'adr']
    col.insert_many(rows)
    client.close()


def write_faa_data(dbname):
    with open(FAA_PRD_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        client: MongoClient = get_fd_mongo_client()
        db = client[dbname]
        col = db['faa_prd']
        col.insert_many(rows)
        client.close()

    with open(FAA_CDR_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        client: MongoClient = get_fd_mongo_client()
        db = client[dbname]
        col = db['faa_cdr']
        col.insert_many(rows)
        client.close()


def write_navdata(dbname):
    with open(CIFP_DATA_FILENAME, 'r') as f:
        cifp_data = json.load(f)

    with open(STARDP_FILENAME, 'r') as f:
        rows = json.load(f)
        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['procedures']
        col.insert_many(rows)
        client.close()

    with open(WAYPOINTS_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['waypoints']
        col.insert_many(rows)
        client.close()

    with open(AIRWAYS_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['airways']
        col.insert_many(rows)
        client.close()

    rows = []
    with open(APT_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['runways'] = []
            row_procedures = defaultdict(list)
            try:
                code = row['icao'] or row['code']
                for rwy, procedures in cifp_data[code].items():
                    row['runways'].append(rwy)
                    for procedure in procedures:
                        row_procedures[procedure].append(rwy)
            except Exception as e:
                pass  # print(row, e)
            row['procedures'] = [{'procedure': key, 'runways': val} for key, val in row_procedures.items()]
            rows.append(row)

    client: MongoClient = get_nav_mongo_client()
    db = client[dbname]
    col = db['airports']
    col.insert_many(rows)
    client.close()

    with open(NAVAIDS_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['navaids']
        col.insert_many(rows)
        client.close()

    with open(FIXES_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['fixes']
        col.insert_many(rows)
        client.close()


def add_mongo_users():
    client = get_admin_mongo_client()
    for user, password in mongo_users.users.items():
        artcc = user[0:3].lower()
        client[artcc].command(
            'createUser', user,
            pwd=password,
            roles=[{'role': 'readWrite', 'db': artcc}]
        )


if __name__ == '__main__':
    # write_navdata(nav_db_name)
    # write_nattypes(NATTYPE_FILENAME, fd_db_name)
    # with open(STARDP_FILENAME, 'r') as f:
    #     stardp_data = json.load(f)
    # dp_data = {row['procedure']: row for row in stardp_data if row['type'] == 'DP'}
    # star_data = {row['procedure']: row for row in stardp_data if row['type'] == 'STAR'}
    # for filepath in glob.iglob('adrdata/AdaptedRoutes/*'):
    #     path = Path(filepath)
    #     if path.stem[:3] == 'adr':
    #         write_adr(filepath, dp_data)
    #     if path.stem[:4] == 'adar':
    #         write_adar(filepath, dp_data, star_data)
    write_faa_data(fd_db_name)
    # write_beacons(fd_db_name)
    # add_mongo_users()
