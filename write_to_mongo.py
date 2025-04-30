# THIS SCRIPT IS USED TO PARSE FAA DATA AND WRITE IT TO THE MONGO DATABASE - THIS IS NOT USED FOR THE API ITSELF

import csv
import glob
import json
import re
from collections import defaultdict
from pathlib import Path
from geopy.distance import distance
import xml.etree.ElementTree as ET

from pymongo import MongoClient
from config import *
# import mongo_users

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

def parse_adar_record(record, dp_data, star_data):
    def text_or_none(elem, tag):
        found = elem.find(tag)
        return found.text.strip() if found is not None else None

    def find_all_text(elem, tag):
        return [e.text.strip() for e in elem.findall(tag)]

    # Extract the fields and match to your schema
    doc = {
        'dep': find_all_text(record.find("ADARDepartureList") or [], "AirportID"),
        'dest': find_all_text(record.find("ADARArrivalList") or [], "AirportID"),
        'route': text_or_none(record.find("ADARAutoRouteAlphas"), "RouteString"),
        'dp': text_or_none(record.find("ADARAutoRouteAlphas"), "DP_ID"),
        'star': text_or_none(record.find("ADARAutoRouteAlphas"), "STAR_ID"),
        'airways': [fix.find("FixName").text.strip() for fix in record.findall("RouteFixList/RouteFix")],
        'min_alt': int(text_or_none(record, "LowerAltitude") or 0),
        'top_alt': int(text_or_none(record, "UpperAltitude") or 0),
        'ierr': [text_or_none(criteria, "IERRCriteriaID") for criteria in record.findall("ADARIERRCriteria")],
        'aircraft_class': [text_or_none(criteria, "AircraftClassCriteriaID") for criteria in record.findall("ADARACClassCriteriaList")],
        'route_fixes': [fix.find("FixName").text.strip() for fix in record.findall("RouteFixList/RouteFix")],
        'dep_content_criteria': text_or_none(record, "DepartureContentCriteria"),
        'dest_content_criteria': text_or_none(record, "DestinationContentCriteria"),
        'order': int(text_or_none(record, "Order") or 0),
        'route_groups': [],  # You can modify if you have additional information
        'artcc': 'ZDV'
    }
    return doc

def import_adar_xml(xml_path, dp_data, star_data, mongo_uri="mongodb://localhost:27017", db_name="flightdata", collection="adar"):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    records = []
    for record in root.findall("ADARRecord"):
        doc = parse_adar_record(record, dp_data, star_data)
        records.append(doc)

    client = get_fd_mongo_client()
    db = client.flightdata
    result = db[collection].insert_many(records)
    print(f"Inserted {len(result.inserted_ids)} ADAR records.")

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

def get_text(elem, default=None):
    return elem.text.strip() if elem is not None and elem.text else default

