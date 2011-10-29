"""
Raft is a script to create a raft, elevate the nozzle and set the temperature.

Original author 
	'Enrique Perez (perez_enrique@yahoo.com) 
	modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
	
license 
	'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

"""

from fabmetheus_utilities.geometry.solids import triangle_mesh
from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from fabmetheus_utilities import intercircle
import math
import os
from config import config
import logging

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, text):
	'Raft the file or text.'
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return text
	return RaftSkein().getCraftedGcode(text)

def getCrossHatchPointLine(crossHatchPointLineTable, y):
	'Get the cross hatch point line.'
	if not crossHatchPointLineTable.has_key(y):
		crossHatchPointLineTable[ y ] = {}
	return crossHatchPointLineTable[ y ]

def getEndpointsFromYIntersections(x, yIntersections):
	'Get endpoints from the y intersections.'
	endpoints = []
	for yIntersectionIndex in xrange(0, len(yIntersections), 2):
		firstY = yIntersections[ yIntersectionIndex ]
		secondY = yIntersections[ yIntersectionIndex + 1 ]
		if firstY != secondY:
			firstComplex = complex(x, firstY)
			secondComplex = complex(x, secondY)
			endpointFirst = euclidean.Endpoint()
			endpointSecond = euclidean.Endpoint().getFromOtherPoint(endpointFirst, secondComplex)
			endpointFirst.getFromOtherPoint(endpointSecond, firstComplex)
			endpoints.append(endpointFirst)
			endpoints.append(endpointSecond)
	return endpoints

def getExtendedLineSegment(extensionDistance, lineSegment, loopXIntersections):
	'Get extended line segment.'
	pointBegin = lineSegment[0].point
	pointEnd = lineSegment[1].point
	segment = pointEnd - pointBegin
	segmentLength = abs(segment)
	if segmentLength <= 0.0:
		logger.error('This should never happen in getExtendedLineSegment in raft, the segment should have a length greater than zero. %s', lineSegment)
		return None
	segmentExtend = segment * extensionDistance / segmentLength
	lineSegment[0].point -= segmentExtend
	lineSegment[1].point += segmentExtend
	for loopXIntersection in loopXIntersections:
		setExtendedPoint(lineSegment[0], pointBegin, loopXIntersection)
		setExtendedPoint(lineSegment[1], pointEnd, loopXIntersection)
	return lineSegment

def getLoopsBySegmentsDictionary(segmentsDictionary, width):
	'Get loops from a horizontal segments dictionary.'
	points = []
	for endpoint in getVerticalEndpoints(segmentsDictionary, width, 0.1 * width, width):
		points.append(endpoint.point)
	for endpoint in euclidean.getEndpointsFromSegmentTable(segmentsDictionary):
		points.append(endpoint.point)
	return triangle_mesh.getDescendingAreaOrientedLoops(points, points, width + width)

def getVerticalEndpoints(horizontalSegmentsTable, horizontalStep, verticalOverhang, verticalStep):
	'Get vertical endpoints.'
	interfaceSegmentsTableKeys = horizontalSegmentsTable.keys()
	interfaceSegmentsTableKeys.sort()
	verticalTableTable = {}
	for interfaceSegmentsTableKey in interfaceSegmentsTableKeys:
		interfaceSegments = horizontalSegmentsTable[interfaceSegmentsTableKey]
		for interfaceSegment in interfaceSegments:
			begin = int(round(interfaceSegment[0].point.real / verticalStep))
			end = int(round(interfaceSegment[1].point.real / verticalStep))
			for stepIndex in xrange(begin, end + 1):
				if stepIndex not in verticalTableTable:
					verticalTableTable[stepIndex] = {}
				verticalTableTable[stepIndex][interfaceSegmentsTableKey] = None
	verticalTableTableKeys = verticalTableTable.keys()
	verticalTableTableKeys.sort()
	verticalEndpoints = []
	for verticalTableTableKey in verticalTableTableKeys:
		verticalTable = verticalTableTable[verticalTableTableKey]
		verticalTableKeys = verticalTable.keys()
		verticalTableKeys.sort()
		xIntersections = []
		for verticalTableKey in verticalTableKeys:
			y = verticalTableKey * horizontalStep
			if verticalTableKey - 1 not in verticalTableKeys:
				xIntersections.append(y - verticalOverhang)
			if verticalTableKey + 1 not in verticalTableKeys:
				xIntersections.append(y + verticalOverhang)
		for segment in euclidean.getSegmentsFromXIntersections(xIntersections, verticalTableTableKey * verticalStep):
			for endpoint in segment:
				endpoint.point = complex(endpoint.point.imag, endpoint.point.real)
				verticalEndpoints.append(endpoint)
	return verticalEndpoints

def setExtendedPoint(lineSegmentEnd, pointOriginal, x):
	'Set the point in the extended line segment.'
	if x > min(lineSegmentEnd.point.real, pointOriginal.real) and x < max(lineSegmentEnd.point.real, pointOriginal.real):
		lineSegmentEnd.point = complex(x, pointOriginal.imag)

