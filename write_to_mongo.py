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
ATS_FILENAME = 'navdata_parser/out/ats.csv'
APT_FILENAME = 'navdata_parser/out/aptdata.csv'
WAYPOINTS_FILENAME = 'navdata_parser/out/navdata_combined.csv'
NAVAIDS_FILENAME = 'navdata_parser/out/navaid_data.csv'
FIXES_FILENAME = 'navdata_parser/out/fixdata.csv'
FAA_PRD_FILENAME = 'navdata_parser/out/faa_prd.csv'
FAA_CDR_FILENAME = 'navdata_parser/out/cdr.csv'
CIFP_DATA_FILENAME = 'navdata_parser/out/cifp_data.json'
AAR_FILENAME = 'adrdata/2112_AAR.csv'

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
        col.drop()
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
    col.drop()
    col.insert_many(rows)
    client.close()


def write_adar(filename, dp_data, star_data):
    rows = []
    artcc = re.search(r'z\S{2}', filename)[0].lower()
    with open(filename, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            alphas = entry['Auto Route Alphas'].split('\n')
            dep_content_criteria = entry['Departure Content Criteria'].split('\r\n')
            dest_content_criteria = entry['Destination Content Criteria'].split('\r\n')
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
                'route_fixes': entry['Route Fixes'],
                'dep_content_criteria': dep_content_criteria if any(dep_content_criteria) else None,
                'dest_content_criteria': dest_content_criteria if any(dest_content_criteria) else None,
                'order': entry['Order'],
                'route_groups': entry['Route Groups'].split(),
                'artcc': artcc
            }
            for a in alphas:
                if a[:13] == '(RouteString)':
                    row['route'] = a[13:].strip()
                if a[:9] == '(Airways)':
                    row['airways'] = a[9:].strip().split()
                if a[:6] == '(DpId)':
                    row['dp'] = a[6:].strip()
                if a[:8] == '(StarId)':
                    row['star'] = a[8:].strip()

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
                    print(f'{star} not in nasr!')
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
                    print(f'{dp} not in nasr!')
            rows.append(row)

    user = f'{artcc}_admin'
    password = mongo_users.users[user]
    client: MongoClient = get_mongo_client(user, password, artcc)
    db = client[artcc]
    col = db[f'adar']
    col.drop()
    col.insert_many(rows)
    client.close()


