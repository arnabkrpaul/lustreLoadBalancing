import ns.core
import ns.network
import ns.internet
import ns.point_to_point
from lustreLoadBalancer.mapper import RequestMapper, RoundRobinRequestMapper, RandomRequestMapper

NUM_OF_IO_RTR = 1
NUM_OF_LNET_RTR = 4
NUM_OF_OSS_PER_RTR = 8
NUM_OF_OST_PER_OSS = 7
DISK_SPACE_PER_OST = 104857600		# 100 kB
P2P_LINK_DATA_RATE = "5Mbps"
P2P_LINK_DELAY = "2ms"
OUTPUT_PERIOD = 0.001
PRINT_PERIOD = 1.0

class LustreSimulator:
	def __init__(self):
		self.numIORtr = NUM_OF_IO_RTR
		self.numLnetRtr = NUM_OF_LNET_RTR
		self.numOSSPerRtr = NUM_OF_OSS_PER_RTR
		self.numOSTPerOSS = NUM_OF_OST_PER_OSS
		self.ostDiskSpace = DISK_SPACE_PER_OST
		self.ioRtrList = []
		self.lnetRtrList = []
		self.ostDict = {}
		self.ostOutputFile = "OST_SIM_STATS_FIN_MINCOST-3_FULL.csv"
		self.requestMapper = RequestMapper(self)
		#self.requestMapper = RoundRobinRequestMapper(self)
		#self.requestMapper = RandomRequestMapper(self)
		self._build_network_topology()

	def _build_network_topology(self):
		stack = ns.internet.InternetStackHelper()
		for i in range(self.numIORtr):
			ioRtr = IORouter(i, stack)
			self.ioRtrList.append(ioRtr)
		for i in range(self.numLnetRtr):
			lnetRtr = LnetRouter(i, stack, self.numOSSPerRtr)
			for j in range(self.numOSSPerRtr):
				oss = OSS(i*self.numOSSPerRtr + j, stack, self.numOSTPerOSS, lnetRtr)
				for k in range(self.numOSTPerOSS):
					ost = OST(i*self.numOSSPerRtr*self.numOSTPerOSS + j*self.numOSTPerOSS + k, stack, self.ostDiskSpace, oss)
					oss.ostList.append(ost)
					self.ostDict[ost.name] = ost
				lnetRtr.ossList.append(oss)
			self.lnetRtrList.append(lnetRtr)

		p2p = ns.point_to_point.PointToPointHelper()
		p2p.SetDeviceAttribute("DataRate", ns.core.StringValue(P2P_LINK_DATA_RATE))
		p2p.SetChannelAttribute("Delay", ns.core.StringValue(P2P_LINK_DELAY))

		for i, ioRtr in enumerate(self.ioRtrList):
			for j, lnetRtr in enumerate(self.lnetRtrList):
				nodes = ns.network.NodeContainer(ioRtr.node)
				nodes.Add(lnetRtr.node)
				devices = p2p.Install(nodes)
				baseAddrStr = "10.1.{0}.0".format(i*self.numLnetRtr + j)
				address = ns.internet.Ipv4AddressHelper()
				address.SetBase(ns.network.Ipv4Address(baseAddrStr), ns.network.Ipv4Mask("255.255.255.0"))
				interfaces = address.Assign(devices)
				ioRtr.create_socket(interfaces.GetAddress(0))
				lnetRtr.update_device(devices.Get(1))
		for i, lnetRtr in enumerate(self.lnetRtrList):
			for j, oss in enumerate(lnetRtr.ossList):
				nodes = ns.network.NodeContainer(lnetRtr.node)
				nodes.Add(oss.node)
				devices = p2p.Install(nodes)
				baseAddrStr = "10.1.{0}.0".format(self.numIORtr*self.numLnetRtr + i*self.numOSSPerRtr + j)
				address = ns.internet.Ipv4AddressHelper()
				address.SetBase(ns.network.Ipv4Address(baseAddrStr), ns.network.Ipv4Mask("255.255.255.240"))
				interfaces = address.Assign(devices)
				oss.update_device(devices.Get(1))
				for k, ost in enumerate(oss.ostList):
					nodes = ns.network.NodeContainer(oss.node)
					nodes.Add(ost.node)
					devices = p2p.Install(nodes)
					baseAddrStr = "10.1.{0}.{1}".format(self.numIORtr*self.numLnetRtr + i*self.numOSSPerRtr + j, (k+1)<<4)
					address = ns.internet.Ipv4AddressHelper()
					address.SetBase(ns.network.Ipv4Address(baseAddrStr), ns.network.Ipv4Mask("255.255.255.240"))
					interfaces = address.Assign(devices)
					ost.update_device(devices.Get(1))
					ost.create_socket(interfaces.GetAddress(1))
		ns.internet.Ipv4GlobalRoutingHelper.PopulateRoutingTables()

	def _schedule_app_events(self, app):
		def event_handler(writeSize, stripeCount):
			stripeSize = writeSize/stripeCount
			ostNameList, flowCost = self.requestMapper.get_osts_for_request(app.id, stripeSize, stripeCount)
			for ostName in ostNameList:
				ost = self.ostDict[ostName]
				app.ioRtr.write_to_ost(stripeSize, ost)

		for event in app.eventList:
			ns.core.Simulator.Schedule(ns.core.Seconds(event.time), event_handler, event.size, event.stripeCount)

	def _schedule_output_events(self):
		def event_handler():
			"""
			tolerance = 0.000001
			ostUsedSpaceList = []
			ossCpuPercent = []
			lnetLoad = [lnetRtr.load for lnetRtr in self.lnetRtrList]
			for lnetRtr in self.lnetRtrList:
				ossCpuPercent += [oss.cpuPercent for oss in lnetRtr.ossList]
				for oss in lnetRtr.ossList:
					ostUsedSpaceList += [ost.usedDiskSpace for ost in oss.ostList]
			meanOSTLoad = float(sum(ostUsedSpaceList))/len(ostUsedSpaceList)
			maxOSTLoad = float(max(ostUsedSpaceList))
			if meanOSTLoad < tolerance and maxOSTLoad < tolerance:
				ostLoadMeasure = 1.0
			elif meanOSTLoad < tolerance:
				ostLoadMeasure = maxOSTLoad/tolerance
			else:
				ostLoadMeasure = maxOSTLoad/meanOSTLoad
			meanOSSLoad = float(sum(ossCpuPercent))/len(ossCpuPercent)
			maxOSSLoad = float(max(ossCpuPercent))
			if meanOSSLoad < tolerance and maxOSSLoad < tolerance:
				ossLoadMeasure = 1.0
			elif meanOSSLoad < tolerance:
				ossLoadMeasure = maxOSSLoad/tolerance
			else:
				ossLoadMeasure = maxOSSLoad/meanOSSLoad
			meanLnetLoad = float(sum(lnetLoad))/len(lnetLoad)
			maxLnetLoad = float(max(lnetLoad))
			if meanLnetLoad < tolerance and maxLnetLoad < tolerance:
				lnetLoadMeasure = 1.0
			elif meanLnetLoad < tolerance:
				lnetLoadMeasure = maxLnetLoad/0.001
			else:
				lnetLoadMeasure = maxLnetLoad/meanLnetLoad
			ostOutputLine = ','.join(map(str, [ostLoadMeasure, ossLoadMeasure, lnetLoadMeasure]))
			"""
			ostUsedSpaceList = []
			for lnetRtr in self.lnetRtrList:
				for oss in lnetRtr.ossList:
					ostUsedSpaceList += [ost.usedDiskSpace for ost in oss.ostList]
			ostOutputLine = ','.join(map(str, ostUsedSpaceList))
			write_output_to_file(ostOutputLine)
			ns.core.Simulator.Schedule(ns.core.Seconds(OUTPUT_PERIOD), event_handler)

		def print_event_handler():
			#print "{0} - {1} - {2} - {3}".format(ns.core.Simulator.Now(), ostLoadMeasure, ossLoadMeasure, lnetLoadMeasure)
			print ns.core.Simulator.Now()
			ns.core.Simulator.Schedule(ns.core.Seconds(PRINT_PERIOD), print_event_handler)

		def write_output_to_file(ostOutputLine):
			self.ostOutputFilePtr.write(ostOutputLine + '\n')

		ns.core.Simulator.Schedule(ns.core.Seconds(OUTPUT_PERIOD), event_handler)
		ns.core.Simulator.Schedule(ns.core.Seconds(PRINT_PERIOD), print_event_handler)

	def _open_output_file_ptrs(self):
		self.ostOutputFilePtr = open(self.ostOutputFile, 'w')

	def _close_output_file_ptrs(self):
		self.ostOutputFilePtr.close()

	def handle_apps(self, appList):
		appList = appList[:self.numIORtr]
		for i, app in enumerate(appList):
			app.update_io_rtr(self.ioRtrList[i])
			self._schedule_app_events(app)
		self._schedule_output_events()

	def run(self, stopTime):
		self._open_output_file_ptrs()
		ns.core.Simulator.Stop(ns.core.Seconds(stopTime))
		ns.core.Simulator.Run()
		ns.core.Simulator.Destroy()
		self._close_output_file_ptrs()
		
