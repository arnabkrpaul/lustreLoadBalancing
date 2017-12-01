import zmq
from zmq.eventloop import zmqstream, ioloop
import socket
import time


hostname = socket.gethostname()
context = zmq.Context()
pub = context.socket(zmq.PUB)
pub.bind("tcp://*:8888")

seq = 1
while True:
    msg = "%s -> %s" % (hostname, seq)
    pub.send_string(msg)
    print msg
    seq += 1
    time.sleep(5)



