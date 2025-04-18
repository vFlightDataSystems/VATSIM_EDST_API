from flask import Flask
from flask_cors import CORS
import threading

from blueprints.edst_bp import edst_blueprint
from blueprints.navdata_bp import navdata_blueprint
from blueprints.prefroute_bp import prefroute_blueprint
from blueprints.weather_bp import weather_blueprint
from blueprints.route_analysis_bp import route_analysis_blueprint
import mongo_client

PREFIX = '/api'


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['CORS_HEADERS'] = 'Content-Type'
    register_extensions(app)
    return app

def register_extensions(app):
    app.register_blueprint(prefroute_blueprint, url_prefix=f'{PREFIX}/prefroute')
    app.register_blueprint(navdata_blueprint, url_prefix=f'{PREFIX}/navdata')
    app.register_blueprint(weather_blueprint, url_prefix=f'{PREFIX}/weather')
    app.register_blueprint(edst_blueprint, url_prefix=f'{PREFIX}/edst')
    app.register_blueprint(route_analysis_blueprint, url_prefix=f'{PREFIX}/route')

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
