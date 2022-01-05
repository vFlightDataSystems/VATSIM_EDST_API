import csv
import re
import json
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
CDR_FILENAME = NASR_DIR + '/CDR.txt'

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
                    rows.append(
                        {'navaid_id': nav_id, 'type': nav_type, 'name': name, 'lat': lat, 'lon': lon})
    return rows


def write_navaid_data(rows):
    with open('out/navaid_data.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['navaid_id', 'type', 'name', 'lat', 'lon'])
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
                rows.append({'fix_id': fix_id, 'name': name, 'lat': lat, 'lon': lon})
    return rows


def write_fixdata(rows):
    with open('out/fixdata.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['fix_id', 'name', 'lat', 'lon'])
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
        writer = csv.DictWriter(f, fieldnames=['waypoint_id', 'type', 'name', 'lat', 'lon'])
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
                                fieldnames=['code', 'icao', 'city', 'name', 'artcc', 'elevation', 'lat', 'lon'])
        writer.writeheader()
        writer.writerows(rows)


def parse_stardp():
    rows = []
    with open(STARDP_FILENAME, 'r') as stardp_f, \
            open(CIFP_FILENAME, 'r') as cifp_f:
        cifp_lines = defaultdict(list)
        for line in cifp_f.readlines():
            cifp_lines[line[13:19].strip()].append(line)
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
                t_lines = [l for l in cifp_lines[procedure] if (
                        (fix_type == 'AA' and fix in line[6:10]) or True)]
                airports = list(set(l[6:10] for l in t_lines if l[20:25] == transition))
                entry['routes'].append(
                    {'transition': transition, 'name': transition_name, 'route': route, 'airports': airports})
                route = [fix]
            elif fix_type == 'AA' and route:
                _transitions = []
                t_lines = [l for l in cifp_lines[procedure] if (
                        (fix_type == 'AA' and fix in line[6:10]) or True)]
                rw_lines = [l for l in t_lines if
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
                    airports = list(set(l[6:10] for l in t_lines if l[20:25] == transition))
                    entry['routes'].append(
                        {'transition': transition, 'name': transition_name, 'route': route, 'airports': airports})
                else:
                    entry['routes'] += [{'transition': t[1], 'name': transition_name, 'route': route,
                                         'airports': t[0]} for t in _transitions]
                route = []
            else:
                route.append(fix)

            if npid != pid:
                procedure = e[0].strip() if npid[0] == 'D' else e[1].strip()
                procedure_name = line[51:161].strip()
                if entry:
                    rows.append(entry)
                entry = {'type': 'DP' if npid[0] == 'D' else 'STAR',
                         'routes': [],
                         'transitions': [],
                         'procedure': procedure,
                         'name': procedure_name
                         }
            if len(e) > 1:
                transition = e[1].strip() if npid[0] == 'D' else e[0].strip()
                if transition not in entry['transitions']:
                    entry['transitions'].append(transition)
                transition_name = line[51:161].strip()
            pid = npid

    return rows


def write_stardp(rows):
    with open('out/stardp.json', 'w', newline='', encoding='utf8') as f:
        f.write(json.dumps(rows))


def parse_prefroutes(stardp_rows):
    procedures = {' '.join(p['name'].split()[:-1]): p for p in stardp_rows}
    prefroute_rows = []
    prev_is_fix = True
    with open(PREFROUTES_FILENAME, 'r') as f:
        entry = {}
        row = {}
        route = ''
        airways = []
        for line in f.readlines():
            dep = line[4:9].strip()
            dest = line[9:14].strip()
            route_type = line[14:17].strip()
            if line[0:4] == 'PFR1':
                route = route + f'.{"." if prev_is_fix else ""}'
                prev_is_fix = True
                if entry:
                    row['route'] = route
                    row['airways'] = ' '.join(airways).strip()
                    prefroute_rows.append(row)
                route = ''
                airways = []
                row = {
                    'dep': dep,
                    'dest': dest,
                    'dp': '',
                    'star': '',
                    'airways': ''
                }
                entry = {'dep': dep, 'dest': dest, 'type': route_type}
            if line[0:4] == 'PFR2' and entry['dep'] == dep and entry['dest'] == dest and entry['type'] == route_type:
                segment = line[22:70].strip()
                seg_type = line[70:77].strip()
                if seg_type in ['DP', 'STAR', 'AIRWAY']:
                    prev_is_fix = False
                    segments = segment.split()
                    name = ' '.join(s for s in segments if s not in ['(RNAV)', '(CANADIAN)']).strip()
                    try:
                        if seg_type == 'AIRWAY':
                            airways.append(segment)
                        else:
                            segment = procedures[name]['procedure']
                            row[seg_type.lower()] = segment
                    except KeyError:
                        pass
                    segment = f'.{segment}'
                else:
                    segment = f'{"." if prev_is_fix else ""}.{segment}'
                    prev_is_fix = True
                route += segment
    return prefroute_rows


def write_prefroutes(route_rows):
    with open('out/faa_prd.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['dep', 'dest', 'route', 'dp', 'star', 'airways'])
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
        writer = csv.DictWriter(f, fieldnames=['airway', 'wpt', 'type', 'sequence', 'mea', 'max_auth_alt', 'moa',
                                               'min_crossing_alt', 'artcc'])
        writer.writeheader()
        writer.writerows(rows)


def parse_cdr():
    rows = []
    with open(CDR_FILENAME, 'r') as f:
        for line in f.readlines():
            fields = line.split(',')
            rows.append({
                'code': fields[0].strip(),
                'dep': fields[1].strip(),
                'dest': fields[2].strip(),
                'dp_fix': fields[3].strip(),
                'route': fields[4].strip(),
                'artcc': fields[5].strip()
            })
    return rows


def write_cdr(rows):
    with open('out/cdr.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['code', 'dep', 'dest', 'dp_fix', 'route', 'artcc'])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    stardp_rows = parse_stardp()
    navaid_rows = parse_navaid_data()
    airway_rows = parse_awy()
    fixdata_rows = parse_fixdata()
    aptdata_rows = parse_aptdata()
    cdr_rows = parse_cdr()
    prefroute_rows = parse_prefroutes(stardp_rows)

    write_cifp_data()
    write_fixdata(fixdata_rows)
    write_navaid_data(navaid_rows)
    write_navdata_combined(navaid_rows, fixdata_rows)
    write_aptdata(aptdata_rows)
    write_stardp(stardp_rows)
    write_cdr(cdr_rows)
    write_awy(airway_rows)
    write_prefroutes(prefroute_rows)
    pass
