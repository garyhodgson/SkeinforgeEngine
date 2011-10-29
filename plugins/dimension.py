"""
Dimension adds Adrian's extruder distance E value to the gcodeCodec movement lines, as described at:

Original author 
	'Enrique Perez (perez_enrique@yahoo.com) 
	modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
	
license 
	'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

"""

from config import config 
from fabmetheus_utilities import archive, euclidean, gcodec, intercircle
from fabmetheus_utilities.geometry.solids import triangle_mesh
import logging
import math

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, text, gcode):
	'Dimension a gcodeCodec file or text.'
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return text
	return DimensionSkein(gcode).getCraftedGcode(text)

class DimensionSkein:
	'A class to dimension a skein of extrusions.'
	def __init__(self, gcode):
		'Initialize.'
		self.absoluteDistanceMode = True
		self.boundaryLayers = []
		self.gcodeCodec = gcodec.Gcode()
		self.gcode = gcode
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
		
		self.activateDimension = config.getboolean(name, 'active')
		self.filamentDiameter = config.getfloat(name, 'filament.diameter')
		self.filamentPackingDensity = config.getfloat(name, 'filament.packing.density')
		self.activateCalibration = config.getboolean(name, 'calibrating.active')
		self.MeasuredXSection = config.getfloat(name, 'calibrating.x.section')
		self.oozeRate = config.getfloat(name, 'oozerate')
		self.extruderRetractionSpeed = config.getfloat(name, 'extruder.retraction.speed')
		self.extrusionUnitsRelative = config.getboolean(name, 'extrusion.units.relative')
		
		self.travelFeedRatePerSecond = config.getfloat('speed', 'feed.rate.travel')
		
		self.layerThickness = config.getfloat('carve', 'layer.height')
		self.feedRate = config.getfloat('speed', 'feed.rate')
		self.feedRateMinute = 60.0 * self.feedRate
		#self.operatingFlowRate = self.gcode.runtimeParameters.operatingFlowRate
		self.flowRate = self.feedRate * config.getfloat('speed', 'flow.rate.ratio')
		self.perimeterWidth = config.getfloat('carve', 'extrusion.width')
		self.absolutePositioning = config.getboolean('preface', 'positioning.absolute')
				

	def addLinearMoveExtrusionDistanceLine(self, extrusionDistance):
		'Get the extrusion distance string from the extrusion distance.'
		self.gcodeCodec.output.write('G1 F%s\n' % self.extruderRetractionSpeedMinuteString)
		self.gcodeCodec.output.write('G1%s\n' % self.getExtrusionDistanceStringFromExtrusionDistance(extrusionDistance))
		self.gcodeCodec.output.write('G1 F%s\n' % self.gcodeCodec.getRounded(self.feedRateMinute))

	def getCraftedGcode(self, gcodeText):
		'Parse gcodeCodec text and store the dimension gcodeCodec.'
		filamentRadius = 0.5 * self.filamentDiameter
		filamentPackingArea = math.pi * filamentRadius * filamentRadius * self.filamentPackingDensity
		self.doubleMinimumTravelForRetraction = 0
		self.lines = archive.getTextLines(gcodeText)
		#self.parseInitialization()
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
		#if self.operatingFlowRate == None:
		#	logger.warning('There is no operatingFlowRate so dimension will do nothing.')
		#	return gcodeText
		self.extruderRetractionSpeedMinuteString = self.gcodeCodec.getRounded(60.0 * self.extruderRetractionSpeed)
		if self.maximumZTravelFeedRatePerSecond != None and self.travelFeedRatePerSecond != None:
			self.zDistanceRatio = self.travelFeedRatePerSecond / self.maximumZTravelFeedRatePerSecond
		for lineIndex in xrange(self.lineIndex, len(self.lines)):
			self.parseLine(lineIndex)
		return self.gcodeCodec.output.getvalue()

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
		if self.absolutePositioning:
			location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
			if self.oldLocation != None:
				distance = abs(location - self.oldLocation)
			#print "location",location,"self.oldLocation",self.oldLocation, "distance",distance
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
		#print "getDistanceToNextThread lineIndex",lineIndex
		#print  "self.oldLocation",self.oldLocation
		if self.oldLocation == None:
			return
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
						return
					locationMinusOld = location - self.oldLocation
					#print "self.zDistanceRatio",self.zDistanceRatio
					self.autoRetractDistance = euclidean.calculateAutoRetractDistance(locationMinusOld, 
																					self.oozeRate, 
																					self.feedRateMinute, 
																					self.zDistanceRatio)
					
			elif firstWord == 'M101':
				isActive = True
			elif firstWord == 'M103':
				isActive = False	
	

	def getExtrusionDistanceString(self, distance, splitLine):
		'Get the extrusion distance string.'
		self.feedRateMinute = gcodec.getFeedRateMinute(self.feedRateMinute, splitLine)
		if not self.isExtruderActive:
			return ''
		if distance <= 0.0:
			return ''
		scaledFlowRate = self.flowRate * self.flowScaleSixty
		
		extrusionDistance = scaledFlowRate / self.feedRateMinute * distance
		#print "orig flowRate",self.flowRate, "scaledFlowRate",scaledFlowRate,"extrusionDistance",extrusionDistance, "distance",distance
		return self.getExtrusionDistanceStringFromExtrusionDistance(extrusionDistance)

	def getExtrusionDistanceStringFromExtrusionDistance(self, extrusionDistance):
		'Get the extrusion distance string from the extrusion distance.'
		if self.extrusionUnitsRelative:
			return ' E' + self.gcodeCodec.getRounded(extrusionDistance)
		self.totalExtrusionDistance += extrusionDistance
		return ' E' + self.gcodeCodec.getRounded(self.totalExtrusionDistance)

	def getRetractionRatio(self, lineIndex):
		'Get the retraction ratio.'
		self.getDistanceToNextThread(lineIndex)
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

	def parseLine(self, lineIndex):
		'Parse a gcodeCodec line and add it to the dimension skein.'
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
			if not self.extrusionUnitsRelative:
				self.gcodeCodec.addLine('M82')
			else: self.gcodeCodec.addLine('M83')
			self.layerIndex += 1
		elif firstWord == 'M101':
			self.addLinearMoveExtrusionDistanceLine((self.autoRetractDistance))
			if not self.extrusionUnitsRelative:
				self.gcodeCodec.addLine('G92 E0')
				self.totalExtrusionDistance = 0.0
			self.isExtruderActive = True
		elif firstWord == 'M103':
			self.retractionRatio = self.getRetractionRatio(lineIndex)
			
			self.addLinearMoveExtrusionDistanceLine(-self.autoRetractDistance)
			self.isExtruderActive = False
		elif firstWord == 'M108':
			self.flowRate = float(splitLine[1][1 :])
		self.gcodeCodec.addLine(line)
