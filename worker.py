from traffic_management_1 import TrafficManagement
import sqlite3
import threading
import xml.etree.ElementTree as ET
import os
import random
import string
from datetime import datetime

import shutil
from multiprocessing import Process

class TrafficManagementHelper(threading.Thread):
    def __init__(self):
        super(TrafficManagementHelper, self).__init__()
        self.id = ''
        for i in range(0,20):
            self.id = self.id + random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits)
        
        
        os.makedirs('tmp/' + self.id)
        shutil.copy2(TrafficManagement.NETWORK_FILE, 'tmp/' + self.id)
        shutil.copy2(TrafficManagement.NETWORK_NODE_FILE, 'tmp/' + self.id)
        
        self.traffic_manager = TrafficManagement(TrafficManagement.DATABASE_FILE, 'tmp/' + self.id + '/oulu.edg.xml', 'tmp/' + self.id + '/oulu.nod.xml')

    def run(self):
        self.update_nearest_edge()
    
    def update_nearest_edge(self):
        conn = sqlite3.connect(TrafficManagement.DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        while True:
            fetch_one_place = "SELECT * FROM places where is_coord_get = 1 and edge_id is null ORDER BY RANDOM() LIMIT 1;"
            
            cur.execute(fetch_one_place)
            row = cur.fetchone()
            
            update_place = "update places set is_coord_get=4 where id=?"
            cur.execute(update_place, (row['id'],))
            conn.commit()
            
            if (row is not None):
                print(row['main_type'], row['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                nearest_edge = self.traffic_manager.find_nearest_edge(float(row['x']), float(row['y']))
            else:
                break
            
            update_place = 'update places set edge_id=?, is_coord_get=1 where id=?'
            cur.execute(update_place, (nearest_edge.attrib['id'], row['id']))
            conn.commit()
        
        conn.close()
        shutil.rmtree('tmp/' + self.id) 

def parallel_function():
    process = TrafficManagementHelper()
    process.update_nearest_edge()

if __name__ == '__main__':
    for i in range(0, 3):
        p = Process(target=parallel_function)
        p.start()