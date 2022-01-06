import logging
import re

from flask import g
from pymongo import MongoClient

import libs.lib
import mongo_client


def amend_aar(route: str, aar: dict) -> dict:
    """

    :param route:
    :param aar: adr dictionary as it is returned from the database
    :return:
    """
    aar_route = aar['route']
    if aar_route == route[len(aar_route):]:
        aar_route = ''
    else:
        expanded_aar = aar['route_fixes']
        tfixes = aar['transition_fixes']
        tfix_info_dict = {e['tfix']: e['info'] for e in aar['transition_fixes_details']}
        for tfix in tfixes:
            # find first tfix which triggered the AAR
            tfix_info = tfix_info_dict[tfix]
            if tfix in route:
                print(tfix)
                if 'Prepend' in tfix_info:
                    route = route[:route.index(tfix)+len(tfix)]
                    break
                elif 'Explicit' in tfix_info:
                    dot_counter = int(tfix_info.split('-')[-1])
                    aar_route = '.' + re.split(r'\.', aar_route, dot_counter)[-1]
                    route = route[:route.index(tfix)+len(tfix)]
                    break
            if 'Implicit' in tfix_info:
                try:
                    dot_counter, implicit_trigger = tfix_info.split('-')[0:]
                    aar_route = re.split(r'\.', aar_route, int(dot_counter))[-1]
                    index = route.index(implicit_trigger)
                    if index:
                        route = route[:index+len(tfix)]
                    else:
                        route_fix = [e for e in expanded_aar if e in route][0]
                        route = route[:route.index(route_fix)+len(tfix)]
                    break
                except (IndexError, ValueError) as e:
                    logging.Logger(str(e))
                    pass
    return {
        'aar_amendment': aar_route,
        'route': route,
        'order': aar['order'],
        'route_groups': aar['route_groups']
    }


def get_eligible_aar(edst_entry, requesting_artcc) -> list:
    aircraft = edst_entry['flightplan']['aircraft_short']
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    nat_list = libs.lib.get_nat_types(aircraft) + ['NATALL']
    aar_list = client.flightdata.aar.find(
        {"airports": edst_entry['dest'],
         "applicable_artcc": requesting_artcc.upper(),
         "aircraft_class": {"$elemMatch": {"$in": nat_list}}
         }, {'_id': False})
    eligible_aar = []
    alt = int(edst_entry['altitude'])*100
    route = edst_entry['route']
    expanded_route = libs.lib.expand_route(route).split()
    for aar in aar_list:
        if (int(aar['min_alt']) <= alt <= int(aar['top_alt'])) or alt == 0:
            for tfix_details in aar['transition_fixes_details']:
                if (('Explicit' in tfix_details['info'] and
                     tfix_details['tfix'] in route) or
                        ('Implicit' in tfix_details['info'] and
                         tfix_details['tfix'] in expanded_route) or
                        (tfix_details['tfix'] in expanded_route and
                         tfix_details['info'] == 'Prepend')):
                    eligible_aar.append(aar)
                    break
    return eligible_aar
