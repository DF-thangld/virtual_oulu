import config
import sqlite3

def create_connection():
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def close_connection(connection, commit=False):
    if commit:
        connection.commit()
    connection.close()
    
def run_command(sql_script, parameter=None, connection=None, commit=True):
    if parameter is None:
        parameter = ()
    conn = None
    if connection is None:
        conn = create_connection()
    else:
        conn = connection
    cur = conn.cursor()
    
    cur.execute(sql_script, parameter)
    
    if commit:
        conn.commit()

    if connection is None:
        close_connection(connection)

def commit(connection):
    connection.commit()

def roll_back(connection):
    pass

def query_one(sql_script, parameter=None, connection=None):
    conn = None
    if parameter is None:
        parameter = ()
    if connection is None:
        conn = create_connection()
    else:
        conn = connection
    cur = conn.cursor()
    
    cur.execute(sql_script, parameter)
    row = cur.fetchone()
    
    if connection is None:
        close_connection(connection)
    
    return row

def query_all(sql_script, parameter=None, connection=None):
    conn = None
    if parameter is None:
        parameter = ()
    if connection is None:
        conn = create_connection()
    else:
        conn = connection
    cur = conn.cursor()
    
    cur.execute(sql_script, parameter)
    row = cur.fetchall()
    
    if connection is None:
        close_connection(connection)
        
    return row