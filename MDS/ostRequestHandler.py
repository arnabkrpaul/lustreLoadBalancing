from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from urlparse import urlparse
from lustreLoadBalancer.mapper import RequestMapper
import json
import uuid

HOSTNAME = '127.0.0.1'
PORT = 8080
REQUEST_MAPPER = RequestMapper()

class HTTPRequestHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    global REQUEST_MAPPER
    query = urlparse(self.path).query
    queryComponents = dict(qc.split("=") for qc in query.split("&"))
    appID = uuid.UUID(int=int(queryComponents["app_id"]))
    writeSize = int(queryComponents["write_size"])
    stripeCount = int(queryComponents["stripe_count"])
    stripeSize = writeSize/stripeCount
    
    #ostNames, cost = REQUEST_MAPPER.get_osts_for_request(appID, stripeSize, stripeCount)
    ostNames = ["ost0", "ost1", "ost2", "ost3"]            # for testing
    
    self.send_response(200)
    self.send_header('Content-type','application/json')
    self.end_headers()
    self.wfile.write(json.dumps(ostNames))
  
def run():
  global HOSTNAME, PORT
  print('HTTP server is starting for handling OST requests...')
  address = (HOSTNAME, PORT)
  server = HTTPServer(address, HTTPRequestHandler)
  server.serve_forever()
  
if __name__ == '__main__':
  run()