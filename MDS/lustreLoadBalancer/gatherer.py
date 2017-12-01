from lustre_utils import LustreModel

NUM_OF_OSS = 32
NUM_OF_OST_PER_OSS = 7
DISK_SPACE_PER_OST = 4294967296		# 4 GB

class LustreStatsGatherer(object):
	def __init__(self, numOSS, numOSTPerOSS, ostDiskSpace):
		self.model = LustreModel(numOSS, numOSTPerOSS, ostDiskSpace)

class SimStatsGatherer(LustreStatsGatherer):
	def __init__(self, lustreSim):
		self.simulator = lustreSim
		super(SimStatsGatherer, self).__init__(lustreSim.numLnetRtr*lustreSim.numOSSPerRtr, lustreSim.numOSTPerOSS, lustreSim.ostDiskSpace)

	def gather_and_update(self):
		#ostUsedSpaceList = []
		for simLnetRtr in self.simulator.lnetRtrList:
			for simOSS in simLnetRtr.ossList:
				modelOSS = self.model.ossDict[simOSS.name]
				ossCPUUsage = float(simOSS.cpuPercent)/100
				lnetLoad = float(simOSS.lnetRtr.load)/100
				modelOSS.update_stats(ossCPUUsage, lnetLoad)
				for simOST in simOSS.ostList:
					modelOST = self.model.ostDict[simOST.name]
					modelOST.update_stats(simOST.usedDiskSpace)
		#			ostUsedSpaceList.append(simOST.usedDiskSpace)
		#print ostUsedSpaceList

class RealStatsGatherer(LustreStatsGatherer):
	def __init__(self):
		super(RealStatsGatherer, self).__init__(NUM_OF_OSS, NUM_OF_OST_PER_OSS, DISK_SPACE_PER_OST)

	def gather_and_update(self):
		"""Oddmon integration"""
		pass