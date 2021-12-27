import atexit

from flask import Flask
# from flask_cors import CORS
import threading

import libs.edst_lib
from blueprints.adaptation_bp import adaptation_blueprint
from blueprints.edst_bp import edst_blueprint
from blueprints.flightplans_bp import flightplans_blueprint
from blueprints.navdata_bp import navdata_blueprint
from blueprints.prefroute_bp import prefroute_blueprint
from blueprints.weather_bp import weather_blueprint
from libs.lib import cache
import mongo_client

PREFIX = '/backend'

cache_config = {
    "DEBUG": True,  # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 15
}

# data_lock = threading.Lock()
update_thread = threading.Thread()
POOL_TIME = 20


def create_app():
    app = Flask(__name__)
    # CORS(app)
    register_extensions(app)

    def interrupt():
        global update_thread
        update_thread.cancel()

    def loop():
        global update_thread
        # with data_lock:
        libs.edst_lib.update_edst_data()
        update_thread = threading.Timer(POOL_TIME, loop, ())
        update_thread.start()

    def start_loop():
        # Do initialisation stuff here
        global update_thread
        # Create your thread
        update_thread = threading.Timer(POOL_TIME, loop, ())
        update_thread.start()

    # Initiate
    start_loop()
    atexit.register(interrupt)
    return app


def register_extensions(app):
    cache.init_app(app, config=cache_config)
    # app.register_blueprint(adr_blueprint, url_prefix=f'{PREFIX}/adr')
    # app.register_blueprint(adar_blueprint, url_prefix=f'{PREFIX}/adar')
    app.register_blueprint(prefroute_blueprint, url_prefix=f'{PREFIX}/prefroute')
    # app.register_blueprint(faa_blueprint, url_prefix=f'{PREFIX}/faa')
    app.register_blueprint(flightplans_blueprint, url_prefix=f'{PREFIX}/flightplan')
    app.register_blueprint(navdata_blueprint, url_prefix=f'{PREFIX}/navdata')
    app.register_blueprint(adaptation_blueprint, url_prefix=f'{PREFIX}/adaptation')
    app.register_blueprint(weather_blueprint, url_prefix=f'{PREFIX}/weather')
    app.register_blueprint(edst_blueprint, url_prefix=f'{PREFIX}/edst')

    @app.before_request
    def _get_mongo_clients():
        mongo_client.get_reader_mongo_client()

    @app.after_request
    def _close_mongo_clients(response):
        mongo_client.close_reader_mongo_client()
        return response


if __name__ == '__main__':
    app = create_app()
    app.run(use_reloader=True)
