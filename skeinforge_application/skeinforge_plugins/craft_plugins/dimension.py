"""
Dimension adds Adrian's extruder distance E value to the gcode movement lines, as described at:
"""

from datetime import date
from fabmetheus_utilities.fabmetheus_tools import fabmetheus_interpret
from fabmetheus_utilities.geometry.solids import triangle_mesh
from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from fabmetheus_utilities import intercircle
from fabmetheus_utilities import settings
from skeinforge_application.skeinforge_utilities import skeinforge_craft
from skeinforge_application.skeinforge_utilities import skeinforge_polyfile
from skeinforge_application.skeinforge_utilities import skeinforge_profile
import math
import os
import sys
from config import config
import logging

__author__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__date__ = '$Date: 2008/02/05 $'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, gcodeText=''):
	'Dimension a gcode file or text.'
	gcodeText = archive.getTextIfEmpty(fileName, gcodeText)
	if gcodec.isProcedureDoneOrFileIsEmpty(gcodeText, name):
		return gcodeText
	if not config.getboolean(name, 'active'):
		return gcodeText
	return DimensionSkein().getCraftedGcode(gcodeText)

class DimensionSkein:
	'A class to dimension a skein of extrusions.'
	def __init__(self):
		'Initialize.'
		self.absoluteDistanceMode = True
		self.boundaryLayers = []
		self.gcode = gcodec.Gcode()
		self.feedRateMinute = None
		self.isExtruderActive = False
		self.layerIndex = -1
		self.lineIndex = 0
		self.maximumZTravelFeedRatePerSecond = None
		self.oldLocation = None
		self.operatingFlowRate = None
		self.retractionRatio = 1.0
		self.totalExtrusionDistance = 0.0
		self.travelFeedRatePerSecond = None
		self.zDistanceRatio = 5.0
		self.oldFlowRateString = None
		self.autoRetractDistance = 0
		self.timeToNextThread = None
		
		self.activateDimension = config.getboolean(name, 'active')
		self.filamentDiameter = config.getfloat(name, 'filament.diameter')
		self.filamentPackingDensity = config.getfloat(name, 'filament.packing.density')
		self.activateCalibration = config.getboolean(name, 'calibrating.active')
		self.MeasuredXSection = config.getfloat(name, 'calibrating.x.section')
		self.oozeRate = config.getfloat(name, 'oozerate')
		self.extruderRetractionSpeed = config.getfloat(name, 'extruder.retraction.speed')
		self.extrusionUnits = config.get(name, 'extrusion.units')

	def addLinearMoveExtrusionDistanceLine(self, extrusionDistance):
		'Get the extrusion distance string from the extrusion distance.'
		self.gcode.output.write('G1 F%s\n' % self.extruderRetractionSpeedMinuteString)
		self.gcode.output.write('G1%s\n' % self.getExtrusionDistanceStringFromExtrusionDistance(extrusionDistance))
		self.gcode.output.write('G1 F%s\n' % self.gcode.getRounded(self.feedRateMinute))

	def getCraftedGcode(self, gcodeText):
		'Parse gcode text and store the dimension gcode.'
		filamentRadius = 0.5 * self.filamentDiameter
		filamentPackingArea = math.pi * filamentRadius * filamentRadius * self.filamentPackingDensity
		self.doubleMinimumTravelForRetraction = 0
		self.lines = archive.getTextLines(gcodeText)
		self.parseInitialization()
		self.parseBoundaries()
		self.calibrationFactor = 1
		if self.activateCalibration:
			self.calibrationFactor = (((self.layerThickness ** 2 / 4) * math.pi) + self.layerThickness * (self.MeasuredXSection - self.layerThickness)) / (((self.layerThickness ** 2 / 4) * math.pi) + self.layerThickness * (self.perimeterWidth - self.layerThickness))
			self.newfilamentPackingDensity = self.filamentPackingDensity * self.calibrationFactor
			logger.info('****************Filament Packing Density (For Calibration)**********************:')
			logger.info('Filament Packing Density (For Calibration) STEPPER EXTRUDERS ONLY : %s', self.newfilamentPackingDensity)
			logger.info('****************Filament Packing Density (For Calibration)**********************')
		self.flowScaleSixty = 60.0 * ((((self.layerThickness + self.perimeterWidth) / 4) ** 2 * math.pi) / filamentPackingArea) / self.calibrationFactor
		if self.calibrationFactor is None:
			logger.warning('Measured extrusion width cant be 0, either un-check calibration or set measured width to what you have measured!')
		if self.operatingFlowRate == None:
			logger.warning('There is no operatingFlowRate so dimension will do nothing.')
			return gcodeText
		self.extruderRetractionSpeedMinuteString = self.gcode.getRounded(60.0 * self.extruderRetractionSpeed)
		if self.maximumZTravelFeedRatePerSecond != None and self.travelFeedRatePerSecond != None:
			self.zDistanceRatio = self.travelFeedRatePerSecond / self.maximumZTravelFeedRatePerSecond
		for lineIndex in xrange(self.lineIndex, len(self.lines)):
			self.parseLine(lineIndex)
		return self.gcode.output.getvalue()

	def getDimensionedArcMovement(self, line, splitLine):
		'Get a dimensioned arc movement.'
		if self.oldLocation == None:
			return line
		relativeLocation = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
		self.oldLocation += relativeLocation
		distance = gcodec.getArcDistance(relativeLocation, splitLine)
		return line + self.getExtrusionDistanceString(distance, splitLine)

	def getDimensionedLinearMovement(self, line, splitLine):
		'Get a dimensioned linear movement.'
		distance = 0.0
		if self.absoluteDistanceMode:
			location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
			if self.oldLocation != None:
				distance = abs(location - self.oldLocation)
			self.oldLocation = location
		else:
			if self.oldLocation == None:
				logger.warning('Warning: There was no absolute location when the G91 command was parsed, so the absolute location will be set to the origin.')
				self.oldLocation = Vector3() #todo why was it  commented in sfact?
			location = gcodec.getLocationFromSplitLine(None, splitLine)
			distance = abs(location)
			self.oldLocation += location
		return line + self.getExtrusionDistanceString(distance, splitLine)

	def getDistanceToNextThread(self, lineIndex):
		'Get the travel distance to the next thread.'
		if self.oldLocation == None:
			return None
		isActive = False
		location = self.oldLocation
		for afterIndex in xrange(lineIndex + 1, len(self.lines)):
			line = self.lines[afterIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'G1':
				if isActive:
					location = gcodec.getLocationFromSplitLine(location, splitLine)
					locationEnclosureIndex = self.getSmallestEnclosureIndex(location.dropAxis())
					if locationEnclosureIndex != self.getSmallestEnclosureIndex(self.oldLocation.dropAxis()):
						return None
					locationMinusOld = location - self.oldLocation
					xyTravel = abs(locationMinusOld.dropAxis())
					zTravelMultiplied = locationMinusOld.z * self.zDistanceRatio
					self.timeToNextThread = math.sqrt(xyTravel * xyTravel + zTravelMultiplied * zTravelMultiplied) / self.feedRateMinute * 60
					self.autoRetractDistance = self.timeToNextThread * abs(self.oozeRate) / 60
					return math.sqrt(xyTravel * xyTravel + zTravelMultiplied * zTravelMultiplied)
			elif firstWord == 'M101':
				isActive = True
			elif firstWord == 'M103':
				isActive = False
		return None

	def getExtrusionDistanceString(self, distance, splitLine):
		'Get the extrusion distance string.'
		self.feedRateMinute = gcodec.getFeedRateMinute(self.feedRateMinute, splitLine)
		if not self.isExtruderActive:
			return ''
		if distance <= 0.0:
			return ''
		scaledFlowRate = self.flowRate * self.flowScaleSixty
		return self.getExtrusionDistanceStringFromExtrusionDistance(scaledFlowRate / self.feedRateMinute * distance)

	def getExtrusionDistanceStringFromExtrusionDistance(self, extrusionDistance):
		'Get the extrusion distance string from the extrusion distance.'
		if self.extrusionUnits == 'relative':
			return ' E' + self.gcode.getRounded(extrusionDistance)
		self.totalExtrusionDistance += extrusionDistance
		return ' E' + self.gcode.getRounded(self.totalExtrusionDistance)

	def getRetractionRatio(self, lineIndex):
		'Get the retraction ratio.'
		self.distanceToNextThread = self.getDistanceToNextThread(lineIndex)
		return 1.00

	def getSmallestEnclosureIndex(self, point):
		'Get the index of the smallest boundary loop which encloses the point.'
		boundaryLayer = self.boundaryLayers[self.layerIndex]
		for loopIndex, loop in enumerate(boundaryLayer.loops):
			if euclidean.isPointInsideLoop(loop, point):
				return loopIndex
		return None

	def parseBoundaries(self):
		'Parse the boundaries and add them to the boundary layers.'
		boundaryLoop = None
		boundaryLayer = None
		for line in self.lines[self.lineIndex :]:
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == '(</boundaryPerimeter>)':
				boundaryLoop = None
			elif firstWord == '(<boundaryPoint>':
				location = gcodec.getLocationFromSplitLine(None, splitLine)
				if boundaryLoop == None:
					boundaryLoop = []
					boundaryLayer.loops.append(boundaryLoop)
				boundaryLoop.append(location.dropAxis())
			elif firstWord == '(<layer>':
				boundaryLayer = euclidean.LoopLayer(float(splitLine[1]))
				self.boundaryLayers.append(boundaryLayer)
		for boundaryLayer in self.boundaryLayers:
			triangle_mesh.sortLoopsInOrderOfArea(False, boundaryLayer.loops)

	def parseInitialization(self):
		'Parse gcode initialization and store the parameters.'
		for self.lineIndex in xrange(len(self.lines)):
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.gcode.parseSplitLine(firstWord, splitLine)
			if firstWord == '(</extruderInitialization>)':
				self.gcode.addLine('(<procedureName> dimension </procedureName>)')
				return
			elif firstWord == '(<layerThickness>':
				self.layerThickness = float(splitLine[1])
			elif firstWord == '(<maximumZDrillFeedRatePerSecond>':
				self.maximumZTravelFeedRatePerSecond = float(splitLine[1])
			elif firstWord == '(<maximumZTravelFeedRatePerSecond>':
				self.maximumZTravelFeedRatePerSecond = float(splitLine[1])
			elif firstWord == '(<operatingFeedRatePerSecond>':
				self.feedRateMinute = 60.0 * float(splitLine[1])
			elif firstWord == '(<operatingFlowRate>':
				self.operatingFlowRate = float(splitLine[1])
				self.flowRate = self.operatingFlowRate
			elif firstWord == '(<perimeterWidth>':
				self.perimeterWidth = float(splitLine[1])
			elif firstWord == '(<travelFeedRatePerSecond>':
				self.travelFeedRatePerSecond = float(splitLine[1])
			self.gcode.addLine(line)

	def parseLine(self, lineIndex):
		'Parse a gcode line and add it to the dimension skein.'
		line = self.lines[lineIndex].lstrip()
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == 'G2' or firstWord == 'G3':
			line = self.getDimensionedArcMovement(line, splitLine)
		if firstWord == 'G1':
			line = self.getDimensionedLinearMovement(line, splitLine)
		if firstWord == 'G90':
			self.absoluteDistanceMode = True
		elif firstWord == 'G91':
			self.absoluteDistanceMode = False
		elif firstWord == '(<layer>':
			if self.extrusionUnits != 'relative':
				self.gcode.addLine('M82')
			else: self.gcode.addLine('M83')
			self.layerIndex += 1
		elif firstWord == 'M101':
			self.addLinearMoveExtrusionDistanceLine((self.autoRetractDistance))
			if self.extrusionUnits != 'relative':
				self.gcode.addLine('G92 E0')
				self.totalExtrusionDistance = 0.0
			self.isExtruderActive = True
		elif firstWord == 'M103':
			self.retractionRatio = self.getRetractionRatio(lineIndex)
			self.addLinearMoveExtrusionDistanceLine(-self.autoRetractDistance)
			self.isExtruderActive = False
		elif firstWord == 'M108':
			self.flowRate = float(splitLine[1][1 :])
		self.gcode.addLine(line)
