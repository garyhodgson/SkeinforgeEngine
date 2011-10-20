"""
Cool is a script to cool the shape.
"""

from fabmetheus_utilities.fabmetheus_tools import fabmetheus_interpret
from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from fabmetheus_utilities import intercircle
from fabmetheus_utilities import settings
from skeinforge_application.skeinforge_utilities import skeinforge_craft
from skeinforge_application.skeinforge_utilities import skeinforge_polyfile
from skeinforge_application.skeinforge_utilities import skeinforge_profile
import os
import sys
from config import config
import logging

__author__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__date__ = '$Date: 2008/21/04 $'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, text):
	'Cool a gcode linear move text.'
	gcodeText = archive.getTextIfEmpty(fileName, text)
	if gcodec.isProcedureDoneOrFileIsEmpty(gcodeText, name):
		return gcodeText
	if not config.getboolean(name, 'active'):
		return gcodeText
	return CoolSkein().getCraftedGcode(gcodeText)

class CoolSkein:
	'A class to cool a skein of extrusions.'
	def __init__(self):
		self.boundaryLayer = None
		self.coolTemperature = None
		self.gcode = gcodec.Gcode()
		self.feedRateMinute = 960.0
		self.highestZ = 1.0
		self.isBridgeLayer = False
		self.isExtruderActive = False
		self.layerCount = settings.LayerCount()
		self.lineIndex = 0
		self.lines = None
		self.multiplier = 1.0
		self.oldFlowRate = None
		self.oldFlowRateString = None
		self.oldLocation = None
		self.oldTemperature = None
		
		self.activateCool = config.getboolean(name, 'active')
		self.minimumLayerTime = config.getfloat(name, 'minimum.layer.time')
		self.minimumLayerFeedrate = config.getfloat(name, 'minimum.layer.feed.rate')
		self.turnFanOnAtBeginning = config.getboolean(name, 'turn.on.fan.at.beginning')
		self.turnFanOffAtEnding = config.getboolean(name, 'turn.off.fan.at.end')
		self.nameOfCoolStartFile = config.get(name, 'cool.start.file')
		self.nameOfCoolEndFile = config.get(name, 'cool.end.file')
		self.coolType = config.get(name, 'cool.type')
		self.maximumCool = config.getfloat(name, 'maximum.cool')
		self.bridgeCool = config.getfloat(name, 'bridge.cool')
		self.minimumOrbitalRadius = config.getfloat(name, 'minimum.orbital.radius')

	def addCoolOrbits(self, remainingOrbitTime):
		'Add the minimum radius cool orbits.'
		if len(self.boundaryLayer.loops) < 1:
			return
		insetBoundaryLoops = intercircle.getInsetLoopsFromLoops(self.perimeterWidth, self.boundaryLayer.loops)
		if len(insetBoundaryLoops) < 1:
			insetBoundaryLoops = self.boundaryLayer.loops
		largestLoop = euclidean.getLargestLoop(insetBoundaryLoops)
		loopArea = euclidean.getAreaLoopAbsolute(largestLoop)
		if loopArea < self.minimumArea:
			center = 0.5 * (euclidean.getMaximumByComplexPath(largestLoop) + euclidean.getMinimumByComplexPath(largestLoop))
			centerXBounded = max(center.real, self.boundingRectangle.cornerMinimum.real)
			centerXBounded = min(centerXBounded, self.boundingRectangle.cornerMaximum.real)
			centerYBounded = max(center.imag, self.boundingRectangle.cornerMinimum.imag)
			centerYBounded = min(centerYBounded, self.boundingRectangle.cornerMaximum.imag)
			center = complex(centerXBounded, centerYBounded)
			maximumCorner = center + self.halfCorner
			minimumCorner = center - self.halfCorner
			largestLoop = euclidean.getSquareLoopWiddershins(minimumCorner, maximumCorner)
		pointComplex = euclidean.getXYComplexFromVector3(self.oldLocation)
		if pointComplex != None:
			largestLoop = euclidean.getLoopStartingNearest(self.perimeterWidth, pointComplex, largestLoop)
		intercircle.addOrbitsIfLarge(
			self.gcode, largestLoop, self.orbitalFeedRatePerSecond, remainingOrbitTime, self.highestZ)

	def addCoolTemperature(self, remainingOrbitTime):
		'Parse a gcode line and add it to the cool skein.'
		layerCool = self.maximumCool * remainingOrbitTime / self.minimumLayerTime
		if self.isBridgeLayer:
			layerCool = max(self.bridgeCool, layerCool)
		if self.oldTemperature != None and layerCool != 0.0:
			self.coolTemperature = self.oldTemperature - layerCool
			self.addTemperature(self.coolTemperature)

	def addFlowRateLineIfNecessary(self, flowRate):
		'Add a line of flow rate if different.'
		flowRateString = euclidean.getFourSignificantFigures(flowRate)
		if flowRateString == self.oldFlowRateString:
			return
		if flowRateString != None:
			self.gcode.addLine('M108 S' + flowRateString)
		self.oldFlowRateString = flowRateString

	def addFlowRateMultipliedLineIfNecessary(self, flowRate):
		'Add a multipled line of flow rate if different.'
		if flowRate != None:
			self.addFlowRateLineIfNecessary(self.multiplier * flowRate)

	def addGcodeFromFeedRateMovementZ(self, feedRateMinute, point, z):
		'Add a movement to the output.'
		self.gcode.addLine(self.gcode.getLinearGcodeMovementWithFeedRate(feedRateMinute, point, z))

	def addOrbitsIfNecessary(self, remainingOrbitTime):
		'Parse a gcode line and add it to the cool skein.'
		if remainingOrbitTime > 0.0 and self.boundaryLayer != None:
			self.addCoolOrbits(remainingOrbitTime)

	def addTemperature(self, temperature):
		'Add a line of temperature.'
		self.gcode.addLine('M104 S' + euclidean.getRoundedToThreePlaces(temperature))

	def getCoolMove(self, line, location, splitLine):
		'Add line to time spent on layer.'
		self.feedRateMinute = gcodec.getFeedRateMinute(self.feedRateMinute, splitLine)
		self.addFlowRateMultipliedLineIfNecessary(self.oldFlowRate)
		coolFeedRate = self.multiplier * self.feedRateMinute
		if coolFeedRate >  self.minimumLayerFeedrate *60 :
			coolFeedRate = coolFeedRate
		else:
			coolFeedRate =  self.minimumLayerFeedrate *60
		return self.gcode.getLineWithFeedRate(coolFeedRate, line, splitLine)

	def getCraftedGcode(self, gcodeText):
		'Parse gcode text and store the cool gcode.'
		self.coolEndLines = settings.getLinesInAlterationsOrGivenDirectory(self.nameOfCoolEndFile)
		self.coolStartLines = settings.getLinesInAlterationsOrGivenDirectory(self.nameOfCoolStartFile)
		self.halfCorner = complex(self.minimumOrbitalRadius, self.minimumOrbitalRadius)
		self.lines = archive.getTextLines(gcodeText)
		self.minimumArea = 4.0 * self.minimumOrbitalRadius * self.minimumOrbitalRadius
		self.parseInitialization()
		self.boundingRectangle = gcodec.BoundingRectangle().getFromGcodeLines(
			self.lines[self.lineIndex :], 0.5 * self.perimeterWidth)
		margin = 0.2 * self.perimeterWidth
		halfCornerMargin = self.halfCorner + complex(margin, margin)
		self.boundingRectangle.cornerMaximum -= halfCornerMargin
		self.boundingRectangle.cornerMinimum += halfCornerMargin
		for self.lineIndex in xrange(self.lineIndex, len(self.lines)):
			line = self.lines[self.lineIndex]
			self.parseLine(line)
		if self.turnFanOffAtEnding:
			self.gcode.addLine('M107')
		return self.gcode.output.getvalue()

	def getLayerTime(self):
		'Get the time the extruder spends on the layer.'
		feedRateMinute = self.feedRateMinute
		layerTime = 0.0
		lastThreadLocation = self.oldLocation
		for lineIndex in xrange(self.lineIndex, len(self.lines)):
			line = self.lines[lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'G1':
				location = gcodec.getLocationFromSplitLine(lastThreadLocation, splitLine)
				feedRateMinute = gcodec.getFeedRateMinute(feedRateMinute, splitLine)
				if lastThreadLocation != None:
					feedRateSecond = feedRateMinute / 60.0
					layerTime += location.distance(lastThreadLocation) / feedRateSecond
				lastThreadLocation = location
			elif firstWord == '(<bridgeRotation>':
				self.isBridgeLayer = True
			elif firstWord == '(</layer>)':
				return layerTime
		return layerTime

	def parseInitialization(self):
		'Parse gcode initialization and store the parameters.'
		for self.lineIndex in xrange(len(self.lines)):
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.gcode.parseSplitLine(firstWord, splitLine)
			if firstWord == 'M108':
				self.setOperatingFlowString(splitLine)
			elif firstWord == '(<perimeterWidth>':
				self.perimeterWidth = float(splitLine[1])
				if self.turnFanOnAtBeginning:
					self.gcode.addLine('M106')
			elif firstWord == '(</extruderInitialization>)':
				self.gcode.addLine('(<procedureName> cool </procedureName>)')
				return
			elif firstWord == '(<orbitalFeedRatePerSecond>':
				self.orbitalFeedRatePerSecond = float(splitLine[1])
			self.gcode.addLine(line)

	def parseLine(self, line):
		'Parse a gcode line and add it to the cool skein.'
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == 'G1':
			location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
			self.highestZ = max(location.z, self.highestZ)
			if self.isExtruderActive:
				line = self.getCoolMove(line, location, splitLine)
			self.oldLocation = location
		elif firstWord == 'M101':   #todo delete?
			self.isExtruderActive = True
		elif firstWord == 'M103':
			self.isExtruderActive = False
		elif firstWord == 'M104':
			self.oldTemperature = gcodec.getDoubleAfterFirstLetter(splitLine[1])
		elif firstWord == 'M108':
			self.setOperatingFlowString(splitLine)
			self.addFlowRateMultipliedLineIfNecessary(self.oldFlowRate)
			return
		elif firstWord == '(<boundaryPoint>':
			self.boundaryLoop.append(gcodec.getLocationFromSplitLine(None, splitLine).dropAxis())
		elif firstWord == '(<layer>':
			self.layerCount.printProgressIncrement('cool')
			self.gcode.addLine(line)
			self.gcode.addLinesSetAbsoluteDistanceMode(self.coolStartLines)
			layerTime = self.getLayerTime()
			remainingOrbitTime = max(self.minimumLayerTime - layerTime, 0.0)
			self.addCoolTemperature(remainingOrbitTime)
			if self.coolType == 'Orbit':
				self.addOrbitsIfNecessary(remainingOrbitTime)
			else:
				self.setMultiplier(layerTime)
			z = float(splitLine[1])
			self.boundaryLayer = euclidean.LoopLayer(z)
			self.highestZ = max(z, self.highestZ)
			self.gcode.addLinesSetAbsoluteDistanceMode(self.coolEndLines)
			return
		elif firstWord == '(</layer>)':
			self.isBridgeLayer = False
			self.multiplier = 1.0
			if self.coolTemperature != None:
				self.addTemperature(self.oldTemperature)
				self.coolTemperature = None
			self.addFlowRateLineIfNecessary(self.oldFlowRate)
		elif firstWord == '(<nestedRing>)':
			self.boundaryLoop = []
			self.boundaryLayer.loops.append(self.boundaryLoop)
		self.gcode.addLine(line)

	def setMultiplier(self, layerTime):
		'Set the feed and flow rate multiplier.'
		self.multiplier = min(1.0, layerTime / self.minimumLayerTime)

	def setOperatingFlowString(self, splitLine):
		'Set the operating flow string from the split line.'
		self.oldFlowRate = float(splitLine[1][1 :])
