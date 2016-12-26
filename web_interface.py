from flask import Flask, render_template, Response, request
import json
import Pyro4
try:
    from flask_cors import CORS  # The typical way to import flask-cors
except ImportError:
    # Path hack allows examples to be run without installation.
    import os
    parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.sys.path.insert(0, parentdir)

    from flask.ext.cors import CORS

import config

app = Flask(__name__)
app.config.from_object('config')
cors = CORS(app)

@app.route('/')
def index():
    return render_template('index.html', server=config.SERVER_URL)

@app.route('/vehicles_positions.php')
def vehicles_positions():
    server = Pyro4.Proxy('PYRO:virtual_oulu@' + config.SERVER_HOST + ':' + str(config.SERVER_PORT))
    vehicles_positions = server.get_vehicles_positions()
    return Response(json.dumps(vehicles_positions), 200, mimetype='application/json')

@app.route('/delete_congestion/<congestion_id>')
def delete_congestion(congestion_id):
    server = Pyro4.Proxy('PYRO:virtual_oulu@' + config.SERVER_HOST + ':' + str(config.SERVER_PORT))
    server.delete_congestion(congestion_id)

    return Response(json.dumps({'success': True, 'congestion_id': congestion_id}), 202, mimetype='application/json')

@app.route('/congest_edge/<lat>/<lon>')
def congest_edge(lat, lon):
    server = Pyro4.Proxy('PYRO:virtual_oulu@' + config.SERVER_HOST + ':' + str(config.SERVER_PORT))
    congestion_id = server.add_congestion(lat, lon)

    return Response(json.dumps({'success': True, 'id': congestion_id}), 200, mimetype='application/json')

@app.route('/update_congest/<congestion_id>/<lat>/<lng>')
def update_congest(congestion_id, lat, lng):
    server = Pyro4.Proxy('PYRO:virtual_oulu@' + config.SERVER_HOST + ':' + str(config.SERVER_PORT))
    congestion_id = server.update_congestion(congestion_id, lat, lng)

    return Response(json.dumps({'success': True, 'id': congestion_id}), 200, mimetype='application/json')

@app.route('/delete_vehicle/<vehicle_id>')
def delete_vehicle(vehicle_id):
    server = Pyro4.Proxy('PYRO:virtual_oulu@' + config.SERVER_HOST + ':' + str(config.SERVER_PORT))
    server.delete_vehicle(vehicle_id)

    return Response(json.dumps({'success': True, 'vehicle_id': vehicle_id}), 202, mimetype='application/json')

@app.route('/get_traffic_lights')
def get_traffic_lights():
    import xml.etree.ElementTree as ET
    import sqlite3
    import config

    tree = ET.parse('data/plain_network/oulu.tll.xml')
    root = tree.getroot()
    results = []
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    for connection in root.iter('connection'):
        from_edge = connection.get('from')
        to_edge = connection.get('to')
        traffic_light_id = connection.get('tl')

        def get_nodes(edge_id, database_cursor):
            sql = 'select * from oulu_edges where id=?'
            database_cursor.execute(sql, (edge_id,))
            row = database_cursor.fetchone()
            if row is not None:
                return [row['from'], row['to']]
            return None
        def get_node_info (node_id, database_cursor):
            sql = 'select * from oulu_nodes where id=?'
            database_cursor.execute(sql, (node_id,))
            row = database_cursor.fetchone()
            if row is not None:
                return {'id': row['id'], 'x': row['x'], 'y': row['y'], 'lat': row['lat'], 'lon': row['lon']}
            return None

        from_nodes = get_nodes(from_edge, cur)
        to_nodes = get_nodes(to_edge, cur)

        node = None
        if from_nodes[0] == to_nodes[0] or from_nodes[0] == to_nodes[1]:
            node = from_nodes[0]
        elif from_nodes[1] == to_nodes[0] or from_nodes[1] == to_nodes[1]:
            node = from_nodes[1]
        if node is not None:
            node_info = get_node_info(node, cur)
            if node_info is not None:
                results.append({'node_id': node_info['id'],
                                'lat': node_info['lat'],
                                'lon': node_info['lon'],
                                'tl': traffic_light_id})

    return Response(json.dumps(results), 200, mimetype='application/json')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)

