from flask import Flask
# from flask_cors import CORS

from blueprints.adar_bp import adar_blueprint
from blueprints.adr_bp import adr_blueprint
from blueprints.faa_bp import faa_blueprint
from blueprints.flightplans_bp import flightplans_blueprint
from blueprints.navdata_bp import navdata_blueprint
from blueprints.prefroute_bp import prefroute_blueprint
from libs.lib import cache
import mongo_client

PREFIX = '/backend'

cache_config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 15
}


def create_app():
    app = Flask(__name__)
    # CORS(app)
    register_extensions(app)
    return app


def register_extensions(app):
    cache.init_app(app, config=cache_config)
    app.register_blueprint(adr_blueprint, url_prefix=f'{PREFIX}/adr')
    app.register_blueprint(adar_blueprint, url_prefix=f'{PREFIX}/adar')
    app.register_blueprint(prefroute_blueprint, url_prefix=f'{PREFIX}/prefroute')
    app.register_blueprint(faa_blueprint, url_prefix=f'{PREFIX}/faa')
    app.register_blueprint(flightplans_blueprint, url_prefix=f'{PREFIX}/flightplan')
    app.register_blueprint(navdata_blueprint, url_prefix=f'{PREFIX}/navdata')

    @app.before_request
    def _get_mongo_client():
        mongo_client.get_fd_mongo_client()
        mongo_client.get_nav_mongo_client()

    @app.after_request
    def _close_mongo_client(response):
        mongo_client.close_fd_mongo_client()
        mongo_client.close_nav_mongo_client()
        return response


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, use_reloader=True)
