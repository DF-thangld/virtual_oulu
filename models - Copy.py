from web_interface import db


class CarType(db.Model):
    __tablename__ = 'car_types'
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100))
    accel = db.Column(db.Float)
    decel = db.Column(db.Float)
    sigma = db.Column(db.Float)
    length = db.Column(db.Float)
    min_gap = db.Column('minGap', db.Float)
    max_speed = db.Column('maxSpeed', db.Float)
    model_file = db.Column(db.String(100))
    description = db.Column(db.String(500))


class FirstName(db.Model):
    __tablename__ = 'first_names'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    from_value = db.Column(db.Integer)
    to_value = db.Column(db.Integer)
    gender = db.Column(db.String(10))

class LastName(db.Model):
    __tablename__ = 'last_names'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    from_value = db.Column(db.Integer)
    to_value = db.Column(db.Integer)


class DayPlan(db.Model):
    __tablename__ = 'day_plans'
    id = db.Column(db.String(100), primary_key=True)
    sequence = db.Column(db.Integer)
    type = db.Column(db.String(50))
    from_place_id = db.Column(db.Integer)
    from_edge_id = db.Column(db.String(50))
    to_place_id = db.Column(db.Integer)
    to_edge_id = db.Column(db.String(50))
    duration = db.Column(db.Integer, default=-1)
    time = db.Column(db.Integer, default=-1)
    person_id = db.Column(db.String(100))
    route = db.Column(db.String(100))
    finish_time = db.Column(db.Integer, default=-1)
    
class Person(db.Model):
    __tablename__ = 'people'
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    home_edge_id = db.Column(db.String(100))
    work_place_id = db.Column(db.Integer)
    university_id = db.Column(db.Integer)
    working_status = db.Column(db.String(100))
    vehicle_id = db.Column(db.String(100))
    
class Place(db.Model):
    __tablename__ = 'places'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    address = db.Column(db.String(100))
    lat = db.Column(db.String(10))
    lon = db.Column(db.String(100))
    type = db.Column(db.String(20))
    main_type = db.Column(db.String(20))
    edge_id = db.Column(db.String(100))
    x = db.Column(db.String(100))
    y = db.Column(db.String(100))