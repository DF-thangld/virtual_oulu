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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)

