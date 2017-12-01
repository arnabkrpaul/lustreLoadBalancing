import networkx as nx
import random

class MinCostFlowOptimizer(object):
	def map_requests(self, requests, osts):
		totalDemand = sum([req.numStripes for req in requests])
		stripeSize = requests[0].stripeSize
		currStripeCount = requests[0].numStripes
		G = nx.DiGraph()
		G.add_node('source', demand=-totalDemand)
		G.add_node('sink', demand=totalDemand)
		doneFlag = False
		while not doneFlag and len(requests) > 0:
			for req in requests:
				G.add_edge('source', req.name, weight=0, capacity=req.numStripes)
				for ost in osts:
					G.add_edge(req.name, ost.name, weight=ost.cost_to_reach(), capacity=1)
			for ost in osts:
				G.add_edge(ost.name, 'sink', weight=ost.cost(), capacity=ost.capacity(stripeSize))
			try:
				flowCost, flowDict = nx.capacity_scaling(G)
				doneFlag = True
			except:
				requests = requests[:-1]
				doneFlag = False
		if doneFlag:
			ostWeights = flowDict['req0']
			ostNames = []
			for ost, weight in ostWeights.iteritems():
				if weight > 0:
					ostNames.append(ost)
			return tuple([ostNames, flowCost])
		else:
			ostNames = [ost.name for ost in random.sample(osts, currStripeCount)]
			return tuple([ostNames, 0])