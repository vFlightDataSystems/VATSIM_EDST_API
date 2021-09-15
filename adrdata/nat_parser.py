import csv
import uuid

NATTYPE_FILENAME = 'ACCriteriaTypes.csv'


def parse():
    rows = []
    with open(NATTYPE_FILENAME, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for entry in reader:
            rows.append({
                'id': uuid.uuid4(),
                'class': entry['Aircraft Class Criteria ID'],
                'owner': entry['Owning Facility'],
                'type': entry['Criteria Type'],
                'aircraft': entry['Aircraft Type']
            })
    with open('nat_types.csv', 'w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'class', 'owner', 'type', 'aircraft'])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    parse()