def write_adr(filename, dp_data):
    rows = []
    artcc = re.search(r'z\S{2}', filename)[0].lower()
    with open(filename, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            tfixes_details = []
            for tfix in entry['Transition Fixes Detail'].split():
                info = re.search(r'\((.*)\)', tfix).group(0)
                tfixes_details.append({
                    'tfix': tfix.replace(info, ''),
                    'info': info[1:-1]
                })
            alphas = entry['Auto Route Alphas'].split('\n')
            dep_content_criteria = entry['Departure Content Criteria'].split('\r\n')
            row = {
                'dep': entry['Airports'].split(),
                'route': '',
                'dp': '',
                'airways': [],
                'route_groups': entry['Route Groups'].split(),
                'min_alt': entry['Lower Altitude'],
                'top_alt': entry['Upper Altitude'],
                'ierr': entry['IERR Criteria'].split(),
                'aircraft_class': entry['AC Class Criteria'].split(),
                'transition_fixes': entry['Transition Fixes'].split(),
                'transition_fixes_details': tfixes_details,
                'route_fixes': entry['Route Fixes'].split(),
                'dep_content_criteria': dep_content_criteria if any(dep_content_criteria) else None,
                'order': entry['Order'],
                'xlines': entry['XLines']
            }
            for a in alphas:
                if a[:13] == '(RouteString)':
                    row['route'] = a[13:].strip()
                if a[:9] == '(Airways)':
                    row['airways'] = a[9:].strip().split()
                if a[:6] == '(DpId)':
                    row['dp'] = a[6:].strip()

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
    col.drop()
    col.insert_many(rows)
    client.close()


def write_aar(filename):
    rows = []
    with open(filename, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            tfixes_details = []
            for tfix in entry['Transition Fixes Detail'].split():
                info = re.search(r'\((.*)\)', tfix).group(0)
                tfixes_details.append({
                    'tfix': tfix.replace(info, ''),
                    'info': info[1:-1]
                })
            alphas = entry['Auto Route Alphas'].split('\n')
            dest_content_criteria = entry['Destination Content Criteria'].split('\r\n')
            row = {
                'owning_facility': entry['Owning Facility'],
                'applicable_artcc': entry['Applicable ARTCCs'].split(),
                'airports': entry['Airports'].split(),
                'route': '',
                'star': '',
                'airways': [],
                'route_groups': entry['Route Groups'].split(),
                'min_alt': entry['Lower Altitude'],
                'top_alt': entry['Upper Altitude'],
                'ierr': entry['IERR Criteria'].split(),
                'aircraft_class': entry['AC Class Criteria'].split(),
                'transition_fixes': entry['Transition Fixes'].split(),
                'transition_fixes_details': tfixes_details,
                'route_fixes': entry['Route Fixes'].split(),
                'dest_content_criteria': dest_content_criteria if any(dest_content_criteria) else None,
                'order': entry['Order'],
                'xlines': entry['XLines']
            }
            for a in alphas:
                if a[:13] == '(RouteString)':
                    row['route'] = a[13:].strip()
                if a[:9] == '(Airways)':
                    row['airways'] = a[9:].strip().split()
                if a[:6] == '(StarId)':
                    row['star'] = a[6:].strip()
            if row['route']:
                rows.append(row)

    client: MongoClient = get_fd_mongo_client()
    db = client.flightdata
    col = db[f'aar']
    col.drop()
    col.insert_many(rows)
    client.close()


def write_faa_data(dbname):
    with open(FAA_PRD_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            row['airways'] = row['airways'].split()
            rows.append(row)
        client: MongoClient = get_fd_mongo_client()
        db = client[dbname]
        col = db['faa_prd']
        col.drop()
        col.insert_many(rows)
        client.close()

    with open(FAA_CDR_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        client: MongoClient = get_fd_mongo_client()
        db = client[dbname]
        col = db['faa_cdr']
        col.drop()
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
        col.drop()
        col.insert_many(rows)
        client.close()

    with open(WAYPOINTS_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['waypoints']
        col.drop()
        col.insert_many(rows)
        client.close()

    with open(AIRWAYS_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['airways']
        col.drop()
        col.insert_many(rows)
        client.close()

    with open(ATS_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['oceanic_airways']
        col.drop()
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
    col.drop()
    col.insert_many(rows)
    client.close()

    with open(NAVAIDS_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['navaids']
        col.drop()
        col.insert_many(rows)
        client.close()

    with open(FIXES_FILENAME, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        client: MongoClient = get_nav_mongo_client()
        db = client[dbname]
        col = db['fixes']
        col.drop()
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


def write_fav():
    client = get_admin_mongo_client()
    with open('fav/Boundaries.json', 'r') as f:
        fav = [e for e in json.load(f)['features'] if re.match(r'K\S{3}', e['properties']['id'])]
        for e in fav:
            artcc = e['properties']['id'][1:].lower()
            if e['geometry']['type'] == 'MultiPolygon' and len(e['geometry']['coordinates']) == 1:
                e['geometry']['type'] = 'Polygon'
                e['geometry']['coordinates'] = e['geometry']['coordinates'][0]
            del e['properties']['label_lat']
            del e['properties']['label_lon']
            del e['type']
            col = client[artcc]['ctr_fav']
            col.drop()
            col.insert_one(e)
    client.close()


def write_artcc_fav(artcc):
    client = get_admin_mongo_client()
    ctr_fav_path = f'fav/{artcc.lower()}/{artcc.upper()}_CTR_FAV_Data.geojson'
    app_fav_path = f'fav/{artcc.lower()}/{artcc.upper()}_APP_FAV_Data.geojson'
    if os.path.exists(ctr_fav_path):
        with open(ctr_fav_path, 'r') as f:
            col = client[artcc]['ctr_fav']
            col.insert_many(json.load(f)['features'])
    if os.path.exists(app_fav_path):
        with open(app_fav_path, 'r') as f:
            col = client[artcc]['app_fav']
            col.drop()
            col.insert_many(json.load(f)['features'])
    client.close()


def write_artcc_profiles(artcc):
    client = get_admin_mongo_client()
    path = f'fav/{artcc.lower}/{artcc.upper()}_Sector_Profiles.geojson'
    if os.path.exists(path):
        with open(path, 'r') as f:
            col = client[artcc]['ctr_profiles']
            col.insert_many(json.load(f))


def write_gpd_data(artcc):
    client = get_admin_mongo_client()
    with open(f'gpd/{artcc.upper()}_gpd_config.json', 'r') as f:
        gpd_data = json.load(f)
        for key, val in gpd_data.items():
            col = client[artcc][f'gpd_{key}']
            col.drop()
            col.insert_many(val)

    client.close()


def write_all_artcc_ref_fixes():
    client = get_admin_mongo_client()
    with open('All_ARTCC_Ref_Fixes.json', 'r') as f:
        ref_fix_data = json.load(f)
        for artcc, fixes in ref_fix_data.items():
            col = client[artcc.lower()]['reference_fixes']
            col.drop()
            col.insert_many(fixes)
    client.close()


if __name__ == '__main__':
    # write_navdata(nav_db_name)
    # write_nattypes(NATTYPE_FILENAME, fd_db_name)
    # with open(STARDP_FILENAME, 'r') as f:
    #     stardp_data = json.load(f)
    # dp_data = {row['procedure'][:-1]: row for row in stardp_data if row['type'] == 'DP'}
    # star_data = {row['procedure'][:-1]: row for row in stardp_data if row['type'] == 'STAR'}
    # for filepath in glob.iglob('adrdata/AdaptedRoutes/*'):
    #     path = Path(filepath)
    #     if path.stem[:3] == 'adr':
    #         write_adr(filepath, dp_data)
    #     if path.stem[:4] == 'adar':
    #         write_adar(filepath, dp_data, star_data)
    # write_aar(AAR_FILENAME)
    # write_faa_data(fd_db_name)
    # write_beacons(fd_db_name)
    # add_mongo_users()
    write_fav()
    write_artcc_fav('zbw')
    write_artcc_fav('zlc')
    write_gpd_data('zbw')
    write_artcc_profiles('zlc')
    # write_all_artcc_ref_fixes()
    pass
