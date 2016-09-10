import threading, os, sys, time, sqlite3
import config
tools = os.path.join(config.SUMO_DIR, 'tools')
sys.path.append(tools)
import traci  # @UnresolvedImport
import traci.constants as tc  # @UnresolvedImport

import traci_helper

class PeopleController(threading.Thread):
    def __init__(self, traffic_manager, people_list=None):
        super(PeopleController, self).__init__()
        if people_list is None:
            self.people_list = []
        else:
            self.people_list = people_list
        self.traffic_manager = traffic_manager
        
        self.ongoing_events = []
        self.upcoming_events = []
        
        for person in self.people_list:
            for action in person.day_plan:
                self.upcoming_events.append(action)
        self.upcoming_events.sort(key = lambda action: (action['sequence'], action['time']))
        
    def add_person(self, person):
        self.people_list.append(person)
        
    
        
    def run(self):
        '''
        If there is no more action then generate new one for the next day
        
        Check first action of each person every seconds:
            - If there is no action then generate new plan for that person for the next day
            - if action type is 'MOVING' then compare "current time" with action's starting time:
                + If current time < action time then do nothing
                + If current time >= action time then check status of the action:
                    o If status is not None then do nothing
                    o If status is None:
                        * Update finish_time of current action in database
                        * Update time for the next action
                        * Remove the action
            - If action type is not 'MOVING':
                + Remove the action
                + Update time for the next action
                + If the next action is 'MOVING' then add it to Traci
                + If the next action is 'MOVING' but the edges information is null then 
                        
        '''
        #open database
        conn = sqlite3.connect(config.DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        #init traci
        traci.init(config.SUMO_PORT)
        current_time = traci_helper.get_current_time()
        current_day = traci_helper.get_current_day()
        while True:
            for person in self.people_list:
                if (len(person.day_plan) == 0):
                    self.traffic_manager.generate_day_plan(person)
                    self.traffic_manager.update_person(person)
                elif person.day_plan[0]['type'] == 'MOVING' and person.day_plan[0]['duration'] == -1:
                    if current_time >= person.day_plan[0]['time']:
                        if traci_helper.get_vehicle_status(person.day_plan[0]['action_id']) is None:
                            #update the action's finish time in template table
                            update_query = 'update day_plans_template set finish_time=?, duration=? where action_id=?'
                            cur.execute(update_query, (current_time, current_time-person.day_plan[0]['time'], person.day_plan[0]['action_id']))
                            
                            #set the time for the next action as current time
                            if person.day_plan[1]['time'] == -1:
                                person.day_plan[1]['time'] = current_time
                            update_query = 'update day_plans_template set time=? where action_id=?'
                            cur.execute(update_query, (current_time, person.day_plan[1]['action_id']))
                            
                            #remove the action from the person's day plan
                            person.day_plan.pop(0)
                            #commit to database
                            conn.commit()
                else:
                    #update finish time for current action in database
                    update_query = 'update day_plans_template set finish_time=? where action_id=?'
                    cur.execute(update_query, (person.day_plan[0]['time'] + person.day_plan[0]['duration'], person.day_plan[0]['action_id']))
                    
                    #remove the action
                    person.day_plan.pop(0)
                    
                    #if the next action is moving then add the moving action to traci
                    if person.day_plan[0]['type'] == 'MOVING':
                        if person.day_plan[0]['edges'] is not None:
                            traci_helper.add_vehicle(person.day_plan[0])
                        else:
                            person.day_plan[0]['duration'] = 30*60
            time.sleep(5/config.REFRESH_RATE)
                        
        conn.close()    
        traci.close()