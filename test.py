import os, sys, time
import sqlite3
from multiprocessing import Process
import config, utility, traci_helper

tools = os.path.join(os.getcwd(), 'sumo_tools')
sys.path.append(tools)
import traci as traci  # @UnresolvedImport

#run sumo
current_dir = os.path.dirname(os.path.realpath('__file__'))
sumo_command = config.SUMO_APP_DIR + ' --step-length 1 --begin 86380 --end 86395'
sumo_command += ' --configuration-file ' + current_dir + '/' + config.SIMULATION_CONFIG_FILE
sumo_command += ' --remote-port ' + str(config.SUMO_PORT)
print(sumo_command)
#p = Process(target=os.system, args=(sumo_command,))
#p.start()
#wait 2 seconds to ensure traci is running
time.sleep(2)

#init traci
current_time = 86390
traci.init(config.SUMO_PORT)

# get random 2 vehicles
conn = sqlite3.connect(config.DATABASE_FILE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
sql = "select * from day_plans where type='MOVING' and route is not null ORDER BY RANDOM() limit 2"
cur.execute(sql)
actions = cur.fetchall()
vehicles = []
for row_day_plans in actions:
    action_time = row_day_plans['time']
    action = {'action_id': utility.generate_random_string(20),
              'edges': row_day_plans['route'],
              'time': current_time + 1,
              'vehicle': 'default_car'}
    vehicles.append(action)

#ser time for each vehicle and run
vehicles[0]['time'] = current_time + 2
vehicles[1]['time'] = current_time + 20

#go to 23:59:50
print('finish init ' + str(traci_helper.get_simulate_time()))
traci.simulationStep(current_time)
print('at 86390')
traci_helper.add_vehicle(vehicles[0])
traci_helper.add_vehicle(vehicles[1])

print('now loop')
while True:
    print(str(current_time) + ' - ' + str(traci_helper.get_simulate_time()))
    current_time += 1
    traci.simulationStep(current_time*1000)
    time.sleep(0.5)