def parse_adr_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    records = []
    for record in root.findall('ADRRecord'):
        # Core fields
        adr_id = get_text(record.find('ADR_ID'))
        upper_alt = get_text(record.find('UpperAltitude'))
        lower_alt = get_text(record.find('LowerAltitude'))
        order = get_text(record.find('Order'))
        auto_route_limit = get_text(record.find('AutoRouteLimit'))

        # AutoRouteAlphas (Optional but common)
        alpha = record.find('ADRAutoRouteAlphas')
        route_string = get_text(alpha.find('RouteString')) if alpha is not None else None
        protected_area = get_text(alpha.find('ProtectedAreaOverwrite')) if alpha is not None else None
        dp_id = get_text(alpha.find('DP_ID')) if alpha is not None else None

        # Route Fixes
        route_fixes = []
        for rf in record.findall('RouteFixList/RouteFix'):
            fix = get_text(rf.find('FixName'))
            if fix:
                route_fixes.append(fix)

        # Transition Fix
        tf = record.find('ADRTransitionFix')
        transition_fix = {
            'FixName': get_text(tf.find('FixName')),
            'FixID': get_text(tf.find('FixID')),
            'ICAOCode': get_text(tf.find('ICAOCode')),
            'TFixType': get_text(tf.find('TFixType')),
            'TFixIndex': get_text(tf.find('TFixIndex'))
        } if tf is not None else None

        # Airport List
        airports = [get_text(ap) for ap in record.findall('ADRAirportList/AirportID') if get_text(ap)]

        # Aircraft Class Criteria
        ac_criteria = []
        for crit in record.findall('ADRACClassCriteriaList'):
            ac_criteria.append({
                'ID': get_text(crit.find('AircraftClassCriteriaID')),
                'Facility': get_text(crit.find('AircraftClassCriteriaFac')),
                'IsExcluded': get_text(crit.find('IsExcluded'))
            })

        # IERR Criteria
        ierr = record.find('ADRIERRCriteria')
        ierr_criteria = {
            'IERRCriteriaID': get_text(ierr.find('IERRCriteriaID')),
            'IERRFacility': get_text(ierr.find('IERRFacility')),
            'RoutePriority': get_text(ierr.find('RoutePriority'))
        } if ierr is not None else None

        # Departure Content Criteria (optional, single line or multiline)
        content_criteria_elem = record.find('DepartureContentCriteria/ContentCriteria')
        if content_criteria_elem is not None and content_criteria_elem.text:
            dep_content_criteria = [
                line.strip() for line in content_criteria_elem.text.strip().splitlines() if line.strip()
            ]
        else:
            dep_content_criteria = None

        # Crossing Lines (optional)
        crossing_lines = []
        for cl in record.findall('ADRCrossingLine'):
            cl_dict = {
                'CrossingLineID': get_text(cl.find('CrossingLineID')),
                'UpperAltitude': get_text(cl.find('UpperAltitude')),
                'LowerAltitude': get_text(cl.find('LowerAltitude')),
                'TransitionLineDistance': get_text(cl.find('TransitionLineDistance')),
                'ApplicabilityType': get_text(cl.find('CrossingLineApplicability/ApplicabilityType')),
                'PriorityInd': get_text(cl.find('CrossingLineApplicability/PriorityInd')),
                'TransFix': {
                    'FixName': get_text(cl.find('ADRCrossingLineTransFix/FixName')),
                    'FixID': get_text(cl.find('ADRCrossingLineTransFix/FixID')),
                    'ICAOCode': get_text(cl.find('ADRCrossingLineTransFix/ICAOCode')),
                },
                'Airports': [
                    get_text(aid) for aid in cl.findall('ADRLineAirportList/AirportID') if get_text(aid)
                ],
                'AircraftClassCriteria': [
                    {
                        'ID': get_text(ac.find('AircraftClassCriteriaID')),
                        'Facility': get_text(ac.find('AircraftClassCriteriaFac')),
                        'IsExcluded': get_text(ac.find('IsExcluded')),
                    }
                    for ac in cl.findall('ADRLineACCCriteriaList')
                ],
                'Coordinates': [
                    {
                        'Latitude': get_text(coord.find('Latitude')),
                        'Longitude': get_text(coord.find('Longitude')),
                        'XSpherical': get_text(coord.find('XSpherical')),
                        'YSpherical': get_text(coord.find('YSpherical')),
                        'ZSpherical': get_text(coord.find('ZSpherical')),
                    }
                    for coord in cl.findall('ADRLineCoordinates')
                ]
            }
            crossing_lines.append(cl_dict)

        # Optional comment
        comment = get_text(record.find('UserComment'))

        # Final structured object
        records.append({
            'adr_id': adr_id,
            'min_alt': lower_alt,
            'top_alt': upper_alt,
            'order': order,
            'route': route_string,
            'dp': dp_id,
            'airways': [],  # can be filled if present
            'route_fixes': route_fixes,
            'transition_fix': transition_fix,
            'airports': airports,
            'aircraft_class': ac_criteria,
            'ierr': ierr_criteria,
            'dep_content_criteria': dep_content_criteria,
            'crossing_lines': crossing_lines,
            'user_comment': comment
        })

    return records

