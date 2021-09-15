import csv
import re
import uuid
from pathlib import Path

NATTYPE_FILENAME = 'ACCriteriaTypes.csv'


def parse_ac_criteria():
    pass


def parse_adar(filename):
    out_name = filename.stem.split('_')[-1] + '_adar'
    rows = []
    index_rows = []
    with open(filename, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            alphas = entry['Auto Route Alphas'].split('\n')
            row = {
                'id': uuid.uuid4(),
                'route': '',
                'dp': '',
                'star': '',
                'airways': '',
                'min_alt': entry['Lower Altitude'],
                'top_alt': entry['Upper Altitude'],
                'ierr': entry['IERR Criteria'],
                'aircraft_class': entry['AC Class Criteria'],
                'order': entry['Order'],
                'route_groups': entry['Route Groups']
            }
            for e in alphas:
                if e[:13] == '(RouteString)':
                    row['route'] = re.sub(r'\.+', ' ', e[13:]).strip()
                if e[:9] == '(Airways)':
                    row['airways'] = e[9:].strip()
                if e[:6] == '(DpId)':
                    row['dp'] = e[6:].strip()
                if e[:8] == '(StarId)':
                    row['star'] = e[8:].strip()
            if row['route']:
                for dep in entry['Dep Airports'].split():
                    for dest in entry['Arr Airports'].split():
                        index_rows.append({
                            'id': uuid.uuid4(),
                            'dep': dep,
                            'dest': dest,
                            'route_groups': row['route_groups'],
                            'ierr': row['ierr'],
                            'aircraft_class': row['aircraft_class'],
                            'order': row['order'],
                            'adar_id': row['id']
                        })
                rows.append(row)
    with open(f'out/{out_name}.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'route', 'dp', 'star', 'airways', 'min_alt', 'top_alt',
                                               'ierr', 'aircraft_class', 'order', 'route_groups'])
        writer.writeheader()
        writer.writerows(rows)
    with open(f'out/{out_name}_index.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'dep', 'dest', 'aircraft_class', 'ierr', 'route_groups', 'order',
                                               'adar_id'])
        writer.writeheader()
        writer.writerows(index_rows)


if __name__ == '__main__':
    files = Path('AdaptedRoutes').rglob('adar_*.csv')
    for file in files:
        parse_adar(file)
    pass
