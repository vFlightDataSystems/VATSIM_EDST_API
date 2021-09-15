# THIS SCRIPT IS USED TO PARSE FAA DATA AND WRITE IT TO THE MONGO DATABASE - THIS IS NOT USED FOR THE API ITSELF

import csv
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

from pymongo import MongoClient
from config import *

NATTYPE_FILENAME = 'adrdata/ACCriteriaTypes.csv'
STARDP_FILENAME = 'navdata_parser/out/stardp.csv'
AIRWAYS_FILENAME = 'navdata_parser/out/airways.csv'
APT_FILENAME = 'navdata_parser/out/aptdata.csv'
WAYPOINTS_FILENAME = 'navdata_parser/out/navdata_combined.csv'
NAVAIDS_FILENAME = 'navdata_parser/out/navaid_data.csv'
FIXES_FILENAME = 'navdata_parser/out/fixdata.csv'
FAA_PRD_FILENAME = 'navdata_parser/out/faa_prd.csv'
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


def get_nav_mongo_client() -> MongoClient:
    return MongoClient(MONGO_URL,
                       username=MONGO_NAV_USER,
                       password=MONGO_NAV_PASS,
                       authSource='navdata')


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
    print(db)
    col = db['nat_types']
    col.insert_many(rows)
    client.close()


def write_adar(filename, dbname, dp_data, star_data):
    rows = []
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
                'route_groups': entry['Route Groups']
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
                        print(star)
                        current_star = star_data[star_id]['procedure']
                        row['star'] = current_star
                        row['route'] = row['route'].replace(star, current_star)
                else:
                    print(f'{star} not in nasr!')
            dp = row['dp']
            if dp:
                dp_id = ''.join([s for s in dp if not s.isdigit()])
                if dp_id in dp_data.keys():
                    if not dp == dp_data[dp_id]['procedure']:
                        print(dp)
                        current_dp = dp_data[dp_id]['procedure']
                        row['dp'] = current_dp
                        row['route'] = row['route'].replace(dp, current_dp)
                else:
                    print(f'{dp} not in nasr!')
            row['route'] = row['route'].split()
            rows.append(row)
    client: MongoClient = get_fd_mongo_client()
    db = client[dbname]
    col = db['adar']
    col.insert_many(rows)
    client.close()


def parse_adr(filename, dbname, dp_data):
    rows = []
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
                'xlines': entry['XLines'],
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
                        print(dp)
                        current_dp = dp_data[dp_id]['procedure']
                        row['dp'] = current_dp
                        row['route'] = row['route'].replace(dp, current_dp)
                else:
                    print(f'{dp} not in nasr!')
            if row['route']:
                row['route'] = row['route'].split()
                rows.append(row)
    client: MongoClient = get_fd_mongo_client()
    db = client[dbname]
    col = db['adr']
    col.insert_many(rows)
    client.close()


def write_faa_prd(filename, dbname):
    rows = []
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            del row['id']
            row['route'] = row['route'].split()
            row['airways'] = row['airways'].split()
            rows.append(row)
    client: MongoClient = get_fd_mongo_client()
    db = client[dbname]
    col = db['faa_prd']
    col.insert_many(rows)
    client.close()


def write_navdata(dbname, stardp_filename, navdata_filename, airways_filename, apt_filename, navaids_filename,
                  fixes_filename, cifp_data_filename):
    with open(cifp_data_filename, 'r') as f:
        cifp_data = json.load(f)

    rows = []
    with open(stardp_filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['airports'] = defaultdict(list)
            procedure = row['procedure']
            for apt, v in cifp_data.items():
                for rwy, rwy_procs in v.items():
                    if procedure in rwy_procs:
                        row['airports'][apt].append(rwy)
            del row['id']
            del row['proc_id']
            rows.append(row)

    client: MongoClient = get_nav_mongo_client()
    db = client[dbname]
    col = db['procedures']
    col.insert_many(rows)
    client.close()

    rows = []
    with open(navdata_filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            del row['id']
            rows.append(row)

    client: MongoClient = get_nav_mongo_client()
    db = client[dbname]
    col = db['waypoints']
    col.insert_many(rows)
    client.close()

    rows = []
    with open(airways_filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            del row['id']
            rows.append(row)

    client: MongoClient = get_nav_mongo_client()
    db = client[dbname]
    col = db['airways']
    col.insert_many(rows)
    client.close()

    rows = []
    with open(apt_filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['runways'] = []
            row['procedures'] = defaultdict(list)
            try:
                code = row['icao'] or row['code']
                for rwy, procedures in cifp_data[code].items():
                    row['runways'].append(rwy)
                    for procedure in procedures:
                        row['procedures'][procedure].append(rwy)
            except Exception as e:
                print(row, e)
            del row['id']
            rows.append(row)

    client: MongoClient = get_nav_mongo_client()
    db = client[dbname]
    col = db['airports']
    col.insert_many(rows)
    client.close()

    rows = []
    with open(navaids_filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            del row['id']
            rows.append(row)

    client: MongoClient = get_nav_mongo_client()
    db = client[dbname]
    col = db['navaids']
    col.insert_many(rows)
    client.close()

    rows = []
    with open(fixes_filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            del row['id']
            rows.append(row)

    client: MongoClient = get_nav_mongo_client()
    db = client[dbname]
    col = db['fixes']
    col.insert_many(rows)
    client.close()


if __name__ == '__main__':
    write_navdata(nav_db_name, STARDP_FILENAME, WAYPOINTS_FILENAME, AIRWAYS_FILENAME, APT_FILENAME, NAVAIDS_FILENAME,
                  FIXES_FILENAME, CIFP_DATA_FILENAME)
    write_nattypes(NATTYPE_FILENAME, fd_db_name)
    # with open(STARDP_FILENAME, 'r') as f:
    #     reader = csv.DictReader(f)
    #     stardp_data = {e['proc_id']: e for e in reader}
    # dp_data = {k: v for k, v in stardp_data.items() if v['type'] == 'DP'}
    # star_data = {k: v for k, v in stardp_data.items() if v['type'] == 'STAR'}
    # for filepath in glob.iglob('adrdata/AdaptedRoutes/*'):
    #     path = Path(filepath)
    #     if path.stem[:3] == 'adr':
    #         parse_adr(filepath, fd_db_name, dp_data)
    #     if path.stem[:4] == 'adar':
    #         write_adar(filepath, fd_db_name, dp_data, star_data)
    # write_faa_prd(FAA_PRD_FILENAME, fd_db_name)
