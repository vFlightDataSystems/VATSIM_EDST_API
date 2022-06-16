import logging
import re

import libs.lib as lib


def amend_adr(route: str, adr: dict) -> dict:
    """

    :param route:
    :param adr: adr dictionary as it is returned from the database
    :return: dictionary containing: the adr upto tfix, rest of the route starting after the tfix, route groups for the adr
    """
    route = lib.format_route(route)
    adr_route = adr['route']
    # if adr matches initial route, there is nothing to do.
    if adr_route == route[:len(adr_route)]:
        adr_route = ''
    else:
        expanded_adr = adr['route_fixes']
        tfixes = adr['transition_fixes']
        tfix_info_dict = {e['tfix']: e['info'] for e in adr['transition_fixes_details']}
        for tfix in reversed(tfixes):
            # find farthest tfix which triggered the ADR
            tfix_info = tfix_info_dict[tfix]
            if tfix in route:
                if 'Append' in tfix_info:
                    route = route[route.index(tfix):]
                    break
                elif 'Explicit' in tfix_info:
                    dot_counter = int(tfix_info.split('-')[-1])
                    adr_route = (re.split(r'\.', adr_route[::-1], adr_route.count('.') - dot_counter)[-1])[::-1] \
                        .rstrip('.')
                    route = route[route.index(tfix) + len(tfix):]
                    break
            if 'Implicit' in tfix_info:
                try:
                    dot_counter, implicit_trigger = tfix_info.split('-')[0:]
                    adr_route = f'{implicit_trigger}' \
                                + ('.' + re.split(r'\.', adr_route[::-1],
                                                  adr_route.count('.') - int(dot_counter))[-1])[::-1]
                    index = route.index(implicit_trigger)
                    if index:
                        route = route[index:]
                    else:
                        route_fix = [e for e in expanded_adr if e in route][0]
                        route = route[route.index(route_fix) + len(tfix):]
                    break
                except (IndexError, ValueError) as e:
                    logging.Logger(str(e))
                    pass
    return {
        'adr_amendment': adr_route,
        'route': route,
        'eligible': adr['eligible'],
        'order': adr['order'],
        'route_groups': adr['route_groups']
    }