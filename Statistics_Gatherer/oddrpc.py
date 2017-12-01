from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler


def ost_list(fsname=None):
    pass

def ost_ranks(top=None):
    pass



class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2', )

# Create server

def main(host='localhost', port=8889)
    server = SimpleXMLRPCServer(
        (host, port), requestHandler=RequestHandler)

    server.register_introspection_functions()

    # register functions

    server.register_function(ost_list)
    server.register_function(ost_ranks)

    # run the server

    server.serve_forever()






