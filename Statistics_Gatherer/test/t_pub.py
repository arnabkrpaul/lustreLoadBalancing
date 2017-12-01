import zmq
from zmq.eventloop import ioloop, zmqstream
import sys


def save_msg(m):
    print m

hosts=["lu1", "lu2"]

context = zmq.Context()
for host in hosts:
    socket_sub = context.socket(zmq.SUB)
    socket_sub.setsockopt(zmq.SUBSCRIBE, "")
    pub_endpoint= "tcp://%s:%s" % (host, 8888)
    try:
        socket_sub.connect(pub_endpoint)
        stream_sub = zmqstream.ZMQStream(socket_sub)
        stream_sub.on_recv(save_msg)
        print "Connected to", pub_endpoint
    except:
        print "Failed to connect: ", pub_endpoint
        sys.exit(1)

ioloop.IOLoop.instance().start()

