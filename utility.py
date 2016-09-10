import sys
import numbers
import collections
import sqlite3
import xml.etree.ElementTree as ET
from math import sqrt, pow
import random
import string

def get_size(obj):
    # recursive function to dig out sizes of member objects:               
    def inner(obj, _seen_ids = set()):
        obj_id = id(obj)
        if obj_id in _seen_ids:
            return 0
        _seen_ids.add(obj_id)
        size = sys.getsizeof(obj)
        if isinstance(obj, (basestring, numbers.Number, xrange)):
            pass # bypass remaining control flow and return                
        elif isinstance(obj, (tuple, list, set, frozenset)):
            size += sum(inner(i) for i in obj)
        elif isinstance(obj, collections.Mapping) or hasattr(obj, 'iteritems'):
            size += sum(inner(k) + inner(v) for k, v in obj.iteritems())
        else:
            attr = getattr(obj, '__dict__', None)
            if attr is not None:
                size += inner(attr)
        return size
    return inner(obj)

def calculate_distance(x0, y0, x1, y1, x2, y2):
    '''
    Input: 3 point X(x0, y0), A(x1, y1), B(x2, y2)
    - Find the equation for the line go from A to B (d1)
    - Find the equation for the perpendicular line with d1 and go pass X (d2)
    - Find the intersection between 2 lines d1 and d2
    - If C inside AB => distance = |XC|
    - If C outside AB => distance = min(|XA|, |XB|)
    '''
    try:
    # if y1=y2
        if x1 == x2 and y1 == y2:
            distance = sqrt(pow(x1 - x0, 2) + pow(y1 - y0, 2))
            return distance
        elif x1 == x2 and y1 != y2:
            x3 = x1
            y3 = y0
        elif y1 == y2 and x1 != x2:
            x3 = x0
            y3 = y1
        else:
            # d1: y = a1x + b1
            a1 = (y1 - y2)/(x1 - x2)
            b1 = y2 - a1*x2
            
            # d2: y = a2x + b2
            a2 = -1/a1
            b2 = y0 - a2*x0
            
            # point C(x3, y3)
            x3 = (b2 - b1)/(a1 - a2)
            y3 = a1*x3 + b1
            
        # check if C is inside A and B
        if x3>=min(x1, x2) and x3<=max(x1, x2) and y3>=min(y1, y2) and y3<=max(y1, y2):
            distance = sqrt(pow(x3 - x0, 2) + pow(y3 - y0, 2))
        else:
            distance_to = sqrt(pow(x2 - x0, 2) + pow(y2 - y0, 2))
            distance_from = sqrt(pow(x1 - x0, 2) + pow(y1 - y0, 2))
            distance = min(distance_to,  distance_from)
        return distance
    except:
        print(x0, y0, x1, y1, x2, y2)
        return 99999999999999

def measure_distance(x1, y1, x2, y2):
    return sqrt(pow(x1 - x2, 2) + pow(y1 - y2, 2))

def get_middle_point(x1, y1, x2, y2, distance_from_x1_y1):
    x1 = float(x1)
    x2 = float(x2)
    y1 = float(y1)
    y2 = float(y2)
    
    if sqrt(pow(x1-x2, 2) + pow(y1-y2,2)) < distance_from_x1_y1:
        raise Exception('Expected distance must be smaller than distant between 2 points')
    
    x01 = 0
    y01 = 0
    x02 = 0
    y02 = 0
    x0 = 0
    y0 = 0
    d = distance_from_x1_y1
    # normal line y=ax+b
    if x1 != x2 and y1 != y2:
        a = (y1-y2)/(x1-x2)
        b = y2 - a*x2
        delta = 4*pow(x1+a*y1-a*b, 2) - 4*(pow(a, 2)+1)*(pow(x1,2)+pow(b-y1,2)-pow(d,2))
        x01 = (2*(x1+a*y1-a*b)+sqrt(delta))/(2*(pow(a,2)+1))
        y01 = a*x01 + b
        x02 = (2*(x1+a*y1-a*b)-sqrt(delta))/(2*(pow(a,2)+1))
        y02 = a*x02 + b
    # special line x = x1    
    elif x1 == x2 and y1 != y2:
        x01 = x1
        y01 = d+y1
        x02 = x1
        y02 = -1*(d+y1)
    # special line y = y1
    elif x1 != x2 and y1 == y2:
        x01 = d+x1
        y01 = y1
        x02 = -1*(d+x1)
        y02 = y1
    
    # get the correct point (in the middle of the line)
    if min(x1,x2) < x01 < max(x1,x2) and min(y1,y2) < y01 < max(y1,y2):
        x0 = x01
        y0 = y01
    else:
        x0 = x02
        y0 = y02
    
    return (x0, y0)

def generate_random_string(length):
    random_string = ''
    for i in range(0,length):
        random_string = random_string + random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits)
    return random_string

def check_going_through(x1, y1, x2, y2, x0, y0, size_to_check):
    
    return True