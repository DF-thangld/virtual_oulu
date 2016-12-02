import config
import database
import utility
import traci_helper

from traffic_manager import TrafficManager
from flask import Flask, render_template, Response, request
import json
import sqlite3
try:
    from flask_cors import CORS  # The typical way to import flask-cors
except ImportError:
    # Path hack allows examples to be run without installation.
    import os
    parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.sys.path.insert(0, parentdir)

    from flask.ext.cors import CORS

traffic_manager = TrafficManager()
if (config.ALWAYS_RELOAD_PEOPLE):
    traffic_manager.generate_new_data(config.PEOPLE_COUNT)
#traffic_manager.create_route_file()


app = Flask(__name__)
cors = CORS(app)

@app.route('/vehicles_positions.php')
def vehicles_positions():
    return Response(json.dumps({'time': traffic_manager.simulating_time, 'vehicles_positions': traffic_manager.vehicles_positions, 'congested_places': traffic_manager.congested_places}), 200, mimetype='application/json')

@app.route('/delete_congestion/<congestion_id>')
def delete_congestion(congestion_id):
    traffic_manager.remove_congestion(congestion_id)
    return Response(json.dumps({'success': True, 'congestion_id': congestion_id}), 202, mimetype='application/json')

@app.route('/congest_edge/<lat>/<lon>')
def congest_edge(lat, lon):
    congestion = traffic_manager.add_congestion(lat, lon)
    return Response(json.dumps({'success': True, 'id': congestion['id']}), 200, mimetype='application/json')

@app.route('/update_congest/<congestion_id>/<lat>/<lng>')
def update_congest(congestion_id, lat, lng):
    traffic_manager.update_congestion(congestion_id, lat, lng)
    return Response(json.dumps({'success': True, 'id': congestion_id}), 200, mimetype='application/json')

@app.route('/')
def index():
    return render_template('index.html')

traffic_manager.start()
app.run(debug=False, port=5000, host='0.0.0.0', threaded=True)
