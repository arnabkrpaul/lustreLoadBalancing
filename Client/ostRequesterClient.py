import urllib
import httplib
import uuid

SERVER_HOSTNAME = '127.0.0.1'
SERVER_PORT = 8080
TIMEOUT = 10

class OSTRequester(object):
	def __init__(self):
		self.appID = uuid.uuid4()

	def request(self, writeSize, stripeCount):
		conn = httplib.HTTPConnection(SERVER_HOSTNAME, SERVER_PORT, timeout=TIMEOUT)
		params = {"app_id": str(self.appID.int), "write_size": str(writeSize), "stripe_count": str(stripeCount)}
		conn.request("GET", "/request?{0}".format(urllib.urlencode(params)))
		response = conn.getresponse()
		data = response.read()
		print data
		conn.close()
