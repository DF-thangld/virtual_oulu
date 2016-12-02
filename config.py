DATABASE_FILE = 'data/data.sqlite'
NETWORK_FILE = 'data/plain_network/oulu.edg.xml'
NETWORK_NODE_FILE = 'data/plain_network/oulu.nod.xml'
SUMO_DIR = 'E:\Documents\Projects\sumo-0.23.0'
SUMO_APP_DIR = '/opt/local/bin/sumo'
DUAROUTER_APP_DIR = '/opt/local/bin/duarouter'
SUMO_NETWORK_FILE = 'data/oulu.net.xml'
SIMULATION_CONFIG_FILE = 'data/oulu.sumocfg'

MAX_DISTANCE = 5
DISTANCE_TO_STOP = 5
DAY_STARTING_TIME = 0
REFRESH_RATE = 1 #1 second in real world equal to 1 second in simulation
MAX_REFRESH_RATE = 512
NUMBER_PEOPLE_CONTROLLERS = 1
DAY_CYCLE = 3600*24
TIME_PER_STEP = 0.01

SUMO_PORT = 9952

PEOPLE_COUNT = 100000
DEFAULT_MOVING_TIME = 1800 # assume that moving time take half an hour

USE_REAL_TIME = False
MINUMUM_VEHICLES = 100
TIME_START = 8*3600
ALWAYS_RELOAD_PEOPLE = False
DELETE_OLD_DATA = False
TOTAL_PEOPLE = 20000

SERVER_URL = 'http://localhost:5000/'
GOOGLE_KEY = 'AIzaSyB4O9doFyBaUVS1WjUgqbTBfIQ3K4IMhMA'

# in case uwsgi cannot run sumo by itself
RUN_SUMO = True
