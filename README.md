Contributors: Arnab Kumar Paul, Arpit Goyal, Sangeetha B. Srinivasa

# ORNLProjectLustre

Requirements: Python 2.7, NetworkX python library, NS3 python bindings (for simulator)

Client: OST Requester module (ostRequesterClient.py) handles the requests consisting of application id, size of write request, number of stripes. These requests are sent to MDS via HTTP GET Requests.

MDS: ostRequestHandler.py receives the requests from the client, performs mapping and returns the set of OSTs to the client. ostRequestHandler.py interacts with the lustreLoadBalancer package on MDS. 

	lustreLoadBalancer package:
		predictor.py: Uses Markov Chain Model to predict future requests.

		gatherer.py: Uses "oddmon" package to collect statistics from MDS, OSS and OSTs. Returns these statistics to lustreLoadBalancer package on MDS.

		optimizer.py: Uses min-cost max-flow algorithm to map requests to OSTs based on the statistics to get load balanced setup.

		mapper.py: Returns the mapping of requests to OSTs back to ostRequestHandler.py, which returns it back to the client.

		lustre_utils.py: Used to define the OSS and OST configuration for Lustre.

		*For running simulation, open a NS3 shell, and run lustreSimulator.py.

*AppLog2.txt: Sample requests for HACC I/O

ODDMON package (inside Statistics Gatherer): Modified the already existing ORNL oddmon package to collect statistics.
	
	oddpub.py: Deployed on OSS to publish the OSS and OST statistics defined in metric_plugins to MDS via RabbitMQ.

	oddsub.py: Deployed on MDS to collect statistics from OSS and also from MDS as defined in metric_plugins.

	These statistics are given to the lustreLoadBalancer package (gatherer.py).
	
