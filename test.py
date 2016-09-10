from models import CarType
cars = CarType.query.all()
print(cars)