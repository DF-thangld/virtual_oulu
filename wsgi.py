from main import app, traffic_manager

if __name__ == "__main__":
    traffic_manager.start()
    app.run()
