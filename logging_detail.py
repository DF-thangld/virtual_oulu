import logging
import os

def get_logger(log_id, file, append_file=False):

    if not append_file:
        try:
            os.remove(file)
        except OSError:
            pass

    logger = logging.getLogger(log_id)
    hdlr = logging.FileHandler(file)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.INFO)
    return logger
