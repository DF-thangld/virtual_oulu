import xml.etree.ElementTree as ET
import sqlite3
from math import pow, sqrt
import math

import config
import traffic_manager
import database
import utility

def import_nodes():
    print('import_nodes')
    tm = traffic_manager.TrafficManager()
    
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('delete from oulu_nodes')
    cur.execute('vacuum')
    conn.commit()
    
    tree = ET.parse('data/plain_network/oulu.nod.xml')
    root = tree.getroot()
    count = 0
    for node in root.iter('node'):
        node_id = node.get('id')
        node_x = float(node.get('x'))
        node_y = float(node.get('y'))
        node_type = node.get('type')
        (lat, lon) = tm.to_latlon(node_x, node_y)
        cur.execute('insert into oulu_nodes (id, x, y, lat, lon, type) values (?, ?, ?, ?, ?, ?)', 
                    (node_id, node_x, node_y, lat, lon, node_type))
        conn.commit()
        count += 1
        if count%1000 == 0:
            print(count)
    
    
    conn.commit()
    conn.close()
    print('finish import_nodes')

def import_lanes():
    print('import_lanes')
    tm = traffic_manager.TrafficManager()
    
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('delete from oulu_edges')
    cur.execute('vacuum')
    conn.commit()
    
    
    tree = ET.parse('data/plain_network/oulu.edg.xml')
    root = tree.getroot()
    count = 0
    for edge in root.iter('edge'):
        edge_id = edge.get('id')
        edge_from = edge.get('from')
        edge_to = edge.get('to')
        edge_priority = edge.get('priority')
        edge_type = edge.get('type')
        edge_numLanes = int(edge.get('numLanes'))
        edge_speed = float(edge.get('speed'))
        edge_shape = edge.get('shape')
        edge_shape_lat_lon = ''
        if edge_shape is not None:
            coordinates = edge_shape.split(' ');
            for coordinate in coordinates:
                coordinate_x_y = coordinate.split(',')
                coordinate_lat_lon = tm.to_latlon(float(coordinate_x_y[0]), float(coordinate_x_y[1]))
                edge_shape_lat_lon += str(coordinate_lat_lon[0]) + ',' + str(coordinate_lat_lon[1]) + ' '
             
        cur.execute('insert into oulu_edges (id, `from`, `to`, priority, type, numLanes, speed, shape, shape_x_y) values (?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                    (edge_id, edge_from, edge_to, edge_priority, edge_type, edge_numLanes, edge_speed, edge_shape_lat_lon.strip(), edge_shape))
        conn.commit()
        count += 1
        if count%1000 == 0:
            print(count)
    
    conn.commit()
    conn.close()
    print('finish import_lanes')


def split_line(from_x, from_y, to_x, to_y, max_distance):
    from_x = float(from_x)
    from_y = float(from_y)
    to_x = float(to_x)
    to_y = float(to_y)
    max_distance = float(max_distance)
    result = []
    result.append((from_x, from_y))
    
    line_distance = sqrt(pow(from_x-to_x, 2) + pow(from_y-to_y,2))
    split_time = math.ceil(line_distance/max_distance)
    splitted_distance = line_distance/split_time
    for i in range(1,int(split_time)):
        result.append(utility.get_middle_point(from_x, from_y, to_x, to_y, i*splitted_distance))
    
    result.append((to_x, to_y))
    return result

def create_edges_full_data_table():
    print('create_edges_full_data_table')
    connection = database.create_connection()
    
    database.run_command('delete from edges_full_data', None, connection, True)
    database.run_command('vacuum', None, connection, True)
    
    sql_query = 'select a.id, a.shape_x_y, b.x from_x, b.y from_y, c.x to_x, c.y to_y \
                from oulu_edges a \
                inner join oulu_nodes b on a.`from` = b.id \
                inner join oulu_nodes c on a.`to` = c.id'
    count = 0
    edges = database.query_all(sql_query, None, connection)
    for edge in edges:
        sequence = 1
        if edge['shape_x_y'] is None:
            
            distance = utility.measure_distance(edge['from_x'], edge['from_y'], edge['to_x'], edge['to_y'])
            if distance <= config.MAX_DISTANCE:
                sql_script = '    insert into "edges_full_data" ("edge_id", "sequence", "from_x", "from_y", "to_x", "to_y", "distance") \
                                values (?, ?, ?, ?, ?, ?, ?)'
                parameter = (edge['id'], sequence, edge['from_x'], edge['from_y'], edge['to_x'], edge['to_y'], distance)
                database.run_command(sql_script, parameter, connection, True)
                sequence += 1
            else:
                splited_dots = split_line(edge['from_x'], edge['from_y'], edge['to_x'], edge['to_y'], config.MAX_DISTANCE)
                for i in range(len(splited_dots)-1):
                    splited_distance = utility.measure_distance(splited_dots[i][0], splited_dots[i][1], splited_dots[i+1][0], splited_dots[i+1][1])
                    sql_script = '    insert into "edges_full_data" ("edge_id", "sequence", "from_x", "from_y", "to_x", "to_y", "distance") \
                                values (?, ?, ?, ?, ?, ?, ?)'
                    parameter = (edge['id'], sequence, splited_dots[i][0], splited_dots[i][1], splited_dots[i+1][0], splited_dots[i+1][1], splited_distance)
                    database.run_command(sql_script, parameter, connection, False)
                    sequence += 1
                database.commit(connection)
        else:
            lines = edge['shape_x_y'].split(' ')
            for i in range(len(lines)-1):
                coord_from = lines[i].split(',')
                coord_to = lines[i+1].split(',')
                distance = sqrt(pow(float(coord_from[0]) - float(coord_to[0]), 2) + pow(float(coord_from[1]) - float(coord_to[1]), 2))
                if distance <= config.MAX_DISTANCE:
                    sql_script = '    insert into "edges_full_data" ("edge_id", "sequence", "from_x", "from_y", "to_x", "to_y", "distance") \
                            values (?, ?, ?, ?, ?, ?, ?)'
                    
                    parameter = (edge['id'], sequence, coord_from[0], coord_from[1], coord_to[0], coord_to[1], distance)
                    database.run_command(sql_script, parameter, connection, False)
                    sequence += 1
                else:
                    splited_dots = split_line(coord_from[0], coord_from[1], coord_to[0], coord_to[1], config.MAX_DISTANCE)
                    for j in range(len(splited_dots)-1):
                        splited_distance = utility.measure_distance(splited_dots[j][0], splited_dots[j][1], splited_dots[j+1][0], splited_dots[j+1][1])
                        sql_script = '    insert into "edges_full_data" ("edge_id", "sequence", "from_x", "from_y", "to_x", "to_y", "distance") \
                                    values (?, ?, ?, ?, ?, ?, ?)'
                        parameter = (edge['id'], sequence, splited_dots[j][0], splited_dots[j][1], splited_dots[j+1][0], splited_dots[j+1][1], splited_distance)
                        database.run_command(sql_script, parameter, connection, False)
                        sequence += 1
                    
            database.commit(connection)
        count += 1
        if count%1000 == 0:
            print(count)
    
    database.close_connection(connection, True)
    print('finish create_edges_full_data_table')

#import_nodes()
#import_lanes()
create_edges_full_data_table()

#print(split_line(13859.28, 0, 14110.65, 1535.92, 5))
