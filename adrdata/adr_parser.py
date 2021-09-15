import csv
import re
import uuid
from pathlib import Path

NATTYPE_FILENAME = 'ACCriteriaTypes.csv'


def parse_ac_criteria():
    pass


def parse_adr(filename):
    out_name = filename.stem.split('_')[-1] + '_adr'
    rows = []
    index_rows = []
    with open(filename, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            tfixes = entry['Transition Fixes Detail']
            airports = entry['Airports']
            alphas = entry['Auto Route Alphas'].split('\n')
            row = {
                'id': uuid.uuid4(),
                'route': '',
                'dp': '',
                'airways': '',
                'route_groups': entry['Route Groups'],
                'min_alt': entry['Lower Altitude'],
                'top_alt': entry['Upper Altitude'],
                'ierr': entry['IERR Criteria'],
                'aircraft_class': entry['AC Class Criteria'],
                'tfixes': tfixes,
                'order': entry['Order'],
                'xlines': entry['XLines'],
                'airports': airports
            }
            for e in alphas:
                if e[:13] == '(RouteString)':
                    row['route'] = re.sub(r'\.+', ' ', e[13:]).strip()
                if e[:9] == '(Airways)':
                    row['airways'] = e[9:].strip()
                if e[:6] == '(DpId)':
                    row['dp'] = e[6:].strip()
            if row['route']:
                for apt in row['airports'].split():
                    for tfix in row['tfixes'].split():
                        info = re.search(r'\((.*)\)', tfix).group(0)
                        index_rows.append({
                            'id': uuid.uuid4(),
                            'airport': apt,
                            'tfix': tfix.replace(info, ''),
                            'info': info[1:-1],
                            'route_groups': row['route_groups'],
                            'aircraft_class': row['aircraft_class'],
                            'ierr': row['ierr'],
                            'xlines': row['xlines'],
                            'order': row['order'],
                            'adr_id': row['id']
                        })
                rows.append(row)
    with open(f'out/{out_name}.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'route', 'dp', 'airways', 'min_alt', 'top_alt', 'aircraft_class',
                                               'ierr', 'tfixes', 'airports', 'order', 'xlines', 'route_groups'])
        writer.writeheader()
        writer.writerows(rows)
    with open(f'out/{out_name}_index.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f,
                                fieldnames=['id', 'airport', 'tfix', 'info', 'aircraft_class', 'ierr', 'route_groups',
                                            'order', 'xlines', 'adr_id'])
        writer.writeheader()
        writer.writerows(index_rows)


if __name__ == '__main__':
    files = Path('AdaptedRoutes').rglob('adr_*.csv')
    for file in files:
        parse_adr(file)
    pass
