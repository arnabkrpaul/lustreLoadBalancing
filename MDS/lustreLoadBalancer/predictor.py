import math
import markovify

NUM_OF_PREDICTED_REQUESTS = 3
MIN_CORPUS_LENGTH = 10
MAX_CORPUS_LENGTH = 10000
MARKOV_CHAIN_ORDER = 3

class RequestPredictor(object):
	def __init__(self):
		self.appIDtoModelDict = {}
		self.numPredictedRequests = NUM_OF_PREDICTED_REQUESTS
		self.minCorpusLength = MIN_CORPUS_LENGTH
		self.maxCorpusLength = MAX_CORPUS_LENGTH
		self.markovOrder = MARKOV_CHAIN_ORDER

	def get_requests(self, appID, stripeSize, numStripes):
		currRequest = Request("req0", stripeSize, numStripes)
		currSize = stripeSize * numStripes
		reqList = [currRequest]
		if self.numPredictedRequests == 0:
			return reqList
		if appID not in self.appIDtoModelDict:
			self.appIDtoModelDict[appID] = {'mean': float(currSize), 'std': 0.0, 'numSamples': 1, 'samples': [currSize]}
		else:
			self.appIDtoModelDict[appID]['numSamples'] += 1
			prevMean = self.appIDtoModelDict[appID]['mean']
			self.appIDtoModelDict[appID]['mean'] = (float(self.appIDtoModelDict[appID]['numSamples']-1)*prevMean + float(currSize))/self.appIDtoModelDict[appID]['numSamples']
			prevVariance = math.pow(self.appIDtoModelDict[appID]['std'], 2)
			newVariance = (float(self.appIDtoModelDict[appID]['numSamples']-1)*prevVariance + (float(currSize)-prevMean)*(float(currSize)-self.appIDtoModelDict[appID]['mean']))/self.appIDtoModelDict[appID]['numSamples']
			self.appIDtoModelDict[appID]['std'] = math.sqrt(newVariance)
			self.appIDtoModelDict[appID]['samples'].append(currSize)
			if len(self.appIDtoModelDict[appID]['samples']) > self.maxCorpusLength:
				self.appIDtoModelDict[appID]['samples'] = self.appIDtoModelDict[appID]['samples'][1:]
			if self.appIDtoModelDict[appID]['numSamples'] >= self.minCorpusLength:
				X = [self.generate_training_samples(self.appIDtoModelDict[appID]['samples'], self.appIDtoModelDict[appID]['mean'], self.appIDtoModelDict[appID]['std'])]
				model = markovify.Chain(X, self.markovOrder)
				predictions = self.get_predictions(model, X[0], self.numPredictedRequests)
				predictedStripeCounts = self.convert_predictions_to_stripe_count(predictions, self.appIDtoModelDict[appID]['mean'], self.appIDtoModelDict[appID]['std'], stripeSize)
				for i in range(len(predictedStripeCounts)):
					reqName = "req{0}".format(i+1)
					req = Request(reqName, stripeSize, predictedStripeCounts[i])
					reqList.append(req)
		return reqList

	def generate_training_samples(self, inputSamples, mean, std):
		training_samples = []
		for s in inputSamples:
			if float(s) <= mean - 0.85*std:
				training_samples.append(-2)
			elif float(s) <= mean - 0.25*std:
				training_samples.append(-1)
			elif float(s) <= mean + 0.25*std:
				training_samples.append(0)
			elif float(s) <= mean + 0.85*std:
				training_samples.append(1)
			else:
				training_samples.append(2)
		return training_samples

	def get_predictions(self, model, chain, numPredictions):
		predictions = []
		for i in range(numPredictions):
			numOrigSamplesForInputState = self.markovOrder - i
			if numOrigSamplesForInputState > 0:
				inputSample = tuple(chain[-numOrigSamplesForInputState:] + predictions)
			else:
				inputSample = tuple(predictions[-self.markovOrder:])
			try:
				prediction = model.move(inputSample)
			except:
				prediction = 0
			if isinstance(prediction, str):
				prediction = 0
			predictions.append(prediction)
		return predictions

	def convert_predictions_to_stripe_count(self, predictions, mean, std, stripeSize):
		predictedStripeCounts = []
		for p in predictions:
			if p == -2:
				predictedStripeCounts.append(self.get_stripe_count(mean-1.7*std, stripeSize))
			elif p == -1:
				predictedStripeCounts.append(self.get_stripe_count(mean-0.5*std, stripeSize))
			elif p == 1:
				predictedStripeCounts.append(self.get_stripe_count(mean+0.5*std, stripeSize))
			elif p == 2:
				predictedStripeCounts.append(self.get_stripe_count(mean+1.7*std, stripeSize))
			else:
				predictedStripeCounts.append(self.get_stripe_count(mean, stripeSize))
		return predictedStripeCounts

	def get_stripe_count(self, size, stripeSize):
		return int(math.ceil(size/stripeSize))

class Request(object):
	def __init__(self, name, stripeSize, numStripes):
		self.name = name
		self.numStripes = numStripes
		self.stripeSize = stripeSize
		self.size = stripeSize * numStripes