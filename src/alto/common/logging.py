import logging
import sys

def fail_with_msg(level, msg):
    logging.log(level, msg)
    sys.exit(-1)
