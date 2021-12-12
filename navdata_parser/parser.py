import csv
import re
import json
import uuid
from collections import defaultdict

from dms2dec.dms_convert import dms2dec

NASR_DIR = 'NASR'
CIFP_FILENAME = 'CIFP/FAACIFP18'

NAVDATA_FILENAME = NASR_DIR + '/NAV.txt'
FIXDATA_FILENAME = NASR_DIR + '/FIX.txt'
APTDATA_FILENAME = NASR_DIR + '/APT.txt'
PREFROUTES_FILENAME = NASR_DIR + '/PFR.txt'
STARDP_FILENAME = NASR_DIR + '/STARDP.txt'
AWY_FILENAME = NASR_DIR + '/AWY.txt'
AIRCRAFT_FILENAME = 'zla_data/aircraft.json'

cifp_rwy_regex = re.compile(r'^SUSAP (\w{3,4})\s?K\d\wRW(\d{1,2}[LCR]?)')
cifp_procedure_rwy_regex = re.compile(r'^SUSAP (\w{3,4})\s?K\d\w(\w{3,5}\d)\s{0,2}\S(?:RW)?(\d{2}[LCRB]?|ALL\s)')

type_altitudes = {
    'L': [0, 18000],
    'H': [18000, 99000],
    'LSD': [0, 18000],
    'HSD': [18000, 99000],
    'SLD': [0, 18000],
    'SHD': [18000, 99000],
    'TEC': [0, 18000],
    'NAR': [0, 99000]
}

with open('faa_ac.json', 'r') as f:
    faa_aircraft_description = json.load(f)
with open('faa_alt.json', 'r') as f:
    faa_altitude_description = json.load(f)


def parse_acdata():
    rows = []
    with open(AIRCRAFT_FILENAME, 'r') as f:
        data = json.load(f)
        for e in data['types']:
            e['id'] = uuid.uuid4()
            rows.append(e)
    return rows


def write_acdata(rows):
    with open('out/aircraft.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'code', 'manufacturer', 'model', 'aircraft_class', 'faa_class',
                                               'tec_class'])
        writer.writeheader()
        writer.writerows(rows)


def parse_navaid_data():
    rows = []
    with open(NAVDATA_FILENAME, 'r') as f:
        for line in f.readlines():
            if line[:4] == 'NAV1':
                lat = dms2dec(line[371:385].strip())
                lon = dms2dec(line[396:410].strip())
                nav_type = line[8:28].strip()
                nav_id = line[4:8].strip()
                name = line[42:72].strip()
                if nav_type != 'VOT':
                    nid = uuid.uuid4()
                    rows.append(
                        {'id': nid, 'navaid_id': nav_id, 'type': nav_type, 'name': name, 'lat': lat, 'lon': lon})
    return rows


