COST_RESOLUTION = 1000000000

class LustreModel(object):
	def __init__(self, numOSS, numOSTPerOSS, ostDiskSpace):
		self.numOSS = numOSS
		self.numOSTPerOSS = numOSTPerOSS
		self.ossDict = {}
		self.ostDict = {}
		for i in range(numOSS):
			ossName = "oss{0}".format(i)
			oss = OSS(ossName, numOSTPerOSS)
			self.ossDict[ossName] = oss
			for j in range(numOSTPerOSS):
				ostName = "ost{0}".format(i*numOSTPerOSS+j)
				ost = OST(ostName, ostDiskSpace, oss)
				self.ostDict[ostName] = ost
				oss.ostList.append(ost)

	def update_stats(self, newStats):
		pass

class OSS(object):
	def __init__(self, name, numOST):
		self.name = name
		self.numOST = numOST
		self.cpuUsage = 0
		self.lnetLoad = 0
		self.cpuWeight = 0.5
		self.memWeight = 0.5
		self.ostList = []

	def mem_used(self):
		usedSpace = sum([ost.usedDiskSpace for ost in self.ostList])
		totalSpace = self.ostList[0].totalDiskSpace * self.numOST
		return float(usedSpace)/totalSpace

	def cost_to_reach(self):
		return int(self.lnetLoad * COST_RESOLUTION)

	def load(self):
		return int((self.cpuWeight*self.cpuUsage + self.memWeight*self.mem_used())*COST_RESOLUTION)

	def update_stats(self, cpuUsage, lnetLoad):
		self.cpuUsage = cpuUsage
		self.lnetLoad = lnetLoad

class OST(object):
	def __init__(self, name, totalDiskSpace, parentOSS):
		self.name = name
		self.totalDiskSpace = totalDiskSpace
		self.usedDiskSpace = 0
		self.oss = parentOSS

	def cost_to_reach(self):
		return self.oss.cost_to_reach() + self.oss.load()

	def capacity(self, stripeSize):
		return int(self.totalDiskSpace - self.usedDiskSpace)/stripeSize

	def cost(self):
		return int(float(self.usedDiskSpace*COST_RESOLUTION)/self.totalDiskSpace)

	def update_stats(self, usedDiskSpace):
		self.usedDiskSpace = usedDiskSpace