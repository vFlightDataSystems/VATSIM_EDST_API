import time
import os
from datetime import datetime, timedelta, timezone
from flask import Flask
from flask_cors import CORS
import threading

from blueprints.edst_bp import edst_blueprint
from blueprints.navdata_bp import navdata_blueprint
from blueprints.prefroute_bp import prefroute_blueprint
from blueprints.weather_bp import weather_blueprint
from blueprints.route_analysis_bp import route_analysis_blueprint
import mongo_client

from libs.wind_lib import download_rap_grib2, interpolate_uv_temp_at_flight_levels, get_date
from libs.weather_data_lock import weather_data, data_lock

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

def run_updater():
    """Run once at startup and then every hour at HH:05 UTC."""
    while True:
        try:
            # Always run once immediately at startup
            date_str, cycle_hour, forecast_hour, save_path = get_date()
            download_rap_grib2(date_str, cycle_hour, forecast_hour, save_path)
            interpolate_uv_temp_at_flight_levels(save_path)
            processed_at = datetime.now(timezone.utc).isoformat()
            new_state = {
                'String': date_str,
                'Cycle': cycle_hour,
                'Forecast Hour': forecast_hour,
                'Processed At': processed_at
            }
            with data_lock:
                weather_data['wx_state'] = new_state
                weather_data['last_updated_utc'] = processed_at
                weather_data['grib_path'] = save_path

            print(f"[Updater] Weather data updated {date_str} {cycle_hour}z f{forecast_hour}")

            # schedule next run at the next HH:05 UTC
            now = datetime.now(timezone.utc)
            next_run = now.replace(minute=5, second=0, microsecond=0)
            if now >= next_run:
                next_run = next_run + timedelta(hours=1)
            sleep_seconds = (next_run - now).total_seconds()
            print(f"[Updater] Next run scheduled at {next_run.isoformat()} (in {int(sleep_seconds)}s)")
            time.sleep(sleep_seconds)

        except Exception as e:
            print("Updater error:", e)
            time.sleep(300)  # retry in 5 min if failed


if __name__ == '__main__':
    # Only start updater in the *main process*, not the reloader
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        updater_thread = threading.Thread(target=run_updater, daemon=True)
        updater_thread.start()

    app = create_app()
    app.run(use_reloader=True)