class IORouter(object):
	def __init__(self, index, stack):
		self.name = "io{0}".format(index)
		self.node = ns.network.Node()
		stack.Install(self.node)
		self.device = None
		self.address = None

	def create_socket(self, address):
		self.address = address
		self.socket = ns.network.Socket.CreateSocket(self.node, ns.core.TypeId.LookupByName("ns3::UdpSocketFactory"))

	def write_to_ost(self, stripeSize, ost):
		self.socket.SendTo(ns.network.Packet(stripeSize), 0, ns.network.InetSocketAddress(ost.address, 8000))

class LnetRouter(object):
	def __init__(self, index, stack, numOSS):
		self.name = "lnet{0}".format(index)
		self.node = ns.network.Node()
		stack.Install(self.node)
		self.ossList = []
		self.numOSS = numOSS
		self.loadPerOSS = 80/self.numOSS
		self.load = 0
		self.device = None

	def update_device(self, device):
		def receive_callback(device, packet, protocol, sender, receiver, packetType):
			self.load += self.loadPerOSS

		self.device = device
		self.device.SetPromiscReceiveCallback(receive_callback)

class OSS(object):
	def __init__(self, index, stack, numOST, parentLnetRtr):
		self.name = "oss{0}".format(index)
		self.node = ns.network.Node()
		stack.Install(self.node)
		self.numOST = numOST
		self.cpuPercentPerOST = 100/self.numOST
		self.ostList = []
		self.cpuPercent = 0
		self.device = None
		self.lnetRtr = parentLnetRtr

	def update_device(self, device):
		def receive_callback(device, packet, protocol, sender, receiver, packetType):
			self.cpuPercent += self.cpuPercentPerOST
			self.lnetRtr.load -= self.lnetRtr.loadPerOSS
		self.device = device
		self.device.SetPromiscReceiveCallback(receive_callback)

