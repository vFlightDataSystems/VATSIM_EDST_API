import requests
import libs.lib as lib


def get_artcc_aar(artcc: str, airport: str = ''):
    response = requests.get(
        f'https://data-api.virtualnas.net/api/pars?artccId={artcc.upper()}&airportId={airport.upper()}')
    return response.json()


def truncate_route(route: str, route_fixes: list, tfix: str):
    remaining_route = route
    if tfix in route:
        remaining_route = route[:route.index(tfix)]
    else:
        for fix in route_fixes[:route_fixes.index(tfix)][::-1]:
            if fix in route:
                following_segment = route[fix + len(fix):].strip('.').split('.')[0]
                remaining_route = route[route.index(following_segment):]
                break
    return remaining_route


def amend_aar(route: str, aar: dict) -> dict:
    """

    :param route:
    :param aar: aar dictionary as it is returned from the database
    :return:
    """
    aar_route = aar['route']
    route_fixes = lib.get_route_fixes(route, aar['airportIds'])
    triggered_tfix = None
    tfixes = aar['transitionFixesDetails']
    for tfix in tfixes:
        fix = tfix['fix']
        # find first tfix which triggered the AAR
        if fix in route_fixes:
            triggered_tfix = tfix
            info = tfix['type']
            if info == 'Explicit':
                aar_route = aar_route[aar_route.index(fix):]
            elif info == 'Implicit':
                implicit_segment = tfix['implicitSegmentName']
                index = aar_route.index(implicit_segment)
                if index:
                    aar_route = f'{fix}.' + aar_route[index:]
            elif info == 'Prepend':
                aar_route = fix + aar_route
            break
    return {
        'aar_amendment': aar_route,
        'tfix': triggered_tfix['fix'],
        'eligible': aar['eligible'],
        'route': truncate_route(route, route_fixes, triggered_tfix['fix']),
        'order': aar['order'],
        'routeGroups': aar['routeGroups']
    } if triggered_tfix else None
