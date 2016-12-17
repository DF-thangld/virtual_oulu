from traffic_manager import TrafficManager
import config
traffic_manager = TrafficManager()

traffic_manager.generate_new_data(config.PEOPLE_COUNT)
