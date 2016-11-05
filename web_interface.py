from flask import Flask, render_template, Response, request
import threading
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

import config

app = Flask(__name__)
app.config.from_object('config')
cors = CORS(app)

@app.route('/')
def index():
    return render_template('index.html', server=config.SERVER_URL)

app.run(debug=True, port=5001, host='0.0.0.0')
