"""
Speed is a script to set the feed rate, and flow rate.
"""

from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
import math
from config import config
import logging

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, text=''):
	"Speed the file or text."
	gcodeText = archive.getTextIfEmpty(fileName, text)
	if gcodec.isProcedureDoneOrFileIsEmpty(gcodeText, name):
		return gcodeText
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return gcodeText
	return SpeedSkein().getCraftedGcode(gcodeText)

class SpeedSkein:
	"A class to speed a skein of extrusions."
	def __init__(self):
		self.gcode = gcodec.Gcode()
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
		self.flowRate = config.getfloat(name, 'flow.rate')
		self.accelerationRate = config.getfloat(name, 'acceleration.rate')
		self.orbitalFeedRateRatio = config.getfloat(name, 'feed.rate.orbiting.ratio')
		self.perimeterFeedRate = config.getfloat(name, 'feed.rate.perimeter')
		self.perimeterFlowRate = config.getfloat(name, 'flow.rate.perimeter')
		self.perimeterAccelerationRate = config.getfloat(name, 'acceleration.rate.perimeter')
		self.bridgeFeedRateRatio = config.getfloat(name, 'feed.rate.bridge.ratio')
		self.bridgeFlowRateRatio = config.getfloat(name, 'flow.rate.bridge')
		self.bridgeAccelerationRate = config.getfloat(name, 'acceleration.rate.bridge')
		self.travelFeedRate = config.getfloat(name, 'feed.rate.travel')
		self.dutyCycleAtBeginning = config.getfloat(name, 'dc.duty.cycle.beginning')
		self.dutyCycleAtEnding = config.getfloat(name, 'dc.duty.cycle.end')


	def addFlowRateLineIfNecessary(self):
		"Add flow rate line."
		flowRateString = self.getFlowRateString()
		if flowRateString != self.oldFlowRateString:
			self.gcode.addLine('M108 S' + flowRateString)
		self.oldFlowRateString = flowRateString

	def addAccelerationRateLineIfNecessary(self): #todo delete if not working
		"Add Acceleration rate line."
		AccelerationRateString = self.getAccelerationRateString()
		if AccelerationRateString != self.oldAccelerationRateString:
			self.gcode.addLine('M201 E' + AccelerationRateString)
		self.oldAccelerationRateString = AccelerationRateString

	def addParameterString(self, firstWord, parameterWord):
		"Add parameter string."
		if parameterWord == '':
			self.gcode.addLine(firstWord)
			return
		self.gcode.addParameter(firstWord, parameterWord)

	def getCraftedGcode(self, gcodeText):
		"Parse gcode text and store the speed gcode."
		self.travelFeedRateMinute = 60.0 * self.travelFeedRate
		self.lines = archive.getTextLines(gcodeText)
		self.parseInitialization()
		for line in self.lines[self.lineIndex :]:
			self.parseLine(line)
		self.addParameterString('M113', self.dutyCycleAtEnding) # Set duty cycle .
		return self.gcode.output.getvalue()

	def getFlowRateString(self):
		"Get the flow rate string."
		nozzleXsection = (self.nozzleDiameter / 2) ** 2 * math.pi
		extrusionXsection = ((self.absolutePerimeterWidth + self.layerThickness) / 4) ** 2 * math.pi#todo transfer to inset
		
		if not self.addFlowRate:
			return None
		flowRate = self.flowRate * self.feedRate
		if self.isBridgeLayer:
			flowRate = (self.bridgeFlowRateRatio * self.bridgeFeedRateRatio) * (self.perimeterFlowRate * self.perimeterFeedRate) * (nozzleXsection / extrusionXsection)
		if self.isPerimeterPath:
			flowRate = self.perimeterFlowRate * self.perimeterFeedRate
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
		'Get gcode line with feed rate.'
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
		return self.gcode.getLineWithFeedRate(feedRateMinute, line, splitLine)

	def parseInitialization(self):
		'Parse gcode initialization and store the parameters.'
		for self.lineIndex in xrange(len(self.lines)):
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.gcode.parseSplitLine(firstWord, splitLine)
			if firstWord == '(<layerThickness>':
				self.layerThickness = float(splitLine[1])
			elif firstWord == '(</extruderInitialization>)':
				self.gcode.addLine('(<procedureName> speed </procedureName>)')
				return
			elif firstWord == '(<perimeterWidth>':
				self.absolutePerimeterWidth = abs(float(splitLine[1]))
				self.gcode.addTagBracketedLine('operatingFeedRatePerSecond', self.feedRate)
				self.gcode.addTagBracketedLine('PerimeterFeedRatePerSecond', self.perimeterFeedRate)
				if self.addFlowRate:
					self.gcode.addTagBracketedLine('operatingFlowRate', self.flowRate * self.feedRate)
					self.gcode.addTagBracketedLine('PerimeterFlowRate', self.perimeterFlowRate * self.perimeterFeedRate)
				orbitalFeedRatePerSecond = self.feedRate * self.orbitalFeedRateRatio
				self.gcode.addTagBracketedLine('orbitalFeedRatePerSecond', orbitalFeedRatePerSecond)
				self.gcode.addTagBracketedLine('travelFeedRate', self.travelFeedRate)
			elif firstWord == '(<nozzleDiameter>':
				self.nozzleDiameter = abs(float(splitLine[1]))
			self.gcode.addLine(line)

	def parseLine(self, line):
		"Parse a gcode line and add it to the speed skein."
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == '(<crafting>)':
			self.gcode.addLine(line)
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
		self.gcode.addLine(line)