def write_navaid_data(rows):
    with open('out/navaid_data.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'navaid_id', 'type', 'name', 'lat', 'lon'])
        writer.writeheader()
        writer.writerows(rows)


def parse_fixdata():
    rows = []
    with open(FIXDATA_FILENAME, 'r') as f:
        for line in f.readlines():
            if line[:4] == 'FIX1':
                lat = dms2dec(line[66:80].strip())
                lon = dms2dec(line[80:94].strip())
                fix_id = line[4:34].strip()
                name = fix_id
                fid = uuid.uuid4()
                rows.append({'id': fid, 'fix_id': fix_id, 'name': name, 'lat': lat, 'lon': lon})
    return rows


def write_fixdata(rows):
    with open('out/fixdata.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'fix_id', 'name', 'lat', 'lon'])
        writer.writeheader()
        writer.writerows(rows)


def write_navdata_combined(navaid_rows, fix_rows):
    for row in fix_rows:
        row['type'] = 'FIX'
        row['waypoint_id'] = row['fix_id']
        del row['fix_id']
    for row in navaid_rows:
        row['waypoint_id'] = row['navaid_id']
        del row['navaid_id']
    with open('out/navdata_combined.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'waypoint_id', 'type', 'name', 'lat', 'lon'])
        writer.writeheader()
        writer.writerows(navaid_rows + fix_rows)


def write_cifp_data():
    cifp_data = defaultdict(defaultdict)
    with open(CIFP_FILENAME, 'r') as cifp_file:
        lines = cifp_file.readlines()
        for line in lines:
            for match in cifp_rwy_regex.finditer(line):
                apt = match.group(1)
                rwy = match.group(2)
                cifp_data[apt][rwy] = []
        for line in lines:
            for match in cifp_procedure_rwy_regex.finditer(line):
                apt = match.group(1)
                procedure = match.group(2)
                runway = match.group(3).strip()
                try:
                    if runway == 'ALL':
                        for v in cifp_data[apt].values():
                            if procedure not in v:
                                v.append(procedure)
                    elif runway[-1] == 'B':
                        for k, v in cifp_data[apt].items():
                            if k[:-1] == runway[:-1] and procedure not in v:
                                v.append(procedure)
                    elif procedure not in cifp_data[apt][runway]:
                        cifp_data[apt][runway].append(procedure)
                except KeyError as e:
                    print(apt, procedure)
                    pass

    with open('out/cifp_data.json', 'w') as f:
        f.write(json.dumps(cifp_data))


def parse_aptdata():
    rows = []
    with open(APTDATA_FILENAME, 'r') as nasr_apt_file:
        for line in nasr_apt_file.readlines():
            if line[0:3] == 'APT':
                loc_id = line[27:31].strip()
                icao = line[1210:1217].strip()
                city = line[93:133].strip()
                name = line[133:183].strip()
                elev = line[578:585].strip()
                lat = dms2dec(line[523:538])
                lon = dms2dec(line[550:565])
                artcc = line[674:678].strip()
                rows.append({
                    'id': uuid.uuid4(),
                    'code': loc_id,
                    'icao': icao,
                    'city': city,
                    'name': name,
                    'artcc': artcc,
                    'elevation': elev,
                    'lat': lat,
                    'lon': lon
                })
    return rows


def write_aptdata(rows):
    with open('out/aptdata.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f,
                                fieldnames=['id', 'code', 'icao', 'city', 'name', 'artcc', 'elevation', 'lat', 'lon'])
        writer.writeheader()
        writer.writerows(rows)


def parse_stardp():
    rows = []
    with open(STARDP_FILENAME, 'r') as stardp_f, \
            open(CIFP_FILENAME, 'r') as cifp_f:
        cifp_lines = cifp_f.readlines()
        entry = {}
        route = []
        procedure = ''
        transition = ''
        transition_name = ''
        pid = None
        airport = ''
        for line in stardp_f.readlines():
            npid = line[:5]
            fix_type = line[10:12].strip()
            e = line[38:51].strip().split('.')
            fix = line[30:35].strip()
            if len(e) > 1 and route:
                transition_lines = [l for l in cifp_lines if l[13:19].strip() == procedure and (
                        (fix_type == 'AA' and fix in line[6:10]) or True)]
                _transitions = set((l[6:10], transition) for l in transition_lines if l[20:25] == transition)
                entry['routes'].append({'transition': t, 'name': transition_name, 'route': route, 'airports': [t[0] for t in _transitions]})
                route = [fix]
            elif fix_type == 'AA' and route:
                _transitions = []
                transition_lines = [l for l in cifp_lines if l[13:19].strip() == procedure and (
                        (fix_type == 'AA' and fix in line[6:10]) or True)]
                rw_lines = [l for l in transition_lines if
                            ((l[29:34].strip() == route[0] and npid[0] == 'D')
                             or (l[29:34].strip() == route[-1] and npid[0] == 'S'))
                            and re.match(r'RW\d+[CLRB]?|ALL', l[20:25])]
                for rw_line in rw_lines:
                    airport = rw_line[6:10].strip()
                    if match := re.search(r'RW\d+[CLRB]?|ALL', rw_line[20:25]):
                        t = match.group(0).strip()
                        if re.match(r'RW\d+B', t):
                            _transitions += [(airport, t.replace('B', c)) for c in 'LR']
                        else:
                            _transitions.append((airport, t))
                if not _transitions:
                    _transitions = set((l[6:10], transition) for l in transition_lines if l[20:25] == transition)
                entry['routes'].append({'transition': t, 'name': transition_name, 'route': route, 'airports': [t[0] for t in _transitions]})
                route = []
            else:
                route.append(fix)

            if npid != pid:
                if entry:
                    rows.append(entry)
                entry = {'type': 'DP' if npid[0] == 'D' else 'STAR',
                         'routes': [],
                         'transitions': []
                         }
            if len(e) > 1:
                procedure = e[0].strip() if npid[0] == 'D' else e[1].strip()
                entry['procedure'] = procedure
                transition = e[1].strip() if npid[0] == 'D' else e[0].strip()
                if transition not in entry['transitions']:
                    entry['transitions'].append(transition)
                transition_name = line[51:161].strip()
            pid = npid

    return rows


def write_stardp(rows):
    with open('out/stardp.json', 'w', newline='', encoding='utf8') as f:
        f.write(json.dumps(rows))


def get_route_info(aircraft, alt, route_type):
    try:
        aircraft = faa_aircraft_description[aircraft]
    except KeyError:
        aircraft = {}
    try:
        alt = faa_altitude_description[alt]
    except KeyError:
        alt = {}
    min_alt, top_alt = type_altitudes[route_type]
    rnav = ''
    if 'RNAV' in aircraft.keys():
        rnav = "required" if aircraft['RNAV'] else "no"
    if 'min' in alt.keys():
        min_alt = alt['min']
    if 'max' in alt.keys():
        top_alt = alt['max']
    if 'fix' in alt.keys():
        if str(alt['fix']).isnumeric():
            min_alt = alt['fix']
            top_alt = alt['fix']
        else:
            fix = alt['fix'].split()
    return min_alt, top_alt, rnav


def parse_prefroutes():
    procedures = {p['proc_id']: p for p in parse_stardp()}
    prefroute_rows = []
    with open(PREFROUTES_FILENAME, 'r') as f:
        entry = {}
        row = {}
        route = []
        airways = []
        for line in f.readlines():
            dep = line[4:9].strip()
            dest = line[9:14].strip()
            route_type = line[14:17].strip()
            if line[0:4] == 'PFR1':
                if entry:
                    row['route'] = ' '.join(route).strip()
                    row['airways'] = ' '.join(airways).strip()
                    prefroute_rows.append(row)
                eid = uuid.uuid4()
                route_id = uuid.uuid4()
                route = []
                airways = []
                alt = line[124:164].strip()
                aircraft = line[164:214].strip()
                min_alt, top_alt, rnav = get_route_info(aircraft, alt, route_type)
                row = {
                    'id': route_id,
                    'dep': dep,
                    'dest': dest,
                    'type': route_type,
                    'lowest_alt': min_alt,
                    'top_alt': top_alt,
                    'dp': '',
                    'star': '',
                    'airways': '',
                    'rnav': rnav
                }
                entry = {'id': eid, 'route_id': route_id, 'dep': dep, 'dest': dest, 'type': route_type}
            if line[0:4] == 'PFR2' and entry['dep'] == dep and entry['dest'] == dest and entry['type'] == route_type:
                segment = line[22:70].strip()
                seg_type = line[70:77].strip()
                if seg_type in ['DP', 'STAR', 'AIRWAY']:
                    segments = segment.split()
                    if len(segments) > 1:
                        if '(RNAV)' in segments:
                            row['rnav'] = "required"
                    name = ' '.join(s for s in segments if s not in ['(RNAV)', '(CANADIAN)']).strip()
                    try:
                        if seg_type == 'AIRWAY':
                            airways.append(segment)
                        else:
                            segment = procedures[name]['procedure']
                            row[seg_type.lower()] = segment
                    except KeyError:
                        pass
                route.append(segment)
    # aircraft = {e: { 'engine': '', 'rnav': '', 'gnss': ''} for e in set(e['aircraft'] for e in rows)}
    # alts = {e: { 'min_alt': '', 'max_alt': '', 'fix': '', 'engine': '', 'speed': ''} for e in set(e['altitude'] for e in rows)}
    # with open('faa_ac.json', 'w') as f:
    #     f.write(json.dumps(aircraft))
    # with open('faa_alt.json', 'w') as f:
    #     f.write(json.dumps(alts))
    return prefroute_rows


def write_prefroutes(route_rows):
    with open('out/faa_prd.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'dep', 'dest', 'route', 'dp', 'star', 'airways', 'type', 'rnav',
                                               'lowest_alt', 'top_alt'])
        writer.writeheader()
        writer.writerows(route_rows)


def parse_awy():
    rows = []
    with open(AWY_FILENAME, 'r') as f:
        entry = {}
        for line in f.readlines():
            awy_name = line[4:9].strip()
            if line[:4] == 'AWY1':
                if entry:
                    rows.append(entry)
                mea = '/'.join([line[74:79].lstrip('0').strip(), line[85:90].lstrip('0').strip()]).strip('/')
                cross_alt = '/'.join([line[110:115].lstrip('0').strip(), line[122:127].lstrip('0').strip()]).strip('/')
                entry = {
                    'id': uuid.uuid4(),
                    'airway': awy_name,
                    'wpt': '',
                    'type': '',
                    'sequence': line[10:15].strip(),
                    'mea': mea,
                    'max_auth_alt': line[96:101].strip(),
                    'moa': line[101:106].strip(),
                    'min_crossing_alt': cross_alt,
                    'artcc': line[141:144].strip()
                }
            if line[:4] == 'AWY2':
                entry['wpt'] = line[120:160].split('*')[1]
                entry['type'] = line[45:64].strip().replace('REP-PT', 'FIX')
        if rows[-1] != entry:
            rows.append(entry)
    return rows


def write_awy(rows):
    with open('out/airways.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'airway', 'wpt', 'type', 'sequence', 'mea', 'max_auth_alt', 'moa',
                                               'min_crossing_alt', 'artcc'])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    # navaid_rows = parse_navaid_data()
    # airway_rows = parse_awy()
    # fixdata_rows = parse_fixdata()
    # aptdata_rows = parse_aptdata()
    # acdata_rows = parse_acdata()
    stardp_rows = parse_stardp()
    # prefroute_rows = parse_prefroutes()

    # write_cifp_data()
    # write_fixdata(fixdata_rows)
    # write_navaid_data(navaid_rows)
    # write_navdata_combined(navaid_rows, fixdata_rows)
    # write_aptdata(aptdata_rows)
    write_stardp(stardp_rows)
    # write_awy(airway_rows)
    # write_prefroutes(prefroute_rows)
    pass
