"""
Support adds layers for supporting overhangs.
Extracted from the Skeinforge raft plugin. 

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html	
"""

from config import config
from fabmetheus_utilities import archive, euclidean, intercircle
from fabmetheus_utilities.geometry.solids import triangle_mesh
from fabmetheus_utilities.vector3 import Vector3
from entities import SupportPath
import logging
import math
import os

name = __name__
logger = logging.getLogger(name)

def performAction(slicedModel):
	"Add support layers."
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return
	SupportSkein(slicedModel).support()

class SupportSkein:
	'A class to support a skein of extrusions.'
	def __init__(self, slicedModel):
		self.slicedModel = slicedModel
		self.boundaryLayers = []
		self.supportLayers = []
		
		self.debug = config.getboolean(name, 'debug')
		self.supportLocation = config.get(name, 'location')
		self.supportMinimumAngle = config.getfloat(name, 'min.angle')
		self.minimumSupportRatio = math.tan(math.radians(self.supportMinimumAngle))
		self.supportCrossHatch = config.getboolean(name, 'crosshatch')
		self.supportFeedRate = config.getfloat('speed', 'feed.rate.support')
		self.supportFlowRateRatio = config.getfloat('speed', 'flow.rate.support.ratio')
		
		self.raftAdditionalMarginOverLengthPercent = config.getfloat(name, 'extension.percent')
		self.raftMargin = config.getfloat(name, 'extension.distance')
		self.infillOverhangOverExtrusionWidth = config.getfloat(name, 'infill.overhang.ratio')
		
		self.supportStartFile = config.get(name, 'support.start.file')
		self.supportEndFile = config.get(name, 'support.end.file')
		self.absoluteSupportStartFilePath = os.path.join('alterations', self.supportStartFile)
		self.absoluteSupportEndFilePath = os.path.join('alterations', self.supportEndFile)
		self.supportStartLines = archive.getTextLines(archive.getFileText(self.absoluteSupportStartFilePath, printWarning=False))
		self.supportEndLines = archive.getTextLines(archive.getFileText(self.absoluteSupportEndFilePath, printWarning=False))
	
		self.extrusionWidth = config.getfloat('carve', 'extrusion.width')
		self.supportGapOverPerimeterExtrusionWidth = config.getfloat(name, 'gap.over.perimeter.extrusion.width.ratio')
		self.supportOutset = self.extrusionWidth * self.supportGapOverPerimeterExtrusionWidth
		
		self.interfaceInfillDensity = config.getfloat(name, 'interface.infill.density')
		self.interfaceLayerThicknessRatio = config.getfloat(name, 'interface.layer.thickness.ratio')
		interfaceExtrusionWidth = self.extrusionWidth * self.interfaceLayerThicknessRatio
		self.interfaceStep = interfaceExtrusionWidth / self.interfaceInfillDensity		
		
		self.cornerMinimum = self.slicedModel.carvingCornerMinimum
		self.cornerMaximum = self.slicedModel.carvingCornerMaximum
		self.cornerMinimumComplex = self.cornerMinimum.dropAxis()
		self.cornerMaximumComplex = self.cornerMaximum.dropAxis() 

	def support(self):
		'Add support layers to sliced model'
		
		for layer in self.slicedModel.layers:
			perimeters = []
			layer.getPerimeterPaths(perimeters)
			boundaryLayer = euclidean.LoopLayer(layer.z) # TODO refactor out
			for perimeter in perimeters:				
				boundaryLoop = []
				boundaryLayer.loops.append(boundaryLoop)
				for boundaryPoint in perimeter.boundaryPoints:
					boundaryLoop.append(boundaryPoint.dropAxis())
			self.boundaryLayers.append(boundaryLayer)
			
		if len(self.boundaryLayers) < 0:
			logger.error('This should never happen, there are no boundary layers in support')
			return
		
		originalExtent = self.cornerMaximumComplex - self.cornerMinimumComplex
		self.raftOutsetRadius = self.raftMargin + (self.raftAdditionalMarginOverLengthPercent * 0.01) * max(originalExtent.real, originalExtent.imag)#todo ACT +0.1
		self.setBoundaryLayers()

		for layer in self.slicedModel.layers:
			endpoints = self.getSupportEndpoints(layer.index)
			if len(endpoints) > 0:
				self.addSupportLayer(endpoints, layer)
	
	def getSupportEndpoints(self, layerIndex):
		'Get the support layer segments.'
		if len(self.supportLayers) <= layerIndex:
			return []
		supportSegmentTable = self.supportLayers[layerIndex].supportSegmentTable
		if layerIndex % 2 == 1 and self.supportCrossHatch:
			return getVerticalEndpoints(supportSegmentTable, self.interfaceStep, 0.1 * self.extrusionWidth, self.interfaceStep)
		return euclidean.getEndpointsFromSegmentTable(supportSegmentTable)
	
	def setBoundaryLayers(self):
		'Set the boundary layers.'
		
		if len(self.boundaryLayers) < 2:
			return
		
		if self.supportLocation == 'EmptyLayersOnly':
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
				

		for supportLayerIndex in xrange(len(self.supportLayers) -1 ):
			self.addSupportSegmentTable(supportLayerIndex)
		
		self.truncateSupportSegmentTables()
		
		for supportLayerIndex in xrange(len(self.supportLayers) - 1):
			boundaryLoops = self.boundaryLayers[supportLayerIndex].loops
			self.extendXIntersections(boundaryLoops, self.supportOutset, self.supportLayers[supportLayerIndex].xIntersectionsTable)
			
		for supportLayer in self.supportLayers:
			self.addToFillXIntersectionIndexTables(supportLayer)
			
		if self.supportLocation == 'ExteriorOnly':
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
	
	def addSupportLayer(self, endpoints, layer):
		'Add support layer before the object layer.'
		
		# TODO refactor to parent object - avoid duplication
		for line in self.supportStartLines:
			layer.preSupportGcodeCommands.append(line)
		
		aroundPixelTable = {}
		aroundWidth = 0.25 * self.interfaceStep
		boundaryLoops = self.boundaryLayers[layer.index].loops
		halfSupportOutset = 0.5 * self.supportOutset
		aroundBoundaryLoops = intercircle.getAroundsFromLoops(boundaryLoops, halfSupportOutset)
		for aroundBoundaryLoop in aroundBoundaryLoops:
			euclidean.addLoopToPixelTable(aroundBoundaryLoop, aroundPixelTable, aroundWidth)
		paths = euclidean.getPathsFromEndpoints(endpoints, 1.5 * self.interfaceStep, aroundPixelTable, aroundWidth)
		feedRateMinuteMultiplied = self.supportFeedRate * 60
		supportFlowRateMultiplied = self.supportFlowRateRatio * self.supportFeedRate
		
		for path in paths:
			supportPath = SupportPath(layer.z, self.slicedModel.runtimeParameters)
			supportPath.addPath(path)
			layer.supportPaths.append(supportPath)

		layer.postSupportGcodeCommands.extend(self.supportEndLines)
	
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

	def addSegmentTablesToSupportLayers(self):
		'Add segment tables to the support layers.'
		for supportLayer in self.supportLayers:
			supportLayer.supportSegmentTable = {}
			xIntersectionsTable = supportLayer.xIntersectionsTable
			for xIntersectionsTableKey in xIntersectionsTable:
				y = xIntersectionsTableKey * self.interfaceStep
				supportLayer.supportSegmentTable[ xIntersectionsTableKey ] = euclidean.getSegmentsFromXIntersections(xIntersectionsTable[ xIntersectionsTableKey ], y)

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

class SupportLayer:
	'Support loops with segment tables.'
	def __init__(self, supportLoops):
		self.supportLoops = supportLoops
		self.supportSegmentTable = {}
		self.xIntersectionsTable = {}

	def __repr__(self):
		'Get the string representation of this loop layer.'
		return '%s' % (self.supportLoops)