def write_adr_xml_to_mongo(xml_file, mongo_uri="mongodb://localhost:27017", db_name="zdv"):
    records = parse_adr_xml(xml_file)

    client = get_fd_mongo_client()
    db = client.flightdata
    col = db['adr']
    col.drop()
    col.insert_many(records)
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
    path = f'fav/{artcc.lower()}/{artcc.upper()}_Sector_Profiles.json'
    if os.path.exists(path):
        with open(path, 'r') as f:
            col = client[artcc]['ctr_profiles']
            data = json.load(f)
            mongo_data = []
            for profile_id, profile_data in data.items():
                mongo_data.append({'id': profile_id, 'name': profile_data['name'], 'sectors': profile_data['sectors']})
            col.insert_many(mongo_data)


def write_gpd_data(artcc):
    client = get_admin_mongo_client()
    with open(f'gpd/{artcc.upper()}_gpd_config.json', 'r') as f:
        gpd_data = json.load(f)
        navaid_list = []
        navdata_prefs = gpd_data['navdata_prefs']
        basepoint = (float(navdata_prefs['artcc_base_lat']), float(navdata_prefs['artcc_base_lon']))
        rad = int(navdata_prefs['radius'])
        for navaid in client.navdata.navaids.find({}, {'_id': False, 'artcc_low': False, 'artcc_high': False, 'name': False}):
            navaid_pos = (float(navaid['lat']), float(navaid['lon']))
            if distance(basepoint, navaid_pos).nautical < rad:
                navaid_list.append(navaid)
        col = client[artcc]['gpd_navaids']
        col.drop()
        col.insert_many(navaid_list)
        airport_list = []
        for airport in client.navdata.navaids.find({}, {'_id': False, 'city': False, 'elevation': False, 'name': False, 'procedures': False, 'runways': False}):
            airport_pos = (float(airport['lat']), float(airport['lon']))
            if distance(basepoint, airport_pos).nautical < rad:
                airport_list.append(airport)
        airway_segment_list = []
        for awy_segment in client.navdata.airways.find({}, {'_id': False, 'artcc': False, 'min_crossing_alt': False, 'max_auth_alt': False, 'moa': False, 'mea': False}):
            if awy_segment['lat'] and awy_segment['lon']:
                segment_pos = (float(awy_segment['lat']), float(awy_segment['lon']))
                if distance(basepoint, segment_pos).nautical < rad:
                    airway_segment_list.append(awy_segment)
        col = client[artcc]['gpd_airways']
        col.drop()
        col.insert_many(airway_segment_list)
        col = client[artcc]['gpd_airports']
        col.drop()
        col.insert_many(airport_list)
        col = client[artcc]['gpd_sectors']
        col.drop()
        col.insert_many(gpd_data['sectors'])
        col = client[artcc]['gpd_waypoints']
        col.drop()
        col.insert_many(navdata_prefs['fixes'])

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
    with open(STARDP_FILENAME, 'r') as f:
        stardp_data = json.load(f)
    dp_data = {row['procedure'][:-1]: row for row in stardp_data if row['type'] == 'DP'}
    star_data = {row['procedure'][:-1]: row for row in stardp_data if row['type'] == 'STAR'}
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
    # write_fav()
    # write_artcc_fav('zbw')
    # write_artcc_fav('zlc')
    # write_gpd_data('zbw')
    # write_gpd_data('zlc')
    # write_artcc_profiles('zlc')
    # write_all_artcc_ref_fixes()
    # write_adr_xml_to_mongo('/home/jonah-lefkoff/Downloads/eram-adaptation/ADR.xml')
    import_adar_xml('/home/jonah-lefkoff/Downloads/eram-adaptation/ADAR.xml', dp_data, star_data)
    pass
