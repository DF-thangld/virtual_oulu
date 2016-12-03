

#import native python libraries
import sqlite3
from random import randint
from datetime import datetime
import threading
import os
import sys
import shutil
from multiprocessing import Process
import time
import datetime
import json

#import external libraries
from asq.initiators import query
import xml.etree.ElementTree as ET
import utm

#import internal classes
import utility
from person import Person
import config
import traci_helper

tools = os.path.join(os.getcwd(), 'sumo_tools')
sys.path.append(tools)
import traci as traci  # @UnresolvedImport

#logging info
import logging
logger = logging.getLogger('virtual_oulu')
hdlr = logging.FileHandler('logs/virtual_oulu.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr) 
logger.setLevel(logging.INFO)
logger.info('start app')

class TrafficManager(threading.Thread):
    '''
    TODO:
    1. Skip to the soonest action
    2. Create a class to control people (should run by different thread)
    '''
    OFFSET_X = -414982.40
    OFFSET_Y = -7194168.66

    def __init__(self, database_file=None, network_file=None, network_node_file=None, sumo_network_file=None, simulation_config_file=None, sumo_dir=None):
        super(TrafficManager, self).__init__()

        # private variables definition
        min_lat = 64.864240
        max_lat = 65.118303
        min_lon = 25.196334
        max_lon = 25.844493

        #public variables
        self.sumo_port = config.SUMO_PORT

        if (database_file is None):
            self.database_file = config.DATABASE_FILE
        else:
            self.database_file = database_file

        if (network_file is None):
            self.network_file = config.NETWORK_FILE
        else:
            self.network_file = network_file

        if (network_node_file is None):
            self.network_node_file = config.NETWORK_NODE_FILE
        else:
            self.network_node_file = network_node_file

        if (sumo_network_file is None):
            self.sumo_network_file = config.SUMO_NETWORK_FILE
        else:
            self.sumo_network_file = sumo_network_file

        if (simulation_config_file is None):
            self.simulation_config_file = config.SIMULATION_CONFIG_FILE
        else:
            self.simulation_config_file = simulation_config_file
        # public variables definition
        self.workplaces = []
        self.leisure_places = []
        self.restaurant_places = []
        self.schools = []
        self.stores = []
        self.female_first_names = []
        self.male_first_names = []
        self.last_names = []
        self.residentials = []
        self.residential_count = 0
        self.car_lanes = []
        self.car_lanes_count = 0
        self.people = []
        self.people_controllers = []
        self.traci_action_queue = []
        self.congested_places = []

        self.current_step = 0
        self.simulating_time = 0
        self.vehicles = []
        self.current_day = 0
        self.subscribed_cars = {}

        self.vehicles_positions = {}

        # database connection
        conn = sqlite3.connect(self.database_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # network edges connection
        tree = ET.parse(self.network_file)
        root = tree.getroot()

        # get places
        fetch_places = "select * from places where is_coord_get=1 and edge_id is not null"
        cur.execute(fetch_places)
        rows = cur.fetchall()
        for row in rows:
            place = {}
            place['name'] = row['name']
            place['address'] = row['address']
            place['lat'] = float(row['lat'])
            place['lon'] = float(row['lon'])
            place['id'] = row['id']
            place['type'] = row['type']
            place['edge_id'] = row['edge_id']
            # if the place's coordinate inside Oulu => added to its type list
            if (place['lat'] > min_lat
                and place['lat'] < max_lat
                and place['lon'] > min_lon
                and place['lon'] < max_lon):
                if row['main_type'] == 'leisure':
                    self.leisure_places.append(place)
                elif row['main_type'] == 'meal':
                    self.restaurant_places.append(place)
                elif row['type'] == 'university':
                    self.schools.append(place)
                elif row['main_type'] == 'store':
                    self.stores.append(place)
                elif row['main_type'] == 'workplace':
                    self.workplaces.append(place)

        # get first names
        fetch_first_names = "select * from first_names"
        cur.execute(fetch_first_names)
        rows = cur.fetchall()
        for row in rows:
            if row['gender'] == 'M':
                self.male_first_names.append(row['name'])
            elif row['gender'] == 'F':
                self.female_first_names.append(row['name'])

        # get last names
        fetch_last_names = "select * from last_names"
        cur.execute(fetch_last_names)
        rows = cur.fetchall()
        for row in rows:
            self.last_names.append(row['name'])

        # get vehicles
        fetch_last_names = "select * from car_types"
        cur.execute(fetch_last_names)
        rows = cur.fetchall()
        for row in rows:
            self.vehicles.append({"id": row['id'],
                                  "name": row['name'],
                                  "accel": row['accel'],
                                  "decel": row['decel'],
                                  "sigma": row['sigma'],
                                  "length": row['length'],
                                  "min_gap": row['minGap'],
                                  "max_speed": row['maxSpeed'],
                                  "model_file": row['model_file'],
                                  "description": row['description']})

        # get list of residential edges
        for edge in root.iter('edge'):
            if (edge.get('type') == 'highway.residential' and self.non_car_lanes_count(edge)<int(edge.get('numLanes'))):
                self.residential_count += 1
                self.residentials.append(edge.get('id'))

        # get list of edges that normal can access
        ''' condition (or):
            1. Have no <lane> child
            2. Number of lanes higher than non-car lanes
                - None car lanes: exists in <lane> child tag with allow='delivery', 'pedestrian', vip, bicycle, rail
        '''
        for edge in root.iter('edge'):
            if self.non_car_lanes_count(edge) < int(edge.attrib['numLanes']):
                self.car_lanes.append({'id': edge.attrib['id'], 'from': edge.attrib['from'], 'to': edge.attrib['to']})
                self.car_lanes_count += 1

        # close database connection
        conn.close()

        # all preparing finished, start loading people
        self.load_people(config.TOTAL_PEOPLE)


    def non_car_lanes_count(self, edge):
        lanes = edge.findall("./lane")
        if len(lanes) == 0:
            return 0
        non_car_lanes = 0
        for lane in lanes:
            if (lane.attrib['allow'] in ['delivery', 'pedestrian', 'vip', 'bicycle', 'rail']):
                non_car_lanes += 1
        return non_car_lanes

    def to_latlon(self, x, y):
        lat, lon = utm.to_latlon(x - TrafficManager.OFFSET_X, y - TrafficManager.OFFSET_Y, 35, zone_letter='W')
        return (lat, lon)

    def from_latlon(self, lat, lon):
        latlon = utm.from_latlon(lat, lon)
        return (latlon[0] + TrafficManager.OFFSET_X, latlon[1] + TrafficManager.OFFSET_Y)

    def find_nearest_edge(self, x, y):
        '''
        Distance from a node to an edge: the smallest between those 3 distances
            - Distance from the node to the "from" node of the edge
            - Distance from the node to the "to" node of the edge
            - Distance from the node to the line
        '''
        edge_tree = ET.parse(self.network_file)
        edge_root = edge_tree.getroot()

        node_tree = ET.parse(self.network_node_file)
        node_root = node_tree.getroot()
        nearest_distance = 9999999999999999
        nearest_edge = None
        for edge in edge_root.iter('edge'):
            if self.non_car_lanes_count(edge) < int(edge.attrib['numLanes']):

                distance = 0

                node_from = node_root.find("./node[@id='" + edge.attrib['from'] + "']")
                node_to = node_root.find("./node[@id='" + edge.attrib['to'] + "']")
                x1 = float(node_from.attrib['x'])
                y1 = float(node_from.attrib['y'])
                x2 = float(node_to.attrib['x'])
                y2 = float(node_to.attrib['y'])

                distance = utility.calculate_distance(x, y, x1, y1, x2, y2)

                # choose the nearest distance
                if (distance < nearest_distance):
                    nearest_distance = distance
                    nearest_edge = edge

        return nearest_edge

    def create_random_person(self, number_of_day=1):
        ''' THE NUMBERS ARE ALL MADE UP AND NEED TO BE CHANGED AFTER PROPER SURVEY
        - Age from 18 to 55 (either going to school or working)
            + 18-22: 35% going to school, 55% working, 10% stay at home
            + 23-28: 65% going to school, 25% working, 10% stay at home
            + 29-55: 80% working, 20% stay at home
        - Gender random between M and F (50-50)
        - Name random
        - Workplace is random
        - School is a random university
        - home is a random edge in network file
        '''
        new_person = Person()

        # the person's id
        new_person.id = utility.generate_random_string(20)
        # the person's age
        new_person.age = randint(18,55)

        #the person's gender
        chance_gender = randint(1,100)
        if chance_gender<=50:
            new_person.gender = Person.GENDER_FEMALE
        else:
            new_person.gender = Person.GENDER_MALE

        #the person's name
        chance_first_name = randint(1,100)
        chance_last_name = randint(0, len(self.last_names)-1)
        if (new_person.gender == Person.GENDER_FEMALE):
            new_person.name = self.female_first_names[chance_first_name-1]
        else:
            new_person.name = self.male_first_names[chance_first_name-1]
        new_person.name = new_person.name + ' ' + self.last_names[chance_last_name]

        #the person's working status
        chance_working_status = randint(1,100)
        if (new_person.age>=18 and new_person.age<=22):
            if chance_working_status <= 70:
                new_person.working_status = Person.STATUS_STUDYING
            elif chance_working_status <= 90:
                new_person.working_status = Person.STATUS_WORKING
            else:
                new_person.working_status = Person.STATUS_STAY_AT_HOME
        elif (new_person.age>=23 and new_person.age<=28):
            if chance_working_status <= 55:
                new_person.working_status = Person.STATUS_STUDYING
            elif chance_working_status <= 90:
                new_person.working_status = Person.STATUS_WORKING
            else:
                new_person.working_status = Person.STATUS_STAY_AT_HOME
        else:
            if chance_working_status <= 80:
                new_person.working_status = Person.STATUS_WORKING
            else:
                new_person.working_status = Person.STATUS_STAY_AT_HOME

        # the person's workplace
        if (new_person.working_status == Person.STATUS_WORKING):
            chance_workplace = randint(0, len(self.workplaces)-1)
            new_person.work_address = {	'id': self.workplaces[chance_workplace]['id'],
                                        'name': self.workplaces[chance_workplace]['name'],
                                        'address': self.workplaces[chance_workplace]['address'],
                                        'lat': self.workplaces[chance_workplace]['lat'],
                                        'lon': self.workplaces[chance_workplace]['lon'],
                                        'edge_id': self.workplaces[chance_workplace]['edge_id']}

        # the person's university
        if (new_person.working_status == Person.STATUS_STUDYING):
            chance_university = randint(0, len(self.schools)-1)
            new_person.school_address = {	'id': self.schools[chance_university]['id'],
                                        'name': self.schools[chance_university]['name'],
                                        'address': self.schools[chance_university]['address'],
                                        'lat': self.schools[chance_university]['lat'],
                                        'lon': self.schools[chance_university]['lon'],
                                        'edge_id': self.schools[chance_university]['edge_id']}
        # the person's house
        chance_house = randint(0, self.residential_count-1)
        new_person.home_address['edge_id'] = self.residentials[chance_house]

        # the person's car
        chance_car = randint(0, len(self.vehicles)-1)
        new_person.vehicle = self.vehicles[chance_car]['id']

        # the person's day plan
        self.generate_day_plan(new_person, number_of_day)

        # return the person
        return new_person

    def generate_day_plan(self,person, number_of_day=1):
        '''
        - If working:
            + Going to work from 7AM to 9AM, stay there for 8 hours
            + After work, 20% go to restaurant for dinner (if go to restaurant, stay there for 1-2 hours), 70% go home, 10% go to shopping places (stay there for 0.5-1 hour then go home)
            + At night, 30% go to some leisure place and stay there for 2-3 hours (from 7AM to 9AM), the person go straight from restaurant to the leisure place. 70% just stay at home, the person also go home if had dinner at restaurant
        - If going to school:
            + 70% go to school at random time from 7:00-14:00, stay there for a random duration between 2 hours to 6 hours
            + If stay at home or have more than 4 empty hours during morning then: 40% go to shopping places (stay there for 0.5-1 hour), 40% go to leisure places (stay there for 1-2 hours, if time less than 1 hour then straight to the next destination, else go home), 20% stay at home
            + At night 30% go to leisure place, 70% stay at home
        - If staying at home:
            + 40% go to a shopping place from 9-11 or 15-17, stay there for 0.5-1 hour then go home, 60% just stay at home
            + If stay at home during afternoon then 30% go to a leisure place (stay there for 1-2 hours) from 2pm to 5pm
            + 20% go to restaurant from 6pm to 7pm, stay there for 1 hour. If end time of leisure place is 1 hour apart from restaurant time then go straight to restaurant from the leisure place.
            + At night 30% go to a leisure place and stay there for 2-3 hour from 8pm-10pm. If the person have dinner out then go straight to the leisure place from the restaurant.
        '''
        chance_event = 0
        chance_place = 0
        chance_time = 0
        chance_duration = 0
        sequence = 1
        total_second_in_one_day = 24*3600

        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                'sequence' : sequence,
                                'type': 'DUMMY',
                                'from_place_id': -1,
                                'from_edge_id' : -1,
                                'to_place_id': -1,
                                'to_edge_id' : -1,
                                'duration': 5,
                                'time': 20})
        sequence += 1

        for current_day in range(number_of_day):
            if person.working_status == Person.STATUS_WORKING:

                # workplace
                workplace = query(self.workplaces).single(lambda workplace: workplace['id'] == person.work_address['id'])
                # some variables
                go_to_restaurant = False
                chance_restaurant_place = 0

                #time go to work from 7AM to 9AM => 120 minutes
                chance_time = randint(current_day*total_second_in_one_day+7*3600, current_day*total_second_in_one_day+9*3600)
                #go to work
                person.day_plan.append({'action_id': utility.generate_random_string(20),
                                        'sequence' : sequence,
                                        'type': 'MOVING',
                                        'from_place_id': -1,
                                        'from_edge_id' : person.home_address['edge_id'],
                                        'to_place_id': workplace['id'],
                                        'to_edge_id' : workplace['edge_id'],
                                        'duration': -1,
                                        'time': chance_time})
                sequence += 1
                # working
                person.day_plan.append({'action_id': utility.generate_random_string(20),
                                        'sequence' : sequence,
                                        'type': 'WORKING',
                                        'from_place_id': workplace['id'],
                                        'from_edge_id' : workplace['edge_id'],
                                        'to_place_id': workplace['id'],
                                        'to_edge_id' : workplace['edge_id'],
                                        'duration': randint(8*3600, 9*3600),
                                        'time': -1})
                sequence+=1
                # go for dinner
                chance_event = randint(0, 100)
                if chance_event <= 20: #go to restaurant
                    # go to restaurant
                    go_to_restaurant = True
                    chance_restaurant_place = randint(0, len(self.restaurant_places)-1)
                    chance_time = randint(60*60, 120*60)
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': workplace['id'],
                                            'from_edge_id' : workplace['edge_id'],
                                            'to_place_id': self.restaurant_places[chance_restaurant_place]['id'],
                                            'to_edge_id': self.restaurant_places[chance_restaurant_place]['edge_id'],
                                            'duration': -1,
                                            'time': -1})
                    sequence+=1
                    #time at restaurant
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'EATING',
                                            'from_place_id': self.restaurant_places[chance_restaurant_place]['id'],
                                            'from_edge_id': self.restaurant_places[chance_restaurant_place]['edge_id'],
                                            'to_place_id': self.restaurant_places[chance_restaurant_place]['id'],
                                            'to_edge_id': self.restaurant_places[chance_restaurant_place]['edge_id'],
                                            'duration': chance_time,
                                            'time': -1})
                    sequence+=1
                elif chance_event <= 30: # go shopping
                    # go to store
                    chance_place = randint(0, len(self.stores)-1)
                    chance_time = randint(30*60, 60*60)
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': workplace['id'],
                                            'from_edge_id' : workplace['edge_id'],
                                            'to_place_id': self.stores[chance_place]['id'],
                                            'to_edge_id': self.stores[chance_place]['edge_id'],
                                            'duration': -1,
                                            'time': -1})
                    sequence+=1
                    #time at store
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'SHOPPING',
                                            'from_place_id': self.stores[chance_place]['id'],
                                            'from_edge_id': self.stores[chance_place]['edge_id'],
                                            'to_place_id': self.stores[chance_place]['id'],
                                            'to_edge_id': self.stores[chance_place]['edge_id'],
                                            'duration': chance_time,
                                            'time': -1})
                    sequence+=1
                    #go home
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': self.stores[chance_place]['id'],
                                            'from_edge_id': self.stores[chance_place]['edge_id'],
                                            'to_place_id': -1,
                                            'to_edge_id': person.home_address['edge_id'],
                                            'duration': -1,
                                            'time': -1})
                    sequence+=1
                else: #go home from work
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': workplace['id'],
                                            'from_edge_id': workplace['edge_id'],
                                            'to_place_id': -1,
                                            'to_edge_id': person.home_address['edge_id'],
                                            'duration': -1,
                                            'time': -1})
                    sequence+=1

                # go to leisure place at night
                chance_event = randint(0, 100)
                if chance_event <= 30: # go to leisure place
                    chance_place = randint(0, len(self.leisure_places)-1)
                    chance_duration = randint(1.5*3600, 3*3600)
                    # go to leisure place
                    if go_to_restaurant: # go straight from restaurant
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': self.restaurant_places[chance_restaurant_place]['id'],
                                                'from_edge_id': self.restaurant_places[chance_restaurant_place]['edge_id'],
                                                'to_place_id': self.leisure_places[chance_place]['id'],
                                                'to_edge_id': self.leisure_places[chance_place]['edge_id'],
                                                'duration': -1,
                                                'time': -1})
                        sequence+=1
                    else: # go from home at random time 7PM to 9PM
                        chance_time = randint(current_day*total_second_in_one_day+19*3600, current_day*total_second_in_one_day+21*3600)
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': -1,
                                                'from_edge_id': person.home_address['edge_id'],
                                                'to_place_id': self.leisure_places[chance_place]['id'],
                                                'to_edge_id': self.leisure_places[chance_place]['edge_id'],
                                                'duration': -1,
                                                'time': chance_time})
                        sequence+=1
                    #stay at leisure place
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'LEISURE',
                                            'from_place_id': self.leisure_places[chance_place]['id'],
                                            'from_edge_id': self.leisure_places[chance_place]['edge_id'],
                                            'to_place_id': self.leisure_places[chance_place]['id'],
                                            'to_edge_id': self.leisure_places[chance_place]['edge_id'],
                                            'duration': chance_duration,
                                            'time': -1})
                    sequence+=1
                    #go home from leisure place
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': self.leisure_places[chance_place]['id'],
                                            'from_edge_id': self.leisure_places[chance_place]['edge_id'],
                                            'to_place_id': -1,
                                            'to_edge_id': person.home_address['edge_id'],
                                            'duration': chance_duration,
                                            'time': -1})
                    sequence+=1
                else:
                    if go_to_restaurant: #go home if have dinner at restaurant
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': self.restaurant_places[chance_restaurant_place]['id'],
                                                'from_edge_id': self.restaurant_places[chance_restaurant_place]['edge_id'],
                                                'to_place_id': -1,
                                                'to_edge_id': person.home_address['edge_id'],
                                                'duration': -1,
                                                'time': -1})
                        sequence+=1
            elif person.working_status == Person.STATUS_STUDYING: # go to school
                university = query(self.schools).single(lambda school: school['id'] == person.school_address['id'])

                go_to_shopping = False

                chance_go_to_school = randint(0, 100)
                if chance_go_to_school <= 70: # school day
                    time_go_to_school = randint(current_day*total_second_in_one_day+7*3600, current_day*total_second_in_one_day+14*3600)
                    duration_at_school = randint(2*3600, 6*3600)
                    if time_go_to_school >= current_day*total_second_in_one_day+12*3600: #go to school at evening
                        chance_free_time_morning = randint(0, 100)
                        if chance_free_time_morning <= 40: #go shopping from 8am to 10am, stay 0.5 to 1 hour
                            go_to_shopping = True
                            time_go_shopping = randint(current_day*total_second_in_one_day+8*3600, current_day*total_second_in_one_day+10*3600)
                            duration_shopping = randint(0.5*3600, 3600)
                            chance_shopping_place = randint(0, len(self.stores)-1)
                            #move to shopping place
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'MOVING',
                                                    'from_place_id': -1,
                                                    'from_edge_id': person.home_address['edge_id'],
                                                    'to_place_id': self.stores[chance_shopping_place]['id'],
                                                    'to_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                    'duration': -1,
                                                    'time': time_go_shopping})
                            sequence+=1
                            #actually shopping
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'SHOPPING',
                                                    'from_place_id': self.stores[chance_shopping_place]['id'],
                                                    'from_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                    'to_place_id': self.stores[chance_shopping_place]['id'],
                                                    'to_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                    'duration': duration_shopping,
                                                    'time': -1})
                            sequence+=1
                            #to home
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'MOVING',
                                                    'from_place_id': self.stores[chance_shopping_place]['id'],
                                                    'from_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                    'to_place_id': -1,
                                                    'to_edge_id': person.home_address['edge_id'],
                                                    'duration': -1,
                                                    'time': -1})
                            sequence+=1
                        elif chance_free_time_morning <= 80: # go to leisure place
                            time_leisure_place = randint(current_day*total_second_in_one_day+8*3600, current_day*total_second_in_one_day+9*3600)
                            duration_leisure_place = randint(3600, 2*3600)
                            chance_leisure_place = randint(0, len(self.leisure_places)-1)
                            #move to leisure place
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'MOVING',
                                                    'from_place_id': -1,
                                                    'from_edge_id': person.home_address['edge_id'],
                                                    'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                    'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                    'duration': -1,
                                                    'time': time_leisure_place})
                            sequence+=1
                            #actually time at leisure place
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'SHOPPING',
                                                    'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                    'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                    'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                    'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                    'duration': duration_leisure_place,
                                                    'time': -1})
                            sequence+=1
                            #to home
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'MOVING',
                                                    'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                    'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                    'to_place_id': -1,
                                                    'to_edge_id': person.home_address['edge_id'],
                                                    'duration': -1,
                                                    'time': -1})
                            sequence+=1

                        #go to school
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': -1,
                                                'from_edge_id': person.home_address['edge_id'],
                                                'to_place_id': person.school_address['id'],
                                                'to_edge_id': person.school_address['edge_id'],
                                                'duration': -1,
                                                'time': time_go_to_school})
                        sequence+=1
                        #stay at school
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'SCHOOLING',
                                                'from_place_id': person.school_address['id'],
                                                'from_edge_id': person.school_address['edge_id'],
                                                'to_place_id': person.school_address['id'],
                                                'to_edge_id': person.school_address['edge_id'],
                                                'duration': duration_at_school,
                                                'time': -1})
                        sequence+=1
                        #go home from school
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': person.school_address['id'],
                                                'from_edge_id': person.school_address['edge_id'],
                                                'to_place_id': -1,
                                                'to_edge_id': person.home_address['edge_id'],
                                                'duration': -1,
                                                'time': -1})
                        sequence+=1
                    elif time_go_to_school + duration_at_school <= current_day*total_second_in_one_day+13*3600: #free time during afternoon
                        #go to school
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': -1,
                                                'from_edge_id': person.home_address['edge_id'],
                                                'to_place_id': person.school_address['id'],
                                                'to_edge_id': person.school_address['edge_id'],
                                                'duration': -1,
                                                'time': time_go_to_school})
                        sequence+=1
                        #stay at school
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'SCHOOLING',
                                                'from_place_id': person.school_address['id'],
                                                'from_edge_id': person.school_address['edge_id'],
                                                'to_place_id': person.school_address['id'],
                                                'to_edge_id': person.school_address['edge_id'],
                                                'duration': duration_at_school,
                                                'time': -1})
                        sequence+=1
                        #go home from school
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': person.school_address['id'],
                                                'from_edge_id': person.school_address['edge_id'],
                                                'to_place_id': -1,
                                                'to_edge_id': person.home_address['edge_id'],
                                                'duration': -1,
                                                'time': -1})
                        sequence+=1

                        chance_free_time_afternoon = randint(0, 100)
                        if chance_free_time_afternoon <= 40: #go shopping from 3pm to 5am, stay 0.5 to 1 hour
                            go_to_shopping = True
                            time_go_shopping = randint(current_day*total_second_in_one_day+15*3600, current_day*total_second_in_one_day+17*3600)
                            duration_shopping = randint(0.5*3600, 3600)
                            chance_shopping_place = randint(0, len(self.stores)-1)
                            #move to shopping place
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'MOVING',
                                                    'from_place_id': -1,
                                                    'from_edge_id': person.home_address['edge_id'],
                                                    'to_place_id': self.stores[chance_shopping_place]['id'],
                                                    'to_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                    'duration': -1,
                                                    'time': time_go_shopping})
                            sequence+=1
                            #actually shopping
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'SHOPPING',
                                                    'from_place_id': self.stores[chance_shopping_place]['id'],
                                                    'from_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                    'to_place_id': self.stores[chance_shopping_place]['id'],
                                                    'to_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                    'duration': duration_shopping,
                                                    'time': -1})
                            sequence+=1
                            #to home
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'MOVING',
                                                    'from_place_id': self.stores[chance_shopping_place]['id'],
                                                    'from_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                    'to_place_id': -1,
                                                    'to_edge_id': person.home_address['edge_id'],
                                                    'duration': -1,
                                                    'time': -1})
                            sequence+=1
                        elif chance_free_time_afternoon <= 80: # go to leisure place
                            time_leisure_place = randint(current_day*total_second_in_one_day+14*3600, current_day*total_second_in_one_day+16*3600)
                            duration_leisure_place = randint(3600, 2*3600)
                            chance_leisure_place = randint(0, len(self.leisure_places)-1)
                            #move to leisure place
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'MOVING',
                                                    'from_place_id': -1,
                                                    'from_edge_id': person.home_address['edge_id'],
                                                    'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                    'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                    'duration': -1,
                                                    'time': time_leisure_place})
                            sequence+=1
                            #actually time at leisure place
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'SHOPPING',
                                                    'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                    'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                    'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                    'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                    'duration': duration_leisure_place,
                                                    'time': -1})
                            sequence+=1
                            #to home
                            person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                    'sequence' : sequence,
                                                    'type': 'MOVING',
                                                    'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                    'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                    'to_place_id': -1,
                                                    'to_edge_id': person.home_address['edge_id'],
                                                    'duration': -1,
                                                    'time': -1})
                            sequence+=1
                else: #no school during the day
                    chance_free_time = randint(0, 100)
                    if chance_free_time <= 40: #go shopping from 9am to 5am, stay 0.5 to 1 hour
                        go_to_shopping = True
                        time_go_shopping = randint(current_day*total_second_in_one_day+9*3600, current_day*total_second_in_one_day+17*3600)
                        duration_shopping = randint(0.5*3600, 3600)
                        chance_shopping_place = randint(0, len(self.stores)-1)
                        #move to shopping place
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': -1,
                                                'from_edge_id': person.home_address['edge_id'],
                                                'to_place_id': self.stores[chance_shopping_place]['id'],
                                                'to_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                'duration': -1,
                                                'time': time_go_shopping})
                        sequence+=1
                        #actually shopping
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'SHOPPING',
                                                'from_place_id': self.stores[chance_shopping_place]['id'],
                                                'from_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                'to_place_id': self.stores[chance_shopping_place]['id'],
                                                'to_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                'duration': duration_shopping,
                                                'time': -1})
                        sequence+=1
                        #to home
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': self.stores[chance_shopping_place]['id'],
                                                'from_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                                'to_place_id': -1,
                                                'to_edge_id': person.home_address['edge_id'],
                                                'duration': -1,
                                                'time': -1})
                        sequence+=1
                    elif chance_free_time <= 80: # go to leisure place
                        time_leisure_place = randint(current_day*total_second_in_one_day+9*3600, current_day*total_second_in_one_day+17*3600)
                        duration_leisure_place = randint(3600, 2*3600)
                        chance_leisure_place = randint(0, len(self.leisure_places)-1)
                        #move to leisure place
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': -1,
                                                'from_edge_id': person.home_address['edge_id'],
                                                'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                'duration': -1,
                                                'time': time_leisure_place})
                        sequence+=1
                        #actually time at leisure place
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'SHOPPING',
                                                'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                'duration': duration_leisure_place,
                                                'time': -1})
                        sequence+=1
                        #go home
                        person.day_plan.append({'action_id': utility.generate_random_string(20),
                                                'sequence' : sequence,
                                                'type': 'MOVING',
                                                'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                                'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                                'to_place_id': -1,
                                                'to_edge_id': person.home_address['edge_id'],
                                                'duration': -1,
                                                'time': -1})
                        sequence+=1

                # at night
                chance_leisure_evening = randint(0, 100)
                if chance_leisure_evening<=30:
                    time_leisure_place = randint(current_day*total_second_in_one_day+19*3600, current_day*total_second_in_one_day+21*3600)
                    duration_leisure_place = randint(0.5*3600, 3*3600)
                    chance_leisure_place = randint(0, len(self.leisure_places)-1)
                    #move to leisure place
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': -1,
                                            'from_edge_id': person.home_address['edge_id'],
                                            'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'duration': -1,
                                            'time': time_leisure_place})
                    sequence+=1
                    #actually time at leisure place
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'SHOPPING',
                                            'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'duration': duration_leisure_place,
                                            'time': -1})
                    sequence+=1
                    #go home
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'to_place_id': -1,
                                            'to_edge_id': person.home_address['edge_id'],
                                            'duration': -1,
                                            'time': -1})
                    sequence+=1
            elif person.working_status == Person.STATUS_STAY_AT_HOME:
                chance_go_shopping = randint(0, 100)
                chance_go_leisure = randint(0, 100)
                time_go_shopping = 0
                duration_shopping = 0
                if chance_go_shopping >= 50:
                    time_go_shopping = randint(current_day*total_second_in_one_day+9*3600, current_day*total_second_in_one_day+12*3600)
                    duration_shopping = randint(0.5*3600, 3600)
                    chance_shopping_place = randint(0, len(self.stores)-1)
                    #move to shopping place
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': -1,
                                            'from_edge_id': person.home_address['edge_id'],
                                            'to_place_id': self.stores[chance_shopping_place]['id'],
                                            'to_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                            'duration': -1,
                                            'time': time_go_shopping})
                    sequence+=1
                    #actually shopping
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'SHOPPING',
                                            'from_place_id': self.stores[chance_shopping_place]['id'],
                                            'from_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                            'to_place_id': self.stores[chance_shopping_place]['id'],
                                            'to_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                            'duration': duration_shopping,
                                            'time': -1})
                    sequence+=1
                    #to home
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': self.stores[chance_shopping_place]['id'],
                                            'from_edge_id': self.stores[chance_shopping_place]['edge_id'],
                                            'to_place_id': -1,
                                            'to_edge_id': person.home_address['edge_id'],
                                            'duration': -1,
                                            'time': -1})
                    sequence+=1
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'STAY_AT_HOME',
                                            'from_place_id': -1,
                                            'from_edge_id': person.home_address['edge_id'],
                                            'to_place_id': -1,
                                            'to_edge_id': person.home_address['edge_id'],
                                            'duration': randint(0.5*3600, 1.5*3600),
                                            'time': -1})
                    sequence+=1
                if chance_go_leisure >= 50:
                    if chance_go_shopping<50:
                        time_leisure_place = randint(current_day*total_second_in_one_day+9*3600, current_day*total_second_in_one_day+12*3600)
                    else:
                        time_leisure_place = -1
                    duration_leisure_place = randint(3600, 1.5*3600)
                    chance_leisure_place = randint(0, len(self.leisure_places)-1)
                    if chance_go_shopping >= 50:
                        time_leisure_place = randint(time_go_shopping+duration_shopping+1800+3600, current_day*total_second_in_one_day+16*3600)
                    #move to leisure place
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': -1,
                                            'from_edge_id': person.home_address['edge_id'],
                                            'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'duration': -1,
                                            'time': time_leisure_place})
                    sequence+=1
                    #actually time at leisure place
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'LEISURE',
                                            'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'duration': duration_leisure_place,
                                            'time': -1})
                    sequence+=1
                    #go home
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'to_place_id': -1,
                                            'to_edge_id': person.home_address['edge_id'],
                                            'duration': -1,
                                            'time': -1})
                    sequence+=1

                # go to leisure place at night
                chance_leisure_evening = randint(0, 100)
                if chance_leisure_evening<=30:
                    time_leisure_place = randint(current_day*total_second_in_one_day+20*3600, current_day*total_second_in_one_day+22*3600)
                    duration_leisure_place = randint(1.5*3600, 3*3600)
                    chance_leisure_place = randint(0, len(self.leisure_places)-1)
                    #move to leisure place
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': -1,
                                            'from_edge_id': person.home_address['edge_id'],
                                            'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'duration': -1,
                                            'time': time_leisure_place})
                    sequence+=1
                    #actually time at leisure place
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'SHOPPING',
                                            'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'to_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'to_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'duration': duration_leisure_place,
                                            'time': -1})
                    sequence+=1
                    #go home
                    person.day_plan.append({'action_id': utility.generate_random_string(20),
                                            'sequence' : sequence,
                                            'type': 'MOVING',
                                            'from_place_id': self.leisure_places[chance_leisure_place]['id'],
                                            'from_edge_id': self.leisure_places[chance_leisure_place]['edge_id'],
                                            'to_place_id': -1,
                                            'to_edge_id': person.home_address['edge_id'],
                                            'duration': -1,
                                            'time': -1})
                    sequence+=1

        for action in person.day_plan:
            action['vehicle'] = person.vehicle
            action['edges'] = None

    def save_day_plan(self, person, conn):
        #define variables
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        delete_old_plan_query = "delete from day_plans where person_id = ?"
        cur.execute(delete_old_plan_query, (person.id,))
        for action in person.day_plan:
            insert_new_plan_query = "insert into day_plans(action_id, sequence, type, from_place_id, from_edge_id, to_place_id, to_edge_id, duration, time, person_id) \
                                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cur.execute(insert_new_plan_query, (action['action_id'], action['sequence'], action['type'], action['from_place_id'], action['from_edge_id'], action['to_place_id'], action['to_edge_id'], action['duration'], action['time'], person.id))

    def save_person(self,person):
        #open connection to database
        conn = sqlite3.connect(self.database_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        #insert basic information
        insert_query = 'insert into people (id, name, age, gender, home_edge_id, workplace_id, university_id, working_status) values (?, ?, ?, ?, ?, ?, ?, ?)'
        cur.execute(insert_query, (person.id, person.name, person.age, person.gender, person.home_address['edge_id'], person.work_address['id'], person.school_address['id'], person.working_status))

        # insert day plan
        self.save_day_plan(person, conn)

        # commit and close database
        conn.commit()
        conn.close()

    def update_person(self, person, connection=None):
        #open connection to database
        if connection is None:
            conn = sqlite3.connect(self.database_file)
            conn.row_factory = sqlite3.Row
        else:
            conn = connection
        cur = conn.cursor()

        #insert basic information
        insert_query = 'update people set name=?, age=?, gender=?, home_edge_id=?, workplace_id=?, university_id=?, working_status=? where id=?'
        cur.execute(insert_query, (person.name, person.age, person.gender, person.home_address['edge_id'], person.work_address['id'], person.school_address['id'], person.working_status, person.id))

        # insert day plan
        self.save_day_plan(person, conn)

        # commit and close database
        conn.commit()
        if connection is None:
            conn.close()

    def get_person(self, person_id):
        person = Person()
        person.id = person_id

        #connect database
        conn = sqlite3.connect(self.database_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        #get person information
        person_query = 'select * from people where id=?'
        cur.execute(person_query, (person.id, ))
        row = cur.fetchone()
        if row is None:
            return None
        person.age = row['age']
        person.name = row['name']
        person.gender = row['gender']
        person.working_status = row['working_status']
        person.home_address = {'edge_id': row['home_edge_id']} # edge_id, address, lat, lon
        person.vehicle = row['vehicle']

        if person.working_status == Person.STATUS_WORKING:
            workplace = query(self.workplaces).single(lambda workplace: workplace['id'] == row['workplace_id'])
            person.work_address = {	'id': workplace['id'],
                                    'name': workplace['name'],
                                    'address': workplace['address'],
                                    'lat': workplace['lat'],
                                    'lon': workplace['lon'],
                                    'edge_id': workplace['edge_id']}
        else:
            person.work_address = {'id': row['workplace_id']} # id, name, address, lat, lon

        if person.working_status == Person.STATUS_STUDYING:
            university = query(self.schools).single(lambda school: school['id'] == row['university_id'])
            person.school_address = {	'id': university['id'],
                                    'name': university['name'],
                                    'address': university['address'],
                                    'lat': university['lat'],
                                    'lon': university['lon'],
                                    'edge_id': university['edge_id']}
        else:
            person.school_address = {'id': row['workplace_id']} # id, name, address, lat, lon

        #get day plan
        person.day_plan = []
        day_plan_query = 'select * from day_plans where person_id=?'
        cur.execute(day_plan_query, (person.id, ))
        rows = cur.fetchall()
        for row in rows:
            person.day_plan.append({'action_id': row['action_id'].encode('ascii','ignore'),
                                    'sequence' : row['sequence'],
                                    'type': row['type'],
                                    'from_place_id': row['from_place_id'],
                                    'from_edge_id' : row['from_edge_id'],
                                    'to_place_id': row['to_place_id'],
                                    'to_edge_id' : row['to_edge_id'],
                                    'edges' : row['route'],
                                    'duration': row['duration'],
                                    'time': row['time'],
                                    'vehicle': person.vehicle})

        #close connection
        conn.close()

        return person

    def load_people(self, number_of_people=0):
        #refresh people list

        #connect database
        conn = sqlite3.connect(self.database_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        #get current date
        current_date = (int)((self.simulating_time/1000)/(3600*24))
        current_hour = ((self.simulating_time/1000) - current_date*(3600*24))/3600
        if (current_hour > 10):
            current_date += 1
        time_gap = current_date*3600*24

        #get people information
        people_query = 'select * from people ORDER BY RANDOM() '
        if number_of_people > 0:
            people_query += ' limit ' + str(number_of_people)
        cur.execute(people_query)
        rows = cur.fetchall()
        for row in rows:
            person = Person()
            person.id = row['id']
            person.age = row['age']
            person.name = row['name']
            person.gender = row['gender']
            person.working_status = row['working_status']
            person.home_address = {'edge_id': row['home_edge_id']} # edge_id, address, lat, lon
            if person.working_status == Person.STATUS_WORKING:
                workplace = query(self.workplaces).single(lambda workplace: workplace['id'] == row['workplace_id'])
                person.work_address = {	'id': workplace['id'],
                                        'name': workplace['name'],
                                        'address': workplace['address'],
                                        'lat': workplace['lat'],
                                        'lon': workplace['lon'],
                                        'edge_id': workplace['edge_id']}
            else:
                person.work_address = {'id': row['workplace_id']} # id, name, address, lat, lon

            if person.working_status == Person.STATUS_STUDYING:
                university = query(self.schools).single(lambda school: school['id'] == row['university_id'])
                person.school_address = {	'id': university['id'],
                                        'name': university['name'],
                                        'address': university['address'],
                                        'lat': university['lat'],
                                        'lon': university['lon'],
                                        'edge_id': university['edge_id']}
            else:
                person.school_address = {'id': row['workplace_id']} # id, name, address, lat, lon

            person.vehicle = row['vehicle']

            #get day plan
            person.day_plan = []
            day_plan_query = 'select * from day_plans where person_id=?'
            cur.execute(day_plan_query, (person.id, ))
            rows_day_plans = cur.fetchall()
            for row_day_plans in rows_day_plans:
                action_time = row_day_plans['time']
                if (action_time != -1):
                    action_time += time_gap

                action = {'action_id': row_day_plans['action_id'].encode('ascii','ignore'),
                                        'sequence' : row_day_plans['sequence'],
                                        'type': row_day_plans['type'],
                                        'from_place_id': row_day_plans['from_place_id'],
                                        'from_edge_id' : row_day_plans['from_edge_id'],
                                        'to_place_id': row_day_plans['to_place_id'],
                                        'to_edge_id' : row_day_plans['to_edge_id'],
                                        'edges' : row_day_plans['route'],
                                        'duration': row_day_plans['duration'],
                                        'time': action_time,
                                        'vehicle': person.vehicle}

                person.day_plan.append(action)

            if (config.USE_REAL_TIME and current_date == 0):
                person.is_real_time = False
                current_time = datetime.datetime.now()
                current_time_in_second = current_time.hour * 3600 + current_time.minute * 60 + current_time.second
                total_action = len(person.day_plan)
                for i in range(0, total_action - 1):
                    # if person already in realtime mode => next person
                    if person.is_real_time:
                        break

                    # if action has start time and duration ready => continue for next action
                    current_action = person.day_plan[i]

                    if current_action['type'] == 'MOVING':
                        # when loading people, first action is never moving, so it is good
                        if current_action['time'] + 2*config.DEFAULT_MOVING_TIME > current_time_in_second:
                            current_action['duration'] = config.DEFAULT_MOVING_TIME
                        else:
                            person.is_real_time = True

                    if current_action['time'] > -1 and current_action['duration'] > -1:
                        if i < total_action-1 and person.day_plan[i+1]['time'] == -1:
                            person.day_plan[i + 1]['time'] = current_action['time'] + current_action['duration'] + 300
                        continue

                    if current_action['time'] > current_time_in_second or i == total_action - 1:
                        person.is_real_time = True
                        break

            #assign person to people list
            self.people.append(person)

        #close connection
        conn.close()

    def create_trip_file(self, filename, only_first_trip=True):
        #open connection to database
        conn = sqlite3.connect(self.database_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        text_file = open(filename, "w")
        #file header
        text_file.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        text_file.write("<trips>\n")

        #fetch car types
        fetch_first_plan_query = "select * from car_types"
        cur.execute(fetch_first_plan_query)
        rows = cur.fetchall()
        for row in rows:
            text_file.write("\t<vType id=\"" + row['id'] + "\" accel=\"" + str(row['accel']) + "\" decel=\"" + str(row['decel']) + "\" sigma=\"" + str(row['sigma']) + "\" length=\"" + str(row['length']) + "\" minGap=\"" + str(row['minGap']) + "\" maxSpeed=\"" + str(row['maxSpeed']) + "\"/>\n")

        #fetch first plan
        if only_first_trip:
            fetch_first_plan_query = "select a.action_id, a.time, a.from_edge_id, a.to_edge_id, b.vehicle car_id from day_plans a inner join people b on a.person_id = b.id where a.sequence=2 order by a.time asc"
        else:
            fetch_first_plan_query = "select a.action_id, 1 time, a.from_edge_id, a.to_edge_id, b.vehicle car_id from day_plans a inner join people b on a.person_id = b.id where a.type='MOVING' order by a.time asc"
        cur.execute(fetch_first_plan_query)
        rows = cur.fetchall()
        for row in rows:
            text_file.write("\t<trip id=\"" + row['action_id'] + "\" depart=\"" + str(row['time']) + "\" from=\"" + row['from_edge_id'] + "\" to=\"" + row['to_edge_id'] + "\" type=\"" + row['car_id'] + "\"/>\n")

        text_file.write("</trips>")

        #write content to file

        text_file.close()

        #close connection
        conn.close()

    def create_route_file(self):
        trip_file_name = utility.generate_random_string(20) + '.xml'
        all_trip_file_name = utility.generate_random_string(20) + '.xml'
        all_route_file_name = utility.generate_random_string(20) + '.rou.xml'
        current_dir = os.path.dirname(os.path.realpath('__file__'))
        tmp_dir = current_dir + '/tmp/' + utility.generate_random_string(20) + '/'
        #create tmp directory
        os.makedirs(tmp_dir)

        #generate trip file
        #self.create_trip_file(tmp_dir + trip_file_name)
        self.create_trip_file(tmp_dir + all_trip_file_name, False)

        #generate route file by using duarouter
        '''duarouter_command = self.sumo_dir + '/bin/duarouter '
        duarouter_command += ' --trip-files ' + tmp_dir + trip_file_name
        duarouter_command += ' --net-file ' + current_dir + '/' + self.sumo_network_file
        duarouter_command += ' --output-file ' + absolute_filename
        duarouter_command += ' --ignore-errors true'
        os.system(duarouter_command)'''


        #generate route file by using duarouter
        duarouter_command = config.DUAROUTER_APP_DIR
        duarouter_command += ' --trip-files ' + tmp_dir + all_trip_file_name
        duarouter_command += ' --net-file ' + current_dir + '/' + self.sumo_network_file
        duarouter_command += ' --output-file ' + tmp_dir + all_route_file_name
        duarouter_command += ' --ignore-errors true'
        os.system(duarouter_command)


        #open created route file
        routes_tree = ET.parse(tmp_dir + all_route_file_name)
        routes_root = routes_tree.getroot()
        #open database
        conn = sqlite3.connect(self.database_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        #query and update routes to database
        for vehicle in routes_root.iter('vehicle'):
            route = vehicle.find('route').get('edges')
            vehicle_id = vehicle.get('id')
            update_route_query = 'update day_plans set route=? where action_id=?'
            cur.execute(update_route_query, (route, vehicle_id))

        conn.commit()
        conn.close()
        shutil.rmtree(tmp_dir)

        #refresh all people
        self.load_people(config.TOTAL_PEOPLE)

    def generate_new_data(self, number_of_people=1000, number_of_day = 1):
        conn = sqlite3.connect(self.database_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if (config.DELETE_OLD_DATA):
            cur.execute('delete from people')
            cur.execute('delete from day_plans')
            cur.execute('vacuum')
            conn.commit()

        for i in range(0, number_of_people):
            person = self.create_random_person(number_of_day)
            self.save_person(person)
            if i%1000 == 999:
                print(str(i+1) + ' people...')
        print('creating route file...')
        self.create_route_file()
        print('reloading people...')
        conn.close()

        self.load_people(config.TOTAL_PEOPLE)

    def save_current_action(self, action, connection=None):
        if connection is None:
            conn = sqlite3.connect(config.DATABASE_FILE)
            conn.row_factory = sqlite3.Row
        else:
            conn = connection
        cur = conn.cursor()

        update_query = 'update day_plans_template set time=?, duration=?, finish_time=? where action_id=?'
        cur.execute(update_query, (action['time'], action['duration'], action['finish_time'], action['action_id']))
        conn.commit()
        if connection is None:
            conn.close()

    def get_nearest_edges(self, lat, lon):
        pass

    def prepare_next_action(self, person, current_time):
        if len(person.day_plan) > 1:
            if person.day_plan[1]['time'] == -1:
                person.day_plan[1]['time'] = person.day_plan[0]['time'] + person.day_plan[0]['duration'] + 300
            if person.day_plan[1]['type'] == 'MOVING' and person.day_plan[1]['duration'] > -1:
                if person.day_plan[1]['edges'] is not None:
                    try:
                        logger.info('addition vehicle at ' + str(traci_helper.get_current_time()) + ':' + json.dumps(person.day_plan[1]))
                        traci_helper.add_vehicle(person.day_plan[1])
                    except:
                        logger.error(str(traci_helper.get_simulate_time()) + '-' + str(self.simulating_time) + ' - ' + str(person.id) + ' - ' + str(person.day_plan[1]['action_id']))
                        person.day_plan[1]['edges'] = None
                        person.day_plan[1]['duration'] = 30*60
                else:
                    person.day_plan[1]['duration'] = 30*60
            person.day_plan.pop(0)

    def get_vehicles_position(self):
        self.vehicle_statuses = traci_helper.get_all_vehicles_statuses()
        vehicles_positions = []
        for vehicle_id in self.vehicle_statuses.keys():
            if self.vehicle_statuses[vehicle_id][86] != -1001:
                vehicle_position = traci_helper.get_vehicle_position(vehicle_id)
                vehicle_angle = traci_helper.get_vehicle_angle(vehicle_id)
                vehicle_speed = traci_helper.get_vehicle_speed(vehicle_id)
                if vehicle_position[0] != -1001 or vehicle_position[1] != -1001:
                    latlon_info = self.to_latlon(vehicle_position[0], vehicle_position[1])
                    vehicles_positions.append({"vehicle_id" : vehicle_id,
                                                'vehicle_angle': vehicle_angle,
                                                'speed': vehicle_speed,
                                                "x" : vehicle_position[0],
                                                "y" : vehicle_position[1],
                                                "lat" : latlon_info[0],
                                                "lon" : latlon_info[1],
                                                'current_edge_id': self.vehicle_statuses[vehicle_id][80],
                                                'current_edge_length_run': self.vehicle_statuses[vehicle_id][86]})
        '''if len(vehicles_positions) > 0:
            logger.error(str(traci_helper.get_simulate_time()) + '-' + str(self.simulating_time))
            logger.error(str(vehicles_positions))'''
        lock = threading.RLock()
        with lock:
            self.vehicles_positions = []
            for vehicle_position in vehicles_positions:
                self.vehicles_positions.append(vehicle_position)

        # stop vehicles near congested places:
        for congested_place in self.congested_places:
            suspected_vehicles = []
            for vehicle in self.vehicles_positions:
                if vehicle['vehicle_id'] not in congested_place['vehicles']:
                    distance = utility.measure_distance(vehicle['x'], vehicle['y'], congested_place['x'], congested_place['y'])
                    if distance <= config.DISTANCE_TO_STOP:
                        congested_place['vehicles'][vehicle['vehicle_id']] = {'id': vehicle['vehicle_id'], 'speed': vehicle['speed']}
                        self.traci_action_queue.append({'action': 'STOP_VEHICLE', 'parameter': {'vehicle_id': vehicle['vehicle_id']}})

    def control_people(self):

        conn = sqlite3.connect(config.DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        current_time = traci_helper.get_current_time()
        current_day = traci_helper.get_current_day()
        self.get_vehicles_position()

        if (config.MINUMUM_VEHICLES > 0):
            running_vehicles_count = len(self.vehicles_positions)
            if running_vehicles_count < config.MINUMUM_VEHICLES:
                sql = "select * from day_plans where type='MOVING' and route is not null ORDER BY RANDOM() limit " + str(config.MINUMUM_VEHICLES - running_vehicles_count)
                cur.execute(sql)
                actions = cur.fetchall()
                for row_day_plans in actions:
                    action_time = row_day_plans['time']
                    action = {'action_id': utility.generate_random_string(20),
                              'edges': row_day_plans['route'],
                              'time': current_time + 100,
                              'vehicle': 'default_car'}
                    try:
                        logger.info('add vehicle at ' + str(current_time) + ':' + json.dumps(action))
                        traci_helper.add_vehicle(action)
                    except:
                        pass


        for person in self.people:
            if (len(person.day_plan) == 0):
                #person.current_day += 1
                #self.generate_day_plan(person)
                #self.update_person(person, conn)

                #self.prepare_next_action(person, current_time)
                self.people.remove(person)
                print('remove person ' + person.id)
            elif person.day_plan[0]['type'] == 'MOVING':
                if person.day_plan[0]['edges'] is None:
                    person.day_plan[0]['duration'] = 30*60
                    person.day_plan[0]['finish_time'] = person.day_plan[0]['time'] + person.day_plan[0]['duration']
                    #self.save_current_action(person.day_plan[0], conn)
                    #remove the action
                    self.prepare_next_action(person, current_time)

                elif current_time > person.day_plan[0]['time']:
                    if person.day_plan[0]['action_id'] not in self.vehicle_statuses:
                        #update the action's finish time in template table
                        person.day_plan[0]['finish_time'] = current_time
                        person.day_plan[0]['duration'] = current_time - person.day_plan[0]['time']
                        #self.save_current_action(person.day_plan[0], conn)
                        #remove the action
                        self.prepare_next_action(person, current_time)
            else:
                #update finish time for current action in database
                person.day_plan[0]['finish_time'] = person.day_plan[0]['time'] + person.day_plan[0]['duration']
                #self.save_current_action(person.day_plan[0], conn)
                #remove the action
                self.prepare_next_action(person, current_time)

        remaining_people_count = len(self.people)
        if (remaining_people_count < config.TOTAL_PEOPLE):
            self.load_people(config.TOTAL_PEOPLE - remaining_people_count)
            logger.info('load people: ' + str(config.TOTAL_PEOPLE - remaining_people_count))
        conn.commit()
        conn.close()

    def add_congestion(self, lat, lng):
        (x, y) = self.from_latlon(float(lat), float(lng))
        congestion = {'id': utility.generate_random_string(20), 'x': x, 'y': y, 'lat': lat, 'lon': lng, 'vehicles': {}}

        lock = threading.RLock()
        with lock:
            self.congested_places.append(congestion)

        return congestion

    def remove_congestion(self, id):
        congestion_count = len(self.congested_places)
        for i in range(0, congestion_count):
            if self.congested_places[i]['id'] == id:
                #print(self.congested_places[i]['vehicles'])
                # release vehicles obstructed by congestion
                for vehicle in self.congested_places[i]['vehicles'].items():
                    self.traci_action_queue.append({'action': 'CHANGE_SPEED', 'parameter': {'vehicle_id': vehicle[1]['id'], 'speed': vehicle[1]['speed']}})

                # remove congestion from list
                lock = threading.RLock()
                with lock:
                    del self.congested_places[i]
                    return
                #return Response(json.dumps({'success': True, 'congestion_id': id}), 200, mimetype='application/json')

    def update_congestion(self, id, lat, lng):
        (x, y) = self.from_latlon(float(lat), float(lng))
        congestion_count = len(self.congested_places)
        for i in range(0, congestion_count):
            if self.congested_places[i]['id'] == id:
                congestion = self.congested_places[i]
                congested_vehicles = congestion['vehicles']
                # update current position
                congestion['x'] = x
                congestion['y'] = y
                congestion['lat'] = lat
                congestion['lon'] = lng
                congestion['vehicles'] = {}

                # set congested cars free
                for vehicle in congested_vehicles.items():
                    self.traci_action_queue.append({'action': 'CHANGE_SPEED', 'parameter': {'vehicle_id': vehicle[1]['id'], 'speed': vehicle[1]['speed']}})

                return

    def process_traci_action_queue(self):
        current_queue = None
        lock = threading.RLock()
        with lock:
            current_queue = self.traci_action_queue
            self.traci_action_queue = []
        for action in current_queue:
            logger.info(action['action'], json.dumps(action['parameter']))
            if action['action'] == 'CREATE_CONGESTION':
                traci_helper.add_congestion(action['parameter']['edge_id'], action['parameter']['position'])
            elif action['action'] == 'STOP_VEHICLE':
                traci_helper.set_vehicle_speed(action['parameter']['vehicle_id'], 0)
            elif action['action'] == 'CHANGE_SPEED':
                print(action)
                traci_helper.set_vehicle_speed(action['parameter']['vehicle_id'], action['parameter']['speed'])

    def run(self):
        #get soonest time to start the simulation
        conn = sqlite3.connect(self.database_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        get_soonest_action_query = "select * from day_plans where type='MOVING' and time!= -1 order by time asc limit 1"
        cur.execute(get_soonest_action_query)
        soonest_action = cur.fetchone()
        soonest_time = soonest_action['time']
        is_using_realtime = False

        conn.commit()
        conn.close()

        #create people controller and append people there
        '''for i in range(config.NUMBER_PEOPLE_CONTROLLERS):
            people_controller = PeopleController(self)
            self.people_controllers.append(people_controller)
        i = 0
        for person in self.people:
            self.people_controllers[i].add_person(person)
            i += 1
            if i >= config.NUMBER_PEOPLE_CONTROLLERS:
                i = 0'''

        # actually run the simulation
        if config.RUN_SUMO:
            current_dir = os.path.dirname(os.path.realpath('__file__'))
            sumo_command = config.SUMO_APP_DIR + ' --step-length ' +str(config.TIME_PER_STEP) + ' --begin ' + str(soonest_time-20) + ' --end ' + str(soonest_time-10)
            sumo_command += ' --configuration-file ' + current_dir + '/' + self.simulation_config_file
            sumo_command += ' --remote-port ' + str(self.sumo_port)
            p = Process(target=os.system, args=(sumo_command,))
            p.start()
            #wait 2 seconds to ensure traci is running
            time.sleep(2)

        # start SUMO controller and go to soonest action
        traci.init(self.sumo_port)

        #go to soonest step
        self.current_step = 0
        if (config.USE_REAL_TIME):
            current_time = datetime.datetime.now()
            current_time_in_second = current_time.hour * 3600 + current_time.minute * 60 + current_time.second

            traci.simulationStep((current_time_in_second - 4000) * 1000)
            self.current_step = current_time_in_second - 4000
            self.simulating_time = (current_time_in_second - 4000) * 1000

        elif soonest_time < config.TIME_START:
            traci.simulationStep((soonest_time-5)*1000)
            self.current_step = soonest_time-5
            self.simulating_time = (soonest_time-5)*1000
        else:
            traci.simulationStep((config.TIME_START-5)*1000)
            self.current_step = config.TIME_START-5
            self.simulating_time = (config.TIME_START-5)*1000

        '''
        Control people every 2 seconds
        In the mean time, keep accelerate
        '''
        duration = 10
        refresh_rate = config.REFRESH_RATE
        while (True):

            total_time = 0
            simulation_time = float(self.simulating_time)/1000
            while total_time < 20:
                if (config.USE_REAL_TIME):
                    if (not is_using_realtime):
                        current_time = datetime.datetime.now()
                        current_time_in_second = current_time.hour*3600 + current_time.minute*60 + current_time.second
                        if (self.simulating_time/1000 < current_time_in_second-3600):
                            refresh_rate = config.MAX_REFRESH_RATE
                        elif (self.simulating_time/1000 < current_time_in_second):
                            refresh_rate = (float)((current_time_in_second - (float)(self.simulating_time/1000))/3600/2)*config.MAX_REFRESH_RATE
                            if (refresh_rate > config.REFRESH_RATE and refresh_rate < 2*config.REFRESH_RATE):
                                refresh_rate = 2*config.REFRESH_RATE
                            elif (refresh_rate <= config.REFRESH_RATE):
                                refresh_rate = config.REFRESH_RATE
                                is_using_realtime = True
                        else:
                            refresh_rate = config.REFRESH_RATE
                            is_using_realtime = True

                start = time.time()
                #time.sleep(1/config.REFRESH_RATE)

                self.current_step += 1
                self.simulating_time += duration
                traci.simulationStep(self.simulating_time)

                self.process_traci_action_queue()

                self.control_people()
                end = time.time()
                duration = (end - start)*1000*refresh_rate
                total_time += duration
                #logger.error(str(duration))
                #print(duration, total_time)
                #time.sleep(float(duration)/float(1000))

        traci.close()

