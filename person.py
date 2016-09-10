class Person():
	STATUS_WORKING = 'WORKING'
	STATUS_STUDYING = 'STUDYING'
	STATUS_STAY_AT_HOME = 'STAY_AT HOME'
	TRANSPORT_AVAILABILITY_ALWAYS = 'ALWAYS' 
	TRANSPORT_AVAILABILITY_NONE = 'NONE'
	GENDER_MALE = 'M'
	GENDER_FEMALE = 'F'
	
	def __init__(self):
		self.id = ''
		self.name = ''
		self.age = 0
		self.gender = ''
		self.car_available = '' # not using now, assuming everyone use cars
		self.bicycle_available = '' # not using now, assuming everyone use cars
		self.daily_routine = []
		self.home_address = {'edge_id': ''} # edge_id, address, lat, lon
		self.work_address = {'id': 0} # id, name, address, lat, lon
		self.school_address = {'id': 0} # id, name, address, lat, lon
		self.working_status = ''
		self.day_plan = []
		self.vehicle = ''
		self.current_day = 0
		
