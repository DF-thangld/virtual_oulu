import logging
logger = logging.getLogger('myapp')
hdlr = logging.FileHandler('myapp_1.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr) 
logger.setLevel(logging.INFO)