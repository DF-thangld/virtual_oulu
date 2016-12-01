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

if __name__ == "__main__":
    traffic_manager = TrafficManager()
    if (config.ALWAYS_RELOAD_PEOPLE):
        traffic_manager.generate_new_data(config.PEOPLE_COUNT)
    #traffic_manager.create_route_file()
    
    traffic_manager.start()
    app = Flask(__name__)
    cors = CORS(app)
    
    @app.route('/vehicles_positions.php')
    def vehicles_positions():
        return Response(json.dumps({'time': traffic_manager.simulating_time, 'vehicles_positions': traffic_manager.vehicles_positions, 'congested_places': traffic_manager.congested_places}), 200, mimetype='application/json')
    
    @app.route('/get_nodes')
    def get_nodes():
        
        conn = sqlite3.connect(config.DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('select * from oulu_nodes')
        rows = cur.fetchall()
        
        result = []
        for row in rows:
            result.append({'id': row['id'],
                           'lat': row['lat'],
                           'lon': row['lon'],
                           'type': row['type']})
        conn.close()
        return Response(json.dumps(result), 200, mimetype='application/json')
    
    @app.route('/get_edges')
    def get_edges():
        conn = sqlite3.connect(config.DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('select * from oulu_edges')
        rows = cur.fetchall()
        
        result = []
        for row in rows:
            result.append({'id': row['id'],
                           'from': row['from'],
                           'to': row['to'],
                           'shape': row['shape']})
        conn.close()
        return Response(json.dumps(result), 200, mimetype='application/json')

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

    @app.route('/get_places')
    def get_places():
        conn = sqlite3.connect(config.DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute('SELECT a.*, c.lat from_lat, c.lon from_lon, d.lat to_lat, d.lon to_lon, b.shape \
            FROM places a \
            left join oulu_edges b on a.edge_id = b.id \
            left join oulu_nodes c on b.`from` = c.id \
            left join oulu_nodes d on b.`to` = d.id \
            where a.is_coord_get = 1 \
            order by main_type, type')
        rows = cur.fetchall()
        result = []
        
        for row in rows:
            result.append({'id' : row['id'],
                           'main_type': row['main_type'],
                           'type': row['type'],
                           'name': row['name'],
                           'lat': row['lat'],
                           'lon': row['lon'],
                           'from_lat': row['from_lat'],
                           'from_lon': row['from_lon'],
                           'to_lat': row['to_lat'],
                           'to_lon': row['to_lon'],
                           'shape': row['shape']})
        
        conn.close()
        return Response(json.dumps(result), 200, mimetype='application/json')
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/non_stop_vehicles.php')
    def non_stop_vehicles():
        return render_template('non_stop_vehicles.html')
    
    app.run(debug=False, port=5000, host='0.0.0.0', threaded=True)