class RaftSkein:
	'A class to raft a skein of extrusions.'
	def __init__(self):
		self.addLineLayerStart = True
		self.baseTemperature = None
		self.beginLoop = None
		self.boundaryLayers = []
		self.coolingRate = None
		self.gcode = gcodec.Gcode()
		self.extrusionStart = True
		self.extrusionTop = 0.0
		self.feedRateMinute = 961.0
		self.heatingRate = None
		self.insetTable = {}
		self.interfaceTemperature = None
		self.isPerimeterPath = False
		self.isStartupEarly = False
		self.isSurroundingLoop = True
		self.layerIndex = -1
		self.layerStarted = False
		self.layerThickness = 0.4
		self.lineIndex = 0
		self.lines = None
		self.isExtruderActive = False
		self.objectFirstLayerInfillTemperature = None
		self.objectFirstLayerPerimeterTemperature = None
		self.objectNextLayersTemperature = None
		self.oldFlowRateInput = 1.0
		self.oldFlowRateOutputString = None
		self.oldLocation = None
		self.oldTemperatureOutputString = None
		self.operatingFlowRate = None
		self.operatingLayerEndLine = '(<operatingLayerEnd> </operatingLayerEnd>)'
		self.operatingJump = None
		self.orbitalFeedRatePerSecond = 2.01
		self.perimeterWidth = 0.6
		self.supportFeedRate = 10
		self.supportFlowRate = None
		self.supportLayers = []
		self.supportLayersTemperature = None
		self.supportedLayersTemperature = None
		self.travelFeedRateMinute = 55
		
		self.activateRaft = config.getboolean(name, 'active')
		self.addRaftElevateNozzleOrbitSetAltitude = config.getboolean(name, 'add.raft.elevate.nozzle.orbit')
		self.supportChoice = config.get(name, 'support.location')
		self.supportMinimumAngle = config.getfloat(name, 'support.min.angle')
		self.minimumSupportRatio = math.tan(math.radians(self.supportMinimumAngle))
		self.supportCrossHatch = config.getboolean(name, 'support.crosshatch')
		self.interfaceInfillDensity = config.getfloat(name, 'interface.infill.density')
		self.interfaceLayerThicknessOverLayerThickness = config.getfloat(name, 'interface.layer.thickness.ratio')
		self.supportFeedRate = config.getfloat(name, 'support.feed.rate')
		self.supportFlowRateOverOperatingFlowRate = config.getfloat(name, 'support.flow.rate.ratio')
		self.supportGapOverPerimeterExtrusionWidth = config.getfloat(name, 'support.gap.over.perimeter.extrusion.width.ratio')
		self.raftAdditionalMarginOverLengthPercent = config.getfloat(name, 'support.extension.percent')
		self.raftMargin = config.getfloat(name, 'support.extension.distance')
		self.nameOfSupportEndFile = config.get(name, 'support.end.file')
		self.nameOfSupportStartFile = config.get(name, 'support.start.file')
		self.operatingNozzleLiftOverLayerThickness = config.getfloat(name, 'nozzle.clearance.ratio')
		self.objectFirstLayerFeedRateInfillMultiplier = config.getfloat(name, 'firstlayer.feed.rate')
		self.objectFirstLayerFeedRatePerimeterMultiplier = config.getfloat(name, 'firstlayer.feed.rate.perimeter')
		self.objectFirstLayerFlowRateInfillMultiplier = config.getfloat(name, 'firstlayer.flow.rate.infill')
		self.objectFirstLayerFlowRatePerimeterMultiplier = config.getfloat(name, 'firstlayer.flow.rate.perimeter')
		self.objectFirstLayerTravelSpeed = config.getfloat(name, 'firstlayer.travel.rate')
		self.interfaceLayers = config.getint(name, 'interface.layers')
		self.interfaceFeedRateMultiplier = config.getfloat(name, 'interface.feed.rate.ratio')
		self.interfaceFlowRateMultiplier = config.getfloat(name, 'interface.flow.rate.ratio')
		self.interfaceNozzleLiftOverInterfaceLayerThickness = config.getfloat(name, 'interface.nozzle.clearance.ratio')
		self.baseLayers = config.getint(name, 'base.layers')
		self.baseFeedRateMultiplier = config.getfloat(name, 'base.feed.rate.ratio')
		self.baseFlowRateMultiplier = config.getfloat(name, 'base.flow.rate.ratio')
		self.baseInfillDensity = config.getfloat(name, 'base.infill.density.ratio')
		self.baseLayerThicknessOverLayerThickness = config.getfloat(name, 'base.layer.thickness.ratio')
		self.baseNozzleLiftOverBaseLayerThickness = config.getfloat(name, 'base.nozzle.clearance.ratio')
		self.initialCircling = config.getboolean(name, 'initial.circling')
		self.infillOverhangOverExtrusionWidth = config.getfloat(name, 'infill.overhang.ratio')

	def addBaseLayer(self):
		'Add a base layer.'
		baseLayerThickness = self.layerThickness * self.baseLayerThicknessOverLayerThickness
		zCenter = self.extrusionTop + 0.5 * baseLayerThickness
		z = zCenter + baseLayerThickness * self.baseNozzleLiftOverBaseLayerThickness
		if len(self.baseEndpoints) < 1:
			print('This should never happen, the base layer has a size of zero.')
			return
		self.addLayerFromEndpoints(
			self.baseEndpoints,
			self.baseFeedRateMultiplier,
			self.baseFlowRateMultiplier,
			baseLayerThickness,
			self.baseLayerThicknessOverLayerThickness,
			self.baseStep,
			z)

	def addBaseSegments(self, baseExtrusionWidth):
		'Add the base segments.'
		baseOverhang = self.infillOverhangOverExtrusionWidth * baseExtrusionWidth
		self.baseEndpoints = getVerticalEndpoints(self.interfaceSegmentsTable, self.interfaceStep, baseOverhang, self.baseStep)

	def addEmptyLayerSupport(self, boundaryLayerIndex):
		'Add support material to a layer if it is empty.'
		supportLayer = SupportLayer([])
		self.supportLayers.append(supportLayer)
		if len(self.boundaryLayers[ boundaryLayerIndex ].loops) > 0:
			return
		aboveXIntersectionsTable = {}
		euclidean.addXIntersectionsFromLoopsForTable(self.getInsetLoopsAbove(boundaryLayerIndex), aboveXIntersectionsTable, self.interfaceStep)
		belowXIntersectionsTable = {}
		euclidean.addXIntersectionsFromLoopsForTable(self.getInsetLoopsBelow(boundaryLayerIndex), belowXIntersectionsTable, self.interfaceStep)
		supportLayer.xIntersectionsTable = euclidean.getIntersectionOfXIntersectionsTables([ aboveXIntersectionsTable, belowXIntersectionsTable ])

	def addFlowRateLineIfDifferent(self, flowRateOutputString):
		'Add a line of flow rate if different.'
		if self.operatingFlowRate == None:
			return
		if flowRateOutputString == self.oldFlowRateOutputString:
			return
		if flowRateOutputString != None:
			self.gcode.addLine('M108 S' + flowRateOutputString)
		self.oldFlowRateOutputString = flowRateOutputString

	def addFlowRateValueIfDifferent(self, flowRate):
		'Add a flow rate value if different.'
		if flowRate != None:
			self.addFlowRateLineIfDifferent(euclidean.getFourSignificantFigures(flowRate))

	def addInterfaceLayer(self):
		'Add an interface layer.'
		interfaceLayerThickness = self.layerThickness * self.interfaceLayerThicknessOverLayerThickness
		zCenter = self.extrusionTop + 0.5 * interfaceLayerThickness
		z = zCenter + interfaceLayerThickness * self.interfaceNozzleLiftOverInterfaceLayerThickness
		if len(self.interfaceEndpoints) < 1:
			logger.error('This should never happen, the interface layer has a size of zero.')
			return
		self.addLayerFromEndpoints(
			self.interfaceEndpoints,
			self.interfaceFeedRateMultiplier,
			self.interfaceFlowRateMultiplier,
			interfaceLayerThickness,
			self.interfaceLayerThicknessOverLayerThickness,
			self.interfaceStep,
			z)

	def addInterfaceTables(self, interfaceExtrusionWidth):
		'Add interface tables.'
		overhang = self.infillOverhangOverExtrusionWidth * interfaceExtrusionWidth
		self.interfaceEndpoints = []
		self.interfaceIntersectionsTableKeys = self.interfaceIntersectionsTable.keys()
		self.interfaceSegmentsTable = {}
		for yKey in self.interfaceIntersectionsTableKeys:
			self.interfaceIntersectionsTable[yKey].sort()
			y = yKey * self.interfaceStep
			lineSegments = euclidean.getSegmentsFromXIntersections(self.interfaceIntersectionsTable[yKey], y)
			xIntersectionIndexList = []
			for lineSegmentIndex in xrange(len(lineSegments)):
				lineSegment = lineSegments[lineSegmentIndex]
				endpointBegin = lineSegment[0]
				endpointEnd = lineSegment[1]
				endpointBegin.point = complex(self.baseStep * math.floor(endpointBegin.point.real / self.baseStep) - overhang, y)
				endpointEnd.point = complex(self.baseStep * math.ceil(endpointEnd.point.real / self.baseStep) + overhang, y)
				if endpointEnd.point.real > endpointBegin.point.real:
					euclidean.addXIntersectionIndexesFromSegment(lineSegmentIndex, lineSegment, xIntersectionIndexList)
			xIntersections = euclidean.getJoinOfXIntersectionIndexes(xIntersectionIndexList)
			joinedSegments = euclidean.getSegmentsFromXIntersections(xIntersections, y)
			if len(joinedSegments) > 0:
				self.interfaceSegmentsTable[yKey] = joinedSegments
			for joinedSegment in joinedSegments:
				self.interfaceEndpoints += joinedSegment

	def addLayerFromEndpoints(self, endpoints, feedRateMultiplier, flowRateMultiplier, layerLayerThickness, layerThicknessRatio, step, z):
		'Add a layer from endpoints and raise the extrusion top.'
		layerThicknessRatioSquared = layerThicknessRatio * layerThicknessRatio
		feedRateMinute = self.feedRateMinute * feedRateMultiplier / layerThicknessRatioSquared
		if len(endpoints) < 1:
			return
		aroundPixelTable = {}
		aroundWidth = 0.25 * step
		paths = euclidean.getPathsFromEndpoints(endpoints, 1.5 * step, aroundPixelTable, aroundWidth)
		self.addLayerLine(z)
		self.addFlowRateValueIfDifferent(flowRateMultiplier * self.oldFlowRateInput)
		for path in paths:
			simplifiedPath = euclidean.getSimplifiedPath(path, step)
			self.gcode.addGcodeFromFeedRateThreadZ(feedRateMinute, simplifiedPath, self.travelFeedRateMinute, z)
		self.extrusionTop += layerLayerThickness
		self.addFlowRateValueIfDifferent(self.oldFlowRateInput)

	def addLayerLine(self, z):
		'Add the layer gcode line and close the last layer gcode block.'
		if self.layerStarted:
			self.gcode.addLine('(</layer>)')
		self.gcode.addLine('(<layer> %s )' % self.gcode.getRounded(z)) # Indicate that a new layer is starting.
		if self.beginLoop != None:
			zBegin = self.extrusionTop + self.layerThickness
			intercircle.addOrbitsIfLarge(self.gcode, self.beginLoop, self.orbitalFeedRatePerSecond, self.temperatureChangeTimeBeforeRaft, zBegin)
			self.beginLoop = None
		self.layerStarted = True

	def addOperatingOrbits(self, boundaryLoops, pointComplex, temperatureChangeTime, z):
		'Add the orbits before the operating layers.'
		if len(boundaryLoops) < 1:
			return
		insetBoundaryLoops = intercircle.getInsetLoopsFromLoops(self.perimeterWidth, boundaryLoops)
		if len(insetBoundaryLoops) < 1:
			insetBoundaryLoops = boundaryLoops
		largestLoop = euclidean.getLargestLoop(insetBoundaryLoops)
		if pointComplex != None:
			largestLoop = euclidean.getLoopStartingNearest(self.perimeterWidth, pointComplex, largestLoop)
		intercircle.addOrbitsIfLarge(self.gcode, largestLoop, self.orbitalFeedRatePerSecond, temperatureChangeTime, z)

	def addRaft(self):
		'Add the raft.'
		if len(self.boundaryLayers) < 0:
			logger.error('This should never happen, there are no boundary layers in addRaft')
			return
		baseExtrusionWidth = self.perimeterWidth * self.baseLayerThicknessOverLayerThickness
		self.baseStep = baseExtrusionWidth / self.baseInfillDensity
		interfaceExtrusionWidth = self.perimeterWidth * self.interfaceLayerThicknessOverLayerThickness
		self.interfaceStep = interfaceExtrusionWidth / self.interfaceInfillDensity
		self.setCornersZ()
		self.cornerMinimumComplex = self.cornerMinimum.dropAxis()
		originalExtent = self.cornerMaximumComplex - self.cornerMinimumComplex
		self.raftOutsetRadius = self.raftMargin + (self.raftAdditionalMarginOverLengthPercent * 0.01) * max(originalExtent.real, originalExtent.imag)#todo ACT +0.1
		self.setBoundaryLayers()
		outsetSeparateLoops = intercircle.getInsetSeparateLoopsFromLoops(-self.raftOutsetRadius, self.boundaryLayers[0].loops, 0.8)
		self.interfaceIntersectionsTable = {}
		euclidean.addXIntersectionsFromLoopsForTable(outsetSeparateLoops, self.interfaceIntersectionsTable, self.interfaceStep)
		if len(self.supportLayers) > 0:
			supportIntersectionsTable = self.supportLayers[0].xIntersectionsTable
			euclidean.joinXIntersectionsTables(supportIntersectionsTable, self.interfaceIntersectionsTable)
		self.addInterfaceTables(interfaceExtrusionWidth)
		self.addRaftPerimeters()
		self.baseIntersectionsTable = {}
		complexRadius = complex(self.raftOutsetRadius, self.raftOutsetRadius)
		self.complexHigh = complexRadius + self.cornerMaximumComplex
		self.complexLow = self.cornerMinimumComplex - complexRadius
		self.beginLoop = euclidean.getSquareLoopWiddershins(self.cornerMinimumComplex, self.cornerMaximumComplex)
		if not intercircle.orbitsAreLarge(self.beginLoop, self.temperatureChangeTimeBeforeRaft):
			self.beginLoop = None
		if self.baseLayers > 0:
			self.addTemperatureLineIfDifferent(self.baseTemperature)
			self.addBaseSegments(baseExtrusionWidth)
		for baseLayerIndex in xrange(self.baseLayers):
			self.addBaseLayer()
		if self.interfaceLayers > 0:
			self.addTemperatureLineIfDifferent(self.interfaceTemperature)
		self.interfaceIntersectionsTableKeys.sort()
		for interfaceLayerIndex in xrange(self.interfaceLayers):
			self.addInterfaceLayer()
		self.operatingJump = self.extrusionTop + self.layerThickness * (self.operatingNozzleLiftOverLayerThickness + 0.5)
		for boundaryLayer in self.boundaryLayers:
			if self.operatingJump != None:
				boundaryLayer.z += self.operatingJump
		if self.baseLayers > 0 or self.interfaceLayers > 0:
			boundaryZ = self.boundaryLayers[0].z
			if self.layerStarted:
				self.gcode.addLine('(</layer>)')
				self.layerStarted = False
			self.gcode.addLine('(<raftLayerEnd> </raftLayerEnd>)')
			self.addLayerLine(boundaryZ)
			temperatureChangeTimeBeforeFirstLayer = self.getTemperatureChangeTime(self.objectFirstLayerPerimeterTemperature)
			self.addTemperatureLineIfDifferent(self.objectFirstLayerPerimeterTemperature)
			largestOutsetLoop = intercircle.getLargestInsetLoopFromLoop(euclidean.getLargestLoop(outsetSeparateLoops), -self.raftOutsetRadius)
			intercircle.addOrbitsIfLarge(self.gcode, largestOutsetLoop, self.orbitalFeedRatePerSecond, temperatureChangeTimeBeforeFirstLayer, boundaryZ)
			self.addLineLayerStart = False

	def addRaftPerimeters(self):
		'Add raft perimeters if there is a raft.'
		for supportLayer in self.supportLayers:
			supportSegmentTable = supportLayer.supportSegmentTable
			if len(supportSegmentTable) > 0:
				outset = 0.5 * self.perimeterWidth
				self.addRaftPerimetersByLoops(getLoopsBySegmentsDictionary(supportSegmentTable, self.interfaceStep), outset)
		if self.baseLayers < 1 and self.interfaceLayers < 1:
			return
		outset = (1.0 + self.infillOverhangOverExtrusionWidth) * self.perimeterWidth
		self.addRaftPerimetersByLoops(getLoopsBySegmentsDictionary(self.interfaceSegmentsTable, self.interfaceStep), outset)

	def addRaftPerimetersByLoops(self, loops, outset):
		'Add raft perimeters to the gcode for loops.'
		loops = intercircle.getInsetSeparateLoopsFromLoops(-outset, loops)
		for loop in loops:
			self.gcode.addLine('(<raftPerimeter>)')
			for point in loop:
				roundedX = self.gcode.getRounded(point.real)
				roundedY = self.gcode.getRounded(point.imag)
				self.gcode.addTagBracketedLine('raftPoint', 'X%s Y%s' % (roundedX, roundedY))
			self.gcode.addLine('(</raftPerimeter>)')

	def addSegmentTablesToSupportLayers(self):
		'Add segment tables to the support layers.'
		for supportLayer in self.supportLayers:
			supportLayer.supportSegmentTable = {}
			xIntersectionsTable = supportLayer.xIntersectionsTable
			for xIntersectionsTableKey in xIntersectionsTable:
				y = xIntersectionsTableKey * self.interfaceStep
				supportLayer.supportSegmentTable[ xIntersectionsTableKey ] = euclidean.getSegmentsFromXIntersections(xIntersectionsTable[ xIntersectionsTableKey ], y)

	def addSupportSegmentTable(self, layerIndex):
		'Add support segments from the boundary layers.'
		aboveLayer = self.boundaryLayers[ layerIndex + 1 ]
		aboveLoops = aboveLayer.loops
		supportLayer = self.supportLayers[layerIndex]
		if len(aboveLoops) < 1:
			return
		boundaryLayer = self.boundaryLayers[layerIndex]
		rise = aboveLayer.z - boundaryLayer.z
		outsetSupportLoops = intercircle.getInsetSeparateLoopsFromLoops(-self.minimumSupportRatio * rise, boundaryLayer.loops)
		numberOfSubSteps = 4
		subStepSize = self.interfaceStep / float(numberOfSubSteps)
		aboveIntersectionsTable = {}
		euclidean.addXIntersectionsFromLoopsForTable(aboveLoops, aboveIntersectionsTable, subStepSize)
		outsetIntersectionsTable = {}
		euclidean.addXIntersectionsFromLoopsForTable(outsetSupportLoops, outsetIntersectionsTable, subStepSize)
		euclidean.subtractXIntersectionsTable(aboveIntersectionsTable, outsetIntersectionsTable)
		for aboveIntersectionsTableKey in aboveIntersectionsTable.keys():
			supportIntersectionsTableKey = int(round(float(aboveIntersectionsTableKey) / numberOfSubSteps))
			xIntersectionIndexList = []
			if supportIntersectionsTableKey in supportLayer.xIntersectionsTable:
				euclidean.addXIntersectionIndexesFromXIntersections(0, xIntersectionIndexList, supportLayer.xIntersectionsTable[ supportIntersectionsTableKey ])
			euclidean.addXIntersectionIndexesFromXIntersections(1, xIntersectionIndexList, aboveIntersectionsTable[ aboveIntersectionsTableKey ])
			supportLayer.xIntersectionsTable[ supportIntersectionsTableKey ] = euclidean.getJoinOfXIntersectionIndexes(xIntersectionIndexList)

	def addSupportLayerTemperature(self, endpoints, z):
		'Add support layer and temperature before the object layer.'
		self.gcode.addLine('(<supportLayer>)')
		self.gcode.addLinesSetAbsoluteDistanceMode(self.supportStartLines)
		self.addTemperatureOrbits(endpoints, self.supportedLayersTemperature, z)
		aroundPixelTable = {}
		aroundWidth = 0.25 * self.interfaceStep
		boundaryLoops = self.boundaryLayers[self.layerIndex].loops
		halfSupportOutset = 0.5 * self.supportOutset
		aroundBoundaryLoops = intercircle.getAroundsFromLoops(boundaryLoops, halfSupportOutset)
		for aroundBoundaryLoop in aroundBoundaryLoops:
			euclidean.addLoopToPixelTable(aroundBoundaryLoop, aroundPixelTable, aroundWidth)
		paths = euclidean.getPathsFromEndpoints(endpoints, 1.5 * self.interfaceStep, aroundPixelTable, aroundWidth)
		feedRateMinuteMultiplied = self.supportFeedRate * 60
		supportFlowRateMultiplied = self.supportFlowRateOverOperatingFlowRate * self.supportFeedRate
		if self.layerIndex == 0:
			feedRateMinuteMultiplied = self.objectFirstLayerFeedRatePerimeterMultiplier * 60
			supportFlowRateMultiplied = self.objectFirstLayerFlowRatePerimeterMultiplier * self.objectFirstLayerFeedRatePerimeterMultiplier
			self.travelFeedRateMinute = self.objectFirstLayerTravelSpeed * 60
		self.addFlowRateValueIfDifferent(supportFlowRateMultiplied)
		for path in paths:
			self.gcode.addGcodeFromFeedRateThreadZ(feedRateMinuteMultiplied, path, self.travelFeedRateMinute, z)
		self.addFlowRateLineIfDifferent(str(self.oldFlowRateInput))
		self.addTemperatureOrbits(endpoints, self.supportLayersTemperature, z)
		self.gcode.addLinesSetAbsoluteDistanceMode(self.supportEndLines)
		self.gcode.addLine('(</supportLayer>)')

	def addTemperatureLineIfDifferent(self, temperature):
		'Add a line of temperature if different.'
		if temperature == None:
			return
		temperatureOutputString = euclidean.getRoundedToThreePlaces(temperature)
		if temperatureOutputString == self.oldTemperatureOutputString:
			return
		if temperatureOutputString != None:
			self.gcode.addLine('M104 S' + temperatureOutputString) # Set temperature.
		self.oldTemperatureOutputString = temperatureOutputString

	def addTemperatureOrbits(self, endpoints, temperature, z):
		'Add the temperature and orbits around the support layer.'
		if self.layerIndex < 0:
			return
		boundaryLoops = self.boundaryLayers[self.layerIndex].loops
		temperatureTimeChange = self.getTemperatureChangeTime(temperature)
		self.addTemperatureLineIfDifferent(temperature)
		if len(boundaryLoops) < 1:
			layerCornerHigh = complex(-987654321.0, -987654321.0)
			layerCornerLow = complex(987654321.0, 987654321.0)
			for endpoint in endpoints:
				layerCornerHigh = euclidean.getMaximum(layerCornerHigh, endpoint.point)
				layerCornerLow = euclidean.getMinimum(layerCornerLow, endpoint.point)
			squareLoop = euclidean.getSquareLoopWiddershins(layerCornerLow, layerCornerHigh)
			intercircle.addOrbitsIfLarge(self.gcode, squareLoop, self.orbitalFeedRatePerSecond, temperatureTimeChange, z)
			return
		perimeterInset = 0.4 * self.perimeterWidth
		insetBoundaryLoops = intercircle.getInsetLoopsFromLoops(perimeterInset, boundaryLoops)
		if len(insetBoundaryLoops) < 1:
			insetBoundaryLoops = boundaryLoops
		largestLoop = euclidean.getLargestLoop(insetBoundaryLoops)
		intercircle.addOrbitsIfLarge(self.gcode, largestLoop, self.orbitalFeedRatePerSecond, temperatureTimeChange, z)

	def addToFillXIntersectionIndexTables(self, supportLayer):
		'Add fill segments from the boundary layers.'
		supportLoops = supportLayer.supportLoops
		supportLayer.fillXIntersectionsTable = {}
		if len(supportLoops) < 1:
			return
		euclidean.addXIntersectionsFromLoopsForTable(supportLoops, supportLayer.fillXIntersectionsTable, self.interfaceStep)

	def extendXIntersections(self, loops, radius, xIntersectionsTable):
		'Extend the support segments.'
		xIntersectionsTableKeys = xIntersectionsTable.keys()
		for xIntersectionsTableKey in xIntersectionsTableKeys:
			lineSegments = euclidean.getSegmentsFromXIntersections(xIntersectionsTable[ xIntersectionsTableKey ], xIntersectionsTableKey)
			xIntersectionIndexList = []
			loopXIntersections = []
			euclidean.addXIntersectionsFromLoops(loops, loopXIntersections, xIntersectionsTableKey)
			for lineSegmentIndex in xrange(len(lineSegments)):
				lineSegment = lineSegments[ lineSegmentIndex ]
				extendedLineSegment = getExtendedLineSegment(radius, lineSegment, loopXIntersections)
				if extendedLineSegment != None:
					euclidean.addXIntersectionIndexesFromSegment(lineSegmentIndex, extendedLineSegment, xIntersectionIndexList)
			xIntersections = euclidean.getJoinOfXIntersectionIndexes(xIntersectionIndexList)
			if len(xIntersections) > 0:
				xIntersectionsTable[ xIntersectionsTableKey ] = xIntersections
			else:
				del xIntersectionsTable[ xIntersectionsTableKey ]

	def getCraftedGcode(self, gcodeText):
		'Parse gcode text and store the raft gcode.'
		
		if self.supportChoice != 'None':
			absoluteSupportEndFilePath = os.path.join( archive.getSkeinforgePath('alterations'),  self.nameOfSupportEndFile)
			self.supportEndLines = archive.getFileText(absoluteSupportEndFilePath)
			absoluteSupportStartFilePath = os.path.join( archive.getSkeinforgePath('alterations'),  self.nameOfSupportStartFile)
			self.supportStartLines = archive.getFileText(absoluteSupportStartFilePath)
		self.lines = archive.getTextLines(gcodeText)
		self.parseInitialization()
		self.temperatureChangeTimeBeforeRaft = 0.0
		if self.initialCircling:
			maxBaseInterfaceTemperature = max(self.baseTemperature, self.interfaceTemperature)
			firstMaxTemperature = max(maxBaseInterfaceTemperature, self.objectFirstLayerPerimeterTemperature)
			self.temperatureChangeTimeBeforeRaft = self.getTemperatureChangeTime(firstMaxTemperature)
		if self.addRaftElevateNozzleOrbitSetAltitude:
			self.addRaft()
		self.addTemperatureLineIfDifferent(self.objectFirstLayerPerimeterTemperature)
		for line in self.lines[self.lineIndex :]:
			self.parseLine(line)
		return self.gcode.output.getvalue()

	def getElevatedBoundaryLine(self, splitLine):
		'Get elevated boundary gcode line.'
		location = gcodec.getLocationFromSplitLine(None, splitLine)
		if self.operatingJump != None:
			location.z += self.operatingJump
		return self.gcode.getBoundaryLine(location)

	def getInsetLoops(self, boundaryLayerIndex):
		'Inset the support loops if they are not already inset.'
		if boundaryLayerIndex not in self.insetTable:
			self.insetTable[ boundaryLayerIndex ] = intercircle.getInsetSeparateLoopsFromLoops(self.quarterPerimeterWidth, self.boundaryLayers[ boundaryLayerIndex ].loops)
		return self.insetTable[ boundaryLayerIndex ]

	def getInsetLoopsAbove(self, boundaryLayerIndex):
		'Get the inset loops above the boundary layer index.'
		for aboveLayerIndex in xrange(boundaryLayerIndex + 1, len(self.boundaryLayers)):
			if len(self.boundaryLayers[ aboveLayerIndex ].loops) > 0:
				return self.getInsetLoops(aboveLayerIndex)
		return []

	def getInsetLoopsBelow(self, boundaryLayerIndex):
		'Get the inset loops below the boundary layer index.'
		for belowLayerIndex in xrange(boundaryLayerIndex - 1, -1, -1):
			if len(self.boundaryLayers[ belowLayerIndex ].loops) > 0:
				return self.getInsetLoops(belowLayerIndex)
		return []

	def getRaftedLine(self, splitLine):
		'Get elevated gcode line with operating feed rate.'
		location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
		self.feedRateMinute = gcodec.getFeedRateMinute(self.feedRateMinute, splitLine)
		feedRateMinuteMultiplied = self.feedRateMinute
		self.oldLocation = location
		z = location.z
		if self.operatingJump != None:
			z += self.operatingJump
		flowRate = self.oldFlowRateInput
		temperature = self.objectNextLayersTemperature
		if self.layerIndex == 0:
			if self.isExtruderActive:
				if self.isPerimeterPath:
					feedRateMinuteMultiplied = self.objectFirstLayerFeedRatePerimeterMultiplier * 60
					flowRate = self.objectFirstLayerFlowRatePerimeterMultiplier * self.objectFirstLayerFeedRatePerimeterMultiplier
					temperature = self.objectFirstLayerPerimeterTemperature
				else:
					feedRateMinuteMultiplied = self.objectFirstLayerFeedRateInfillMultiplier * 60
					flowRate = self.objectFirstLayerFlowRateInfillMultiplier * self.objectFirstLayerFeedRateInfillMultiplier
					temperature = self.objectFirstLayerInfillTemperature
			else:
				feedRateMinuteMultiplied = self.objectFirstLayerTravelSpeed * 60

		self.addFlowRateValueIfDifferent(flowRate)
		self.addTemperatureLineIfDifferent(temperature)
		return self.gcode.getLinearGcodeMovementWithFeedRate(feedRateMinuteMultiplied, location.dropAxis(), z)

	def getStepsUntilEnd(self, begin, end, stepSize):
		'Get steps from the beginning until the end.'
		step = begin
		steps = []
		while step < end:
			steps.append(step)
			step += stepSize
		return steps

	def getSupportEndpoints(self):
		'Get the support layer segments.'
		if len(self.supportLayers) <= self.layerIndex:
			return []
		supportSegmentTable = self.supportLayers[self.layerIndex].supportSegmentTable
		if self.layerIndex % 2 == 1 and self.supportCrossHatch:
			return getVerticalEndpoints(supportSegmentTable, self.interfaceStep, 0.1 * self.perimeterWidth, self.interfaceStep)
		return euclidean.getEndpointsFromSegmentTable(supportSegmentTable)

	def getTemperatureChangeTime(self, temperature):
		'Get the temperature change time.'
		if temperature == None:
			return 0.0
		oldTemperature = 25.0 # typical chamber temperature
		if self.oldTemperatureOutputString != None:
			oldTemperature = float(self.oldTemperatureOutputString)
		if temperature == oldTemperature:
			return 0.0
		if temperature > oldTemperature:
			return (temperature - oldTemperature) / self.heatingRate
		return (oldTemperature - temperature) / abs(self.coolingRate)

	def parseInitialization(self):
		'Parse gcode initialization and store the parameters.'
		for self.lineIndex in xrange(len(self.lines)):
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.gcode.parseSplitLine(firstWord, splitLine)
			if firstWord == '(<baseTemperature>':
				self.baseTemperature = float(splitLine[1])
			elif firstWord == '(<coolingRate>':
				self.coolingRate = float(splitLine[1])
			elif firstWord == '(</extruderInitialization>)':
				self.gcode.addLine('(<procedureName> raft </procedureName>)')
			elif firstWord == '(<heatingRate>':
				self.heatingRate = float(splitLine[1])
			elif firstWord == '(<interfaceTemperature>':
				self.interfaceTemperature = float(splitLine[1])
			elif firstWord == '(<layer>':
				return
			elif firstWord == '(<layerThickness>':
				self.layerThickness = float(splitLine[1])
			elif firstWord == '(<objectFirstLayerInfillTemperature>':
				self.objectFirstLayerInfillTemperature = float(splitLine[1])
			elif firstWord == '(<objectFirstLayerPerimeterTemperature>':
				self.objectFirstLayerPerimeterTemperature = float(splitLine[1])
			elif firstWord == '(<objectNextLayersTemperature>':
				self.objectNextLayersTemperature = float(splitLine[1])
			elif firstWord == '(<orbitalFeedRatePerSecond>':
				self.orbitalFeedRatePerSecond = float(splitLine[1])
			elif firstWord == '(<operatingFeedRatePerSecond>':
				self.feedRateMinute = 60.0 * float(splitLine[1])
			elif firstWord == '(<operatingFlowRate>':
				self.oldFlowRateInput = float(splitLine[1])
				self.operatingFlowRate = self.oldFlowRateInput
			elif firstWord == '(<perimeterWidth>':
				self.perimeterWidth = float(splitLine[1])
				self.quarterPerimeterWidth = 0.25 * self.perimeterWidth
				self.supportOutset = self.perimeterWidth * self.supportGapOverPerimeterExtrusionWidth #todo check ACT
				self.gcode.addTagBracketedLine('objectFirstLayerTravelSpeed', self.objectFirstLayerTravelSpeed)
			elif firstWord == '(<supportLayersTemperature>':
				self.supportLayersTemperature = float(splitLine[1])
			elif firstWord == '(<supportedLayersTemperature>':
				self.supportedLayersTemperature = float(splitLine[1])
			elif firstWord == '(<travelFeedRatePerSecond>':
				self.travelFeedRateMinute = 60.0 * float(splitLine[1])
			self.gcode.addLine(line)

	def parseLine(self, line):
		'Parse a gcode line and add it to the raft skein.'
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == 'G1':
			if self.extrusionStart:
				line = self.getRaftedLine(splitLine)
		elif firstWord == 'M101':
			self.isExtruderActive = True
			if self.isStartupEarly:
				self.isStartupEarly = False
				return
		elif firstWord == 'M103':
			self.isExtruderActive = False
		elif firstWord == 'M108':
			flowRateOutputString = splitLine[1][1 :]
			self.addFlowRateLineIfDifferent(flowRateOutputString)
			self.oldFlowRateInput = float(flowRateOutputString)
		elif firstWord == '(<boundaryPoint>':
			line = self.getElevatedBoundaryLine(splitLine)
		elif firstWord == '(</crafting>)':
			self.extrusionStart = False
			self.gcode.addLine(self.operatingLayerEndLine)
		elif firstWord == '(<layer>':
			#logger.info('%s layer count %s', name, self.layerIndex + 1)
			self.layerIndex += 1
			boundaryLayer = None
			layerZ = self.extrusionTop + float(splitLine[1])
			if len(self.boundaryLayers) > 0:
				boundaryLayer = self.boundaryLayers[self.layerIndex]
				layerZ = boundaryLayer.z
			if self.operatingJump != None:
				line = '(<layer> %s )' % self.gcode.getRounded(layerZ)
			if self.layerStarted and self.addLineLayerStart:
				self.gcode.addLine('(</layer>)')
			self.layerStarted = False
			if self.layerIndex > len(self.supportLayers) + 1:
				self.gcode.addLine(self.operatingLayerEndLine)
				self.operatingLayerEndLine = ''
			if self.addLineLayerStart:
				self.gcode.addLine(line)
			self.addLineLayerStart = True
			line = ''
			endpoints = self.getSupportEndpoints()
			if self.layerIndex == 1:
				if len(endpoints) < 1:
					temperatureChangeTimeBeforeNextLayers = self.getTemperatureChangeTime(self.objectNextLayersTemperature)
					self.addTemperatureLineIfDifferent(self.objectNextLayersTemperature)
					if self.addRaftElevateNozzleOrbitSetAltitude and len(boundaryLayer.loops) > 0:
						self.addOperatingOrbits(boundaryLayer.loops, euclidean.getXYComplexFromVector3(self.oldLocation), temperatureChangeTimeBeforeNextLayers, layerZ)
			if len(endpoints) > 0:
				self.addSupportLayerTemperature(endpoints, layerZ)
		elif firstWord == '(<perimeter>' or firstWord == '(<perimeterPath>)':
			self.isPerimeterPath = True
		elif firstWord == '(</perimeter>)' or firstWord == '(</perimeterPath>)':
			self.isPerimeterPath = False
		self.gcode.addLine(line)

	def setBoundaryLayers(self):
		'Set the boundary layers.'
		if self.supportChoice == 'None':
			return
		if len(self.boundaryLayers) < 2:
			return
		if self.supportChoice == 'EmptyLayersOnly':
			supportLayer = SupportLayer([])
			self.supportLayers.append(supportLayer)
			for boundaryLayerIndex in xrange(1, len(self.boundaryLayers) - 1):
				self.addEmptyLayerSupport(boundaryLayerIndex)
			self.truncateSupportSegmentTables()
			self.addSegmentTablesToSupportLayers()
			return
		for boundaryLayer in self.boundaryLayers:
			# thresholdRadius of 0.8 is needed to avoid the ripple inset bug http://hydraraptor.blogspot.com/2010/12/crackers.html
			supportLoops = intercircle.getInsetSeparateLoopsFromLoops(-self.supportOutset, boundaryLayer.loops, 0.8)
			supportLayer = SupportLayer(supportLoops)
			self.supportLayers.append(supportLayer)
		for supportLayerIndex in xrange(len(self.supportLayers) - 1):
			self.addSupportSegmentTable(supportLayerIndex)
		self.truncateSupportSegmentTables()
		for supportLayerIndex in xrange(len(self.supportLayers) - 1):
			boundaryLoops = self.boundaryLayers[supportLayerIndex].loops
			self.extendXIntersections(boundaryLoops, self.supportOutset, self.supportLayers[supportLayerIndex].xIntersectionsTable)
		for supportLayer in self.supportLayers:
			self.addToFillXIntersectionIndexTables(supportLayer)
		if self.supportChoice == 'ExteriorOnly':
			for supportLayerIndex in xrange(1, len(self.supportLayers)):
				self.subtractJoinedFill(supportLayerIndex)
		for supportLayer in self.supportLayers:
			euclidean.subtractXIntersectionsTable(supportLayer.xIntersectionsTable, supportLayer.fillXIntersectionsTable)
		for supportLayerIndex in xrange(len(self.supportLayers) - 2, -1, -1):
			xIntersectionsTable = self.supportLayers[supportLayerIndex].xIntersectionsTable
			aboveXIntersectionsTable = self.supportLayers[supportLayerIndex + 1].xIntersectionsTable
			euclidean.joinXIntersectionsTables(aboveXIntersectionsTable, xIntersectionsTable)
		for supportLayerIndex in xrange(len(self.supportLayers)):
			supportLayer = self.supportLayers[supportLayerIndex]
			self.extendXIntersections(supportLayer.supportLoops, self.raftOutsetRadius, supportLayer.xIntersectionsTable)
		for supportLayer in self.supportLayers:
			euclidean.subtractXIntersectionsTable(supportLayer.xIntersectionsTable, supportLayer.fillXIntersectionsTable)
		self.addSegmentTablesToSupportLayers()

	def setCornersZ(self):
		'Set maximum and minimum corners and z.'
		boundaryLoop = None
		boundaryLayer = None
		layerIndex = -1
		self.cornerMaximumComplex = complex(-912345678.0, -912345678.0)
		self.cornerMinimum = Vector3(912345678.0, 912345678.0, 912345678.0)
		self.firstLayerLoops = []
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
				self.cornerMaximumComplex = euclidean.getMaximum(self.cornerMaximumComplex, location.dropAxis())
				self.cornerMinimum.minimize(location)
			elif firstWord == '(<layer>':
				z = float(splitLine[1])
				boundaryLayer = euclidean.LoopLayer(z)
				self.boundaryLayers.append(boundaryLayer)
			elif firstWord == '(<layer>':
				layerIndex += 1
				if self.supportChoice == 'None':
					if layerIndex > 1:
						return

	def subtractJoinedFill(self, supportLayerIndex):
		'Join the fill then subtract it from the support layer table.'
		supportLayer = self.supportLayers[supportLayerIndex]
		fillXIntersectionsTable = supportLayer.fillXIntersectionsTable
		belowFillXIntersectionsTable = self.supportLayers[ supportLayerIndex - 1 ].fillXIntersectionsTable
		euclidean.joinXIntersectionsTables(belowFillXIntersectionsTable, supportLayer.fillXIntersectionsTable)
		euclidean.subtractXIntersectionsTable(supportLayer.xIntersectionsTable, supportLayer.fillXIntersectionsTable)

	def truncateSupportSegmentTables(self):
		'Truncate the support segments after the last support segment which contains elements.'
		for supportLayerIndex in xrange(len(self.supportLayers) - 1, -1, -1):
			if len(self.supportLayers[supportLayerIndex].xIntersectionsTable) > 0:
				self.supportLayers = self.supportLayers[ : supportLayerIndex + 1 ]
				return
		self.supportLayers = []


class SupportLayer:
	'Support loops with segment tables.'
	def __init__(self, supportLoops):
		self.supportLoops = supportLoops
		self.supportSegmentTable = {}
		self.xIntersectionsTable = {}

	def __repr__(self):
		'Get the string representation of this loop layer.'
		return '%s' % (self.supportLoops)
