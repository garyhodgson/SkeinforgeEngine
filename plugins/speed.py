"""
Speed is a script to set the feed rate, and flow rate.

Original author 
	'Enrique Perez (perez_enrique@yahoo.com) 
	modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
	
license 
	'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

"""

from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
import math
from config import config
import logging


logger = logging.getLogger(__name__)
name = 'speed'

def getCraftedText(fileName, text, gcode):
	"Speed the file or text."
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return text
	return SpeedSkein(gcode).getCraftedGcode(text)

class SpeedSkein:
	"A class to speed a skein of extrusions."
	def __init__(self, gcode):
		self.gcodeCodec = gcodec.Gcode()
		self.gcode = gcode
		self.isBridgeLayer = False
		self.isExtruderActive = False
		self.isPerimeterPath = False
		self.lineIndex = 0
		self.lines = None
		self.oldFlowRateString = None
		self.oldAccelerationRateString = None
		self.activateSpeed = config.getboolean(name, 'active')
		self.addFlowRate = config.getboolean(name, 'add.flow.rate')
		self.addAccelerationRate = config.getboolean(name, 'add.acceleration.rate')
		self.feedRate = config.getfloat(name, 'feed.rate')
		self.flowRateRatio = config.getfloat(name, 'flow.rate.ratio')
		self.accelerationRate = config.getfloat(name, 'acceleration.rate')
		self.orbitalFeedRateRatio = config.getfloat(name, 'feed.rate.orbiting.ratio')
		self.perimeterFeedRate = config.getfloat(name, 'feed.rate.perimeter')
		self.perimeterFlowRateRatio = config.getfloat(name, 'flow.rate.perimeter.ratio')
		self.perimeterAccelerationRate = config.getfloat(name, 'acceleration.rate.perimeter')
		self.bridgeFeedRateRatio = config.getfloat(name, 'feed.rate.bridge.ratio')
		self.bridgeFlowRateRatio = config.getfloat(name, 'flow.rate.bridge.ratio')
		self.bridgeAccelerationRate = config.getfloat(name, 'acceleration.rate.bridge')
		self.travelFeedRate = config.getfloat(name, 'feed.rate.travel')
		self.dutyCycleAtBeginning = config.getfloat(name, 'dc.duty.cycle.beginning')
		self.dutyCycleAtEnding = config.getfloat(name, 'dc.duty.cycle.end')
		
		runtimeParameters = self.gcode.runtimeParameters
		runtimeParameters.operatingFeedRatePerSecond = self.feedRate
		runtimeParameters.perimeterFeedRatePerSecond = self.perimeterFeedRate
		
		if self.addFlowRate:
			runtimeParameters.operatingFlowRate = self.flowRateRatio * self.feedRate
			runtimeParameters.perimeterFlowRateRatio = self.perimeterFlowRateRatio * self.perimeterFeedRate
		runtimeParameters.orbitalFeedRatePerSecond = self.feedRate * self.orbitalFeedRateRatio
		runtimeParameters.travelFeedRate = self.travelFeedRate
		
		self.travelFeedRateMinute = 60.0 * self.travelFeedRate
		self.absolutePerimeterWidth = abs(config.getfloat('carve', 'extrusion.width'))
		self.layerThickness = config.getfloat('carve', 'layer.height')
		self.nozzleDiameter = config.getfloat('inset', 'nozzle.diameter')

	def addFlowRateLineIfNecessary(self):
		"Add flow rate line."
		flowRateString = self.getFlowRateString()
		if flowRateString != self.oldFlowRateString:
			self.gcodeCodec.addLine('M108 S' + flowRateString)
		self.oldFlowRateString = flowRateString

	def addAccelerationRateLineIfNecessary(self): #todo delete if not working
		"Add Acceleration rate line."
		AccelerationRateString = self.getAccelerationRateString()
		if AccelerationRateString != self.oldAccelerationRateString:
			self.gcodeCodec.addLine('M201 E' + AccelerationRateString)
		self.oldAccelerationRateString = AccelerationRateString

	def addParameterString(self, firstWord, parameterWord):
		"Add parameter string."
		if parameterWord == '':
			self.gcodeCodec.addLine(firstWord)
			return
		self.gcodeCodec.addParameter(firstWord, parameterWord)

	def getCraftedGcode(self, gcodeText):
		"Parse gcodeCodec text and store the speed gcodeCodec."
		
		self.lines = archive.getTextLines(gcodeText)
		
		for line in self.lines[self.lineIndex :]:
			self.parseLine(line)
		self.addParameterString('M113', self.dutyCycleAtEnding) # Set duty cycle .
		return self.gcodeCodec.output.getvalue()

	def getFlowRateString(self):
		"Get the flow rate string."
		nozzleXsection = (self.nozzleDiameter / 2) ** 2 * math.pi
		extrusionXsection = ((self.absolutePerimeterWidth + self.layerThickness) / 4) ** 2 * math.pi#todo transfer to inset
		
		if not self.addFlowRate:
			return None
		flowRate = self.flowRateRatio * self.feedRate
		if self.isBridgeLayer:
			flowRate = (self.bridgeFlowRateRatio * self.bridgeFeedRateRatio) * (self.perimeterFlowRateRatio * self.perimeterFeedRate) * (nozzleXsection / extrusionXsection)
		if self.isPerimeterPath:
			flowRate = self.perimeterFlowRateRatio * self.perimeterFeedRate
		return euclidean.getFourSignificantFigures(flowRate)

	def getAccelerationRateString(self):
		"Get the Acceleration rate string."

		if not self.addAccelerationRate:
			return None
		accelerationRate = self.accelerationRate
		if self.isBridgeLayer:
			accelerationRate = self.bridgeAccelerationRate
		if self.isPerimeterPath:
			accelerationRate = self.perimeterAccelerationRate
		return euclidean.getFourSignificantFigures(accelerationRate)

	def getSpeededLine(self, line, splitLine):
		'Get gcodeCodec line with feed rate.'
		if gcodec.getIndexOfStartingWithSecond('F', splitLine) > 0:
			return line
		feedRateMinute = 60.0 * self.feedRate
		if self.isBridgeLayer:
			feedRateMinute = self.bridgeFeedRateRatio * self.perimeterFeedRate * 60 # todo former reference to main feed now perimeter feed
		if self.isPerimeterPath:
			feedRateMinute = self.perimeterFeedRate * 60
		if not self.isExtruderActive:
			feedRateMinute = self.travelFeedRate * 60
		self.addFlowRateLineIfNecessary()
		self.addAccelerationRateLineIfNecessary()
		return self.gcodeCodec.getLineWithFeedRate(feedRateMinute, line, splitLine)

	def parseLine(self, line):
		"Parse a gcodeCodec line and add it to the speed skein."
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == '(<crafting>)':
			self.gcodeCodec.addLine(line)
			self.addParameterString('M113', self.dutyCycleAtBeginning)
			return
		elif firstWord == 'G1':
			line = self.getSpeededLine(line, splitLine)
		elif firstWord == 'M101':
			self.isExtruderActive = True
		elif firstWord == 'M103':
			self.isExtruderActive = False
		elif firstWord == '(<bridgeRotation>':
			self.isBridgeLayer = True
		elif firstWord == '(<layer>':
			self.isBridgeLayer = False
			self.addFlowRateLineIfNecessary()
			self.addAccelerationRateLineIfNecessary()
		elif firstWord == '(<perimeter>' or firstWord == '(<perimeterPath>)':
			self.isPerimeterPath = True
		elif firstWord == '(</perimeter>)' or firstWord == '(</perimeterPath>)':
			self.isPerimeterPath = False
		self.gcodeCodec.addLine(line)
