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
        congestion_count = len(traffic_manager.congested_places)
        for i in range(0, congestion_count-1):
            if traffic_manager.congested_places[i]['id'] == congestion_id:
                del traffic_manager.congested_places[i]
                return Response(json.dumps({'success': True, 'congestion_id': congestion_id}), 200, mimetype='application/json')

        return Response(json.dumps({'success': False, 'congestion_id': congestion_id}), 404, mimetype='application/json')


    @app.route('/congest_edge/<lat>/<lon>')
    def congest_edge(lat, lon):
        (x, y) = traffic_manager.from_latlon(float(lat), float(lon))


        traffic_manager.congested_places.append({'id': utility.generate_random_string(20), 'x': x, 'y': y, 'lat': lat, 'lon': lon})
        return Response(json.dumps({'success': True}), 200, mimetype='application/json')

        connection = database.create_connection()
        
        size_to_check = 3
        size_block = 1
        max_x = x+size_to_check
        min_x = x-size_to_check
        max_y = y+size_to_check
        min_y = y-size_to_check
        
        edges_query = 'select * from edges_full_data where (from_x>=? and from_x<=? and from_y>=? and from_y<=?) \
                        or (to_x>=? and to_x<=? and to_y>=? and to_y<=?) order by edge_id, sequence desc'
        row_edges = database.query_all(edges_query, (min_x, max_x, min_y, max_y, min_x, max_x, min_y, max_y), connection)

        edges = []
        for row in row_edges:
            edges.append({'sequence': row['sequence'], "edge_id": row['edge_id'], "from_x": row['from_x'], "from_y": row['from_y'], "to_x": row['to_x'], "to_y": row['to_y']})
        
        edges_lens = len(edges)
        result_edges = []
        for edge in edges:
            (from_lat, from_lon) = traffic_manager.to_latlon(float(edge['from_x']), float(edge['from_y']))
            (to_lat, to_lon) = traffic_manager.to_latlon(float(edge['to_x']), float(edge['to_y']))
            edge['from_lat'] = from_lat
            edge['from_lon'] = from_lon
            edge['to_lat'] = to_lat
            edge['to_lon'] = to_lon
            
            traffic_manager.congested_places.append({'id': utility.generate_random_string(20), 'edge_id': edge['edge_id'], 'x': x, 'y': y, 'lat': lat, 'lon': lon})
            
            if utility.calculate_distance(x, y, edge['from_x'], edge['from_y'], edge['to_x'], edge['to_y']) <= size_block:
                blocked_position = database.query_one('select sum(distance) total_distance from edges_full_data where edge_id=? and sequence<=?', (edge['edge_id'], edge['sequence']), connection)['total_distance']
                edge['total_distance'] = blocked_position
                result_edges.append(edge)
                #traffic_manager.traci_action_queue.append({'action': 'CREATE_CONGESTION', 'parameter': {'edge_id': edge['edge_id'], 'position': blocked_position}})
                '''for vehicle in traffic_manager.vehicles_positions:
                    if vehicle['current_edge_id'] == edge['edge_id']:
                        traffic_manager.traci_action_queue.append({'action': 'STOP_VEHICLE', 'parameter': {'vehicle_id': vehicle['vehicle_id']}})'''
        
        (lat_1, lon_1) = traffic_manager.to_latlon(max_x, max_y)
        (lat_2, lon_2) = traffic_manager.to_latlon(max_x, min_y)
        (lat_3, lon_3) = traffic_manager.to_latlon(min_x, max_y)
        (lat_4, lon_4) = traffic_manager.to_latlon(min_x, min_y)
        
        database.close_connection(connection, True)
        result_json = {'lat_lon': {'lat': lat, 'lon': lon},
                       'max_lat_max_lon': {'lat': lat_1, 'lon': lon_1},
                       'max_lat_min_lon': {'lat': lat_2, 'lon': lon_2},
                       'min_lat_max_lon': {'lat': lat_3, 'lon': lon_3},
                       'min_lat_min_lon': {'lat': lat_4, 'lon': lon_4},
                       'edges': result_edges}
        return Response(json.dumps(result_json), 200, mimetype='application/json')
        
    
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
    
    app.run(debug=False, port=5000, host='0.0.0.0')
