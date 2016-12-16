import threading, os, sys, time
import config
import utility
tools = os.path.join(os.getcwd(), 'sumo_tools')
sys.path.append(tools)
import logging
import traci as traci  # @UnresolvedImport
import traci.constants as tc  # @UnresolvedImport
import traci.route # @UnresolvedImport
import traci.vehicle # @UnresolvedImport

def add_route(route_id, edges_text):
    '''
    Add a route to sumo simulation
    Input:
        Route_id: the id of the route
        edges_text: edges of the route in text format ('edge_1 edge_2 edge_3')
    '''
    edges = edges_text.split(' ')
    traci.route.add(route_id, edges)

def add_vehicle(action, route_added=False):
    '''
    Add a vehicle to sumo simulation
    The vehicle can be and should be added before its actual start time
    Pre-condition: the route must be added before adding vehicle
    '''
    if not route_added:
        add_route(action['action_id'], action['edges'])

    #action['time'] *= 1000
    if 'departPos' not in action:
        traci.vehicle.addFull(action['action_id'], action['action_id'], typeID=action['vehicle'], depart=str(action['time']))
    else:
        traci.vehicle.addFull(action['action_id'], action['action_id'], typeID=action['vehicle'], depart=str(action['time']), departPos=str(action['departPos']))

    traci.vehicle.subscribe(action['action_id'], (tc.VAR_ROAD_ID, tc.VAR_LANEPOSITION))

    
def add_congestion(edge_id, position):
    id = 'BLOCKED_' + utility.generate_random_string(20)
    add_route(id, edge_id)
    
    traci.vehicle.addFull(id, id, typeID='congestion_thing', departPos=str(position))
    traci.vehicle.subscribe(id, (tc.VAR_ROAD_ID, tc.VAR_LANEPOSITION))
    
def get_current_time():
    second_in_a_day = 86400
    current_time_of_day = (traci.simulation.getCurrentTime()/1000)%second_in_a_day
    return current_time_of_day

def get_simulate_time():
    return traci.simulation.getCurrentTime()

def get_current_day():
    second_in_a_day = 86400
    current_day = (traci.simulation.getCurrentTime()/1000)/second_in_a_day
    return current_day
    
def get_vehicle_status(vehicle_id):
    return traci.vehicle.getSubscriptionResults(vehicle_id)

def get_all_vehicles_statuses():
    return traci.vehicle.getSubscriptionResults()

def get_vehicle_position(vehicle_id):
    try:
        return traci.vehicle.getPosition(vehicle_id)
    except:
        return (-1001, -1001)
    
def get_vehicle_angle(vehicle_id):
    return traci.vehicle.getAngle(vehicle_id)

def get_vehicle_speed(vehicle_id):
    return traci.vehicle.getSpeed(vehicle_id)
        
def set_vehicle_speed(vehicle_id, speed):
    try:
        traci.vehicle.setSpeed(vehicle_id, speed)
    except:
        pass

def stop(vehicle_id, edge_id):
    traci.vehicle.slowDown(vehicle_id, 0.0, 1)
