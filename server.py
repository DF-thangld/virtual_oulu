import threading
import Pyro4
import json
import config
from traffic_manager import TrafficManager

@Pyro4.expose
class VirtualOuluServer(object):
    def __init__(self, traffic_manager=None):
        super(VirtualOuluServer, self).__init__()
        if traffic_manager is not None:
            self.traffic_manager = traffic_manager
        else:
            self.traffic_manager = TrafficManager()

        self.traffic_manager.start()

    def get_vehicles_positions(self):
        return {'time': self.traffic_manager.simulating_time,
                           'vehicles_positions': self.traffic_manager.vehicles_positions,
                           'congested_places': self.traffic_manager.congested_places}

    def delete_congestion(self, congestion_id):
        self.traffic_manager.remove_congestion(congestion_id)
        return True

    def add_congestion(self, lat, lgn):
        congestion = self.traffic_manager.add_congestion(lat, lgn)
        return congestion['id']

    def update_congestion(self, congestion_id, lat, lng):
        self.traffic_manager.update_congestion(congestion_id, lat, lng)
        return congestion_id

    def remove_vehicle(self, vehicle_id):
        self.traffic_manager.remove_vehicle(vehicle_id)
        return vehicle_id

if __name__ == '__main__':
    print('init server')
    server = VirtualOuluServer()
    print('start server')
    Pyro4.Daemon.serveSimple(
    {
        server: "virtual_oulu"
    },
    host=config.SERVER_HOST, port=config.SERVER_PORT,
    ns = False)