class OST(object):
	def __init__(self, index, stack, diskSpace, parentOSS):
		self.name = "ost{0}".format(index)
		self.node = ns.network.Node()
		stack.Install(self.node)
		self.device = None
		self.address = None
		self.totalDiskSpace = diskSpace
		self.usedDiskSpace = 0
		self.oss = parentOSS

	def update_device(self, device):
		self.device = device

	def create_socket(self, address):
		def recv_callback(socket):
			received_packet = socket.Recv()
			self.usedDiskSpace += received_packet.GetSize()
			self.oss.cpuPercent -= self.oss.cpuPercentPerOST
		self.address = address
		self.socket = ns.network.Socket.CreateSocket(self.node, ns.core.TypeId.LookupByName("ns3::UdpSocketFactory"))
		self.socket.Bind(ns.network.InetSocketAddress(self.address, 8000))
		self.socket.SetRecvCallback(recv_callback)

class WriteEvent(object):
	def __init__(self, size, stripeCount, seconds):
		self.size = size
		self.stripeCount = stripeCount
		self.time = seconds

class Application(object):
	def __init__(self, id, traceFile, runtime):
		self.id = id
		self.eventList = self._parse_trace(traceFile, runtime)
		self.ioRtr = None

	def update_io_rtr(self, ioRtr):
		self.ioRtr = ioRtr

	def _parse_trace(self, traceFile, runtime):
		fptr = open(traceFile, 'r')
		text = fptr.read()
		lines = text.split("\n")
		lines.remove('')
		fptr.close()
		numReq = len(lines)
		eventList = []
		for i in range(numReq):
			line = lines[i]
			elms = line.split(" ")
			timestamp = float(elms[0])
			if timestamp > float(runtime):
				break
			reqSize = int(elms[1]) 
			stripeCount = int(elms[2])
			eventList.append(WriteEvent(reqSize, stripeCount, timestamp))
		return eventList

if __name__ == '__main__':
	runtime = 200
	app = Application(1, 'FinancialApp.txt', runtime)
	simulator = LustreSimulator()
	simulator.handle_apps([app])
	simulator.run(runtime)