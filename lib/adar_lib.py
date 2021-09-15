from pymongo import MongoClient


def get_best_adar(client: MongoClient, dep: str, dest: str, altitude: int, aircraft: str, equipment: list,
                  route_groups: set) -> list:
    """

    :param client:
    :param altitude:
    :param dep:
    :param dest:
    :param aircraft:
    :param equipment:
    :param route_groups:
    :return:
    """
    return []
