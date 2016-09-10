from flask import Flask,render_template, request
import sqlite3
import json

app = Flask(__name__)


@app.route('/')
def homepage():
    return render_template('get_coords.html')

@app.route('/workplaces')
def get_workplaces():
	conn = sqlite3.connect('data.sqlite')
	conn.row_factory = sqlite3.Row
	cur = conn.cursor()
	fetch_workplaces = "select * from works where is_coord_get=0 and name != '' LIMIT 6"
	cur.execute(fetch_workplaces)
	rows = cur.fetchall()
	
	returned_data = []
	for row in rows:
		returned_data.append({'id' : row['id'],
					'address' : row['address'],
					'mail_address' : row['mail_address']})
	conn.close()
	return json.dumps(returned_data)
	
@app.route('/get_leisure_places')
def get_leisure_places():
	return render_template('get_leisure_places.html')

@app.route('/leisure_places')
def leisure_places():
	conn = sqlite3.connect('data.sqlite')
	conn.row_factory = sqlite3.Row
	cur = conn.cursor()
	fetch_leisures = "select * from leisure where is_coord_get=0 LIMIT 6"
	cur.execute(fetch_leisures)
	rows = cur.fetchall()
	
	returned_data = []
	for row in rows:
		returned_data.append({'place_id' : row['place_id']})
	conn.close()
	return json.dumps(returned_data)
	
@app.route('/update_leisure_places')
def update_leisure_places():
	return render_template('update_leisure_places.html')
	
@app.route('/update_leisure_place', methods=['POST'])
def update_leisure_place():
	conn = sqlite3.connect('data.sqlite')
	conn.row_factory = sqlite3.Row
	cur = conn.cursor()
	args = request.get_json(force=True)
	update_query = "update leisure \
					set name=?,address=?,lat=?,lon=?,type=?,is_coord_get=1\
					where place_id=?"
	cur.execute(update_query, (args['name'], args['address'], args['lat'], args['lon'], args['type'], args['place_id']))
	conn.commit()
	conn.close()
	return "{'insert' : 'ok'}"

@app.route('/update_leisure_place_error', methods=['POST'])
def update_leisure_place_error():
	conn = sqlite3.connect('data.sqlite')
	conn.row_factory = sqlite3.Row
	cur = conn.cursor()
	args = request.get_json(force=True)
	update_query = "update leisure \
					set is_coord_get=3\
					where place_id=?"
	cur.execute(update_query, (args['place_id'],))
	conn.commit()
	conn.close()
	return "{'insert' : 'ok'}"
	
@app.route('/insert_leisure_place', methods=['POST'])
def insert_leisure_place():
	conn = sqlite3.connect('data.sqlite')
	conn.row_factory = sqlite3.Row
	cur = conn.cursor()
	args = request.get_json(force=True)
	update_query = "insert into leisure (place_id) values (?)"
	cur.execute(update_query, (args['place_id'],))
	conn.commit()
	conn.close()
	return "{'insert' : 'ok'}"
	
@app.route('/update_workplace', methods=['POST'])
def update_workplace():
	
	conn = sqlite3.connect('data.sqlite')
	conn.row_factory = sqlite3.Row
	cur = conn.cursor()
	args = request.get_json(force=True)
	update_query = "update works set lat=?, lon=?, is_coord_get=1 where id=?"
	cur.execute(update_query, (args['lat'], args['lon'], args['id']))
	conn.commit()
	conn.close()
	return "{'success' : 'ok'}"
	
@app.route('/workplace_not_found', methods=['POST'])
def workplace_not_found():
	
	conn = sqlite3.connect('data.sqlite')
	conn.row_factory = sqlite3.Row
	cur = conn.cursor()
	args = request.get_json(force=True)
	update_query = "update works set is_coord_get=3 where id=?"
	cur.execute(update_query, (args['id'],))
	conn.commit()
	conn.close()
	return "{'success' : 'ok'}"

if __name__ == '__main__':
	app.run(debug=True)