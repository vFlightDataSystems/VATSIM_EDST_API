from flask import g
from pymongo import MongoClient
from config import *


def get_reader_client():
    return MongoClient(MONGO_URL,
                       username='reader',
                       password=MONGO_READER_PASS,
                       authSource='admin')


def get_edst_client():
    return MongoClient(MONGO_URL,
                       username=MONGO_EDST_USER,
                       password=MONGO_EDST_PASS,
                       authSource='edst')


def get_fd_mongo_client():
    if 'mongo_fd_client' not in g:
        g.mongo_fd_client = MongoClient(MONGO_URL,
                                        username=MONGO_FD_USER,
                                        password=MONGO_FD_PASS,
                                        authSource='flightdata')
    return g.mongo_fd_client


def get_nav_mongo_client():
    if 'mongo_nav_client' not in g:
        g.mongo_nav_client = MongoClient(MONGO_URL,
                                         username=MONGO_NAV_USER,
                                         password=MONGO_NAV_PASS,
                                         authSource='navdata')
    return g.mongo_nav_client


def get_reader_mongo_client():
    if 'mongo_reader_client' not in g:
        g.mongo_reader_client = get_reader_client()

    return g.mongo_reader_client


def get_adapt_mongo_client():
    if 'mongo_adapt_client' not in g:
        g.mongo_adapt_client = MongoClient(MONGO_URL,
                                           username=MONGO_ADAPT_USER,
                                           password=MONGO_ADAPT_PASS,
                                           authSource='adaptationProfiles')
    return g.mongo_nav_client


def get_edst_mongo_client():
    if 'mongo_edst_client' not in g:
        g.mongo_edst_client = get_edst_client()
    return g.mongo_edst_client


def close_fd_mongo_client(e=None):
    client = g.pop('mongo_fd_client', None)
    if client is not None:
        client.close()


def close_nav_mongo_client(e=None):
    client = g.pop('mongo_nav_client', None)
    if client is not None:
        client.close()


def close_reader_mongo_client(e=None):
    client = g.pop('mongo_reader_client', None)
    if client is not None:
        client.close()


def close_adapt_mongo_client(e=None):
    client = g.pop('mongo_adapt_client', None)
    if client is not None:
        client.close()


def close_edst_mongo_client(e=None):
    client = g.pop('mongo_edst_client', None)
    if client is not None:
        client.close()


reader_client = get_reader_client()
