"""
Fills the perimeters.

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from fabmetheus_utilities import archive, euclidean, gcodec, intercircle
from fabmetheus_utilities.vector3 import Vector3
import logging
import math
import sys

logger = logging.getLogger(__name__)
name = __name__

def performAction(gcode):
	'Fills the perimeters.'
	FillSkein(gcode).fill()
	
class FillSkein:
	'A class to fill a skein of extrusions.'
	def __init__(self, gcode):
		self.gcode = gcode
		self.extruderActive = False
		self.previousExtraShells = -1
		self.oldOrderedLocation = None
		
		self.activateFill = config.getboolean(name, 'active')
		self.infillSolidity = config.getfloat(name, 'infill.solidity.ratio')
		self.infillWidthOverThickness = config.getfloat(name, 'extrusion.lines.extra.spacer.scaler')
		self.infillPerimeterOverlap = config.getfloat(name, 'infill.overlap.over.perimeter.scaler')
		self.extraShellsAlternatingSolidLayer = config.getint(name, 'shells.alternating.solid')
		self.extraShellsBase = config.getint(name, 'shells.base')
		self.extraShellsSparseLayer = config.getint(name, 'shells.sparse')
		self.solidSurfaceThickness = config.getint(name, 'fully.filled.layers')
		self.doubleSolidSurfaceThickness = self.solidSurfaceThickness + self.solidSurfaceThickness
		self.startFromChoice = config.get(name, 'extrusion.sequence.start.layer')
		self.threadSequenceChoice = config.get(name, 'extrusion.sequence.print.order')
		self.threadSequence = self.threadSequenceChoice.split(",")
		self.infillPattern = config.get(name, 'infill.pattern')
		self.gridExtraOverlap = config.getfloat(name, 'grid.extra.overlap')
		self.diaphragmPeriod = config.getint(name, 'diaphragm.every.n.layers')
		self.diaphragmThickness = config.getint(name, 'diaphragm.thickness')
		self.infillBeginRotation = math.radians(config.getfloat(name, 'infill.rotation.begin'))
		self.infillBeginRotationRepeat = config.getint(name, 'infill.rotation.repeat')
		self.infillOddLayerExtraRotation = math.radians(config.getfloat(name, 'infill.rotation.odd.layer'))
		self.bridgeWidthMultiplier = config.getfloat('inset', 'bridge.width.multiplier.ratio')
		self.extrusionWidth = config.getfloat('carve', 'extrusion.width')
		self.infillWidth = self.extrusionWidth * self.infillWidthOverThickness * (0.7853)
		self.betweenWidth = self.extrusionWidth * self.infillWidthOverThickness * (0.7853)

	def fill(self):
		'Fills the layers.'
		if self.extrusionWidth == None:
			logger.warning('Nothing will be done because extrusion width FillSkein is None.')
			return

		for layerIndex in xrange(len(self.gcode.layers)):
			layer = self.gcode.layers.values()[layerIndex]
			self.addFill(layerIndex, layer)		
		
	def addFill(self, layerIndex, rotatedLayer):
		'Add fill to the carve layer.'
		alreadyFilledArounds = []
		pixelTable = {}
		arounds = []
		betweenWidth = self.extrusionWidth / 1.7594801994   # this really sucks I cant find hwe#(self.repository.infillWidthOverThickness.value * self.extrusionWidth *(0.7853))/1.5 #- 0.0866#todo todo TODO *0.5 is the distance between the outer loops..
		self.layerExtrusionWidth = self.infillWidth # spacing between fill lines
		layerFillInset = self.infillWidth  # the distance between perimeter incl loops and the fill pattern
		
		layerRotation = self.getLayerRotation(layerIndex, rotatedLayer)
		reverseRotation = complex(layerRotation.real, -layerRotation.imag)
		surroundingCarves = []
		layerRemainder = layerIndex % self.diaphragmPeriod
		extraShells = self.extraShellsSparseLayer
		
		if layerRemainder >= self.diaphragmThickness and rotatedLayer.bridgeRotation == None:
			for surroundingIndex in xrange(1, self.solidSurfaceThickness + 1):
				self.addRotatedCarve(layerIndex, -surroundingIndex, reverseRotation, surroundingCarves)
				self.addRotatedCarve(layerIndex, surroundingIndex, reverseRotation, surroundingCarves)

		if len(surroundingCarves) < self.doubleSolidSurfaceThickness:
			extraShells = self.extraShellsAlternatingSolidLayer
			if self.previousExtraShells != self.extraShellsBase:
				extraShells = self.extraShellsBase
		 
		if rotatedLayer.bridgeRotation != None:
			extraShells = 0
			betweenWidth *= self.bridgeWidthMultiplier#/0.7853  #todo check what is better with or without the normalizer
			self.layerExtrusionWidth *= self.bridgeWidthMultiplier
			layerFillInset *= self.bridgeWidthMultiplier
		 
		aroundInset = 0.25 * self.layerExtrusionWidth
		aroundWidth = 0.25 * self.layerExtrusionWidth
		self.previousExtraShells = extraShells
		gridPointInsetX = 0.5 * layerFillInset
		doubleExtrusionWidth = 2.0 * self.layerExtrusionWidth
		endpoints = []
		infillPaths = []
		layerInfillSolidity = self.infillSolidity
		
		self.isDoubleJunction = True
		self.isJunctionWide = True
		rotatedLoops = []

		nestedRings = rotatedLayer.nestedRings
				 
		createFillForSurroundings(nestedRings, betweenWidth, False)
		 
		for extraShellIndex in xrange(extraShells):
			createFillForSurroundings(nestedRings, self.layerExtrusionWidth, True)

		fillLoops = euclidean.getFillOfSurroundings(nestedRings, None)
		
		slightlyGreaterThanFill = 1.001 * layerFillInset #todo was 1.01 ACT 0.95  How much the parallel fill is filled
		 
		for loop in fillLoops:
			alreadyFilledLoop = []
			alreadyFilledArounds.append(alreadyFilledLoop)
			planeRotatedPerimeter = euclidean.getPointsRoundZAxis(reverseRotation, loop)
			rotatedLoops.append(planeRotatedPerimeter)
			centers = intercircle.getCentersFromLoop(planeRotatedPerimeter, slightlyGreaterThanFill)
			euclidean.addLoopToPixelTable(planeRotatedPerimeter, pixelTable, aroundWidth)
			for center in centers:
				alreadyFilledInset = intercircle.getSimplifiedInsetFromClockwiseLoop(center, layerFillInset)
				if intercircle.isLargeSameDirection(alreadyFilledInset, center, layerFillInset):
					alreadyFilledLoop.append(alreadyFilledInset)
					around = intercircle.getSimplifiedInsetFromClockwiseLoop(center, aroundInset)
					if euclidean.isPathInsideLoop(planeRotatedPerimeter, around) == euclidean.isWiddershins(planeRotatedPerimeter):
						around.reverse()
						arounds.append(around)
						euclidean.addLoopToPixelTable(around, pixelTable, aroundWidth)
		 
		if len(arounds) < 1:
			self.addThreadsBridgeLayer(layerIndex, nestedRings, rotatedLayer)
			return
		 
		back = euclidean.getBackOfLoops(arounds)
		front = euclidean.getFrontOfLoops(arounds)
		front = math.ceil(front / self.layerExtrusionWidth) * self.layerExtrusionWidth
		fillWidth = back - front
		numberOfLines = int(math.ceil(fillWidth / self.layerExtrusionWidth))
		self.frontOverWidth = 0.0
		self.horizontalSegmentLists = euclidean.getHorizontalSegmentListsFromLoopLists(alreadyFilledArounds, front, numberOfLines, rotatedLoops, self.layerExtrusionWidth)
		self.surroundingXIntersectionLists = []
		self.yList = []
		removedEndpoints = []
		 
		if len(surroundingCarves) >= self.doubleSolidSurfaceThickness:
			xIntersectionIndexLists = []
			self.frontOverWidth = euclidean.getFrontOverWidthAddXListYList(front, surroundingCarves, numberOfLines, xIntersectionIndexLists, self.layerExtrusionWidth, self.yList)
			for fillLine in xrange(len(self.horizontalSegmentLists)):
				xIntersectionIndexList = xIntersectionIndexLists[fillLine]
				surroundingXIntersections = euclidean.getIntersectionOfXIntersectionIndexes(self.doubleSolidSurfaceThickness, xIntersectionIndexList)
				self.surroundingXIntersectionLists.append(surroundingXIntersections)
				addSparseEndpoints(doubleExtrusionWidth, endpoints, fillLine, self.horizontalSegmentLists, layerInfillSolidity, removedEndpoints, self.solidSurfaceThickness, surroundingXIntersections)
		else:
			for fillLine in xrange(len(self.horizontalSegmentLists)):
				addSparseEndpoints(doubleExtrusionWidth, endpoints, fillLine, self.horizontalSegmentLists, layerInfillSolidity, removedEndpoints, self.solidSurfaceThickness, None)
		 
		paths = euclidean.getPathsFromEndpoints(endpoints, 5.0 * self.layerExtrusionWidth, pixelTable, aroundWidth)
		 
		oldRemovedEndpointLength = len(removedEndpoints) + 1
		 
		while oldRemovedEndpointLength - len(removedEndpoints) > 0:
			oldRemovedEndpointLength = len(removedEndpoints)
			removeEndpoints(pixelTable, self.layerExtrusionWidth, paths, removedEndpoints, aroundWidth)
		
		paths = euclidean.getConnectedPaths(paths, pixelTable, aroundWidth)
		 
		for path in paths:
			addPath(self.layerExtrusionWidth, infillPaths, path, layerRotation)

		for nestedRing in nestedRings:
			nestedRing.transferPaths(infillPaths)
		 
		self.addThreadsBridgeLayer(layerIndex, nestedRings, rotatedLayer)

	def addRotatedCarve(self, currentLayer, layerDelta, reverseRotation, surroundingCarves):
		'Add a rotated carve to the surrounding carves.'
		layerIndex = currentLayer + layerDelta
		if layerIndex < 0 or layerIndex >= len(self.gcode.layers):
			return
		
		layer = self.gcode.layers.values()[layerIndex]
		
		nestedRings = layer.nestedRings
		rotatedCarve = []
		for nestedRing in nestedRings:
			planeRotatedLoop = euclidean.getPointsRoundZAxis(reverseRotation, nestedRing.getXYBoundaries())
			rotatedCarve.append(planeRotatedLoop)
		outsetRadius = float(abs(layerDelta)) * self.extrusionWidth #todo investigate was   float(abs(layerDelta)) * self.layerThickness
		rotatedCarve = intercircle.getInsetSeparateLoopsFromLoops(-outsetRadius, rotatedCarve)
		surroundingCarves.append(rotatedCarve)

	def addThreadsBridgeLayer(self, layerIndex, nestedRings, rotatedLayer):
		'Add the threads, add the bridge end & the layer end tag.'
		if self.oldOrderedLocation == None or self.startFromChoice == "LowerLeft":
			self.oldOrderedLocation = getLowerLeftCorner(nestedRings)
		extrusionHalfWidth = 0.5 * self.layerExtrusionWidth
		threadSequence = self.threadSequence
		if layerIndex < 1:
			threadSequence = ['perimeter', 'loops', 'infill']
		#euclidean.addToThreadsRemove(extrusionHalfWidth, nestedRings, self.oldOrderedLocation, threadSequence)
		for nestedRing in nestedRings:
			nestedRing.addToThreads(extrusionHalfWidth, self.oldOrderedLocation, threadSequence)

	def getLayerRotation(self, layerIndex, rotatedLayer):
		'Get the layer rotation.'
		rotation = rotatedLayer.bridgeRotation
		if rotation != None:
			return rotation
		infillOddLayerRotationMultiplier = float(layerIndex % (self.infillBeginRotationRepeat + 1) == self.infillBeginRotationRepeat)
		layerAngle = self.infillBeginRotation + infillOddLayerRotationMultiplier * self.infillOddLayerExtraRotation
		return euclidean.getWiddershinsUnitPolar(layerAngle)

def addPath(infillWidth, infillPaths, path, rotationPlaneAngle):
	'Add simplified path to fill.'
	simplifiedPath = euclidean.getSimplifiedPath(path, infillWidth)
	if len(simplifiedPath) < 2:
		return
	planeRotated = euclidean.getPointsRoundZAxis(rotationPlaneAngle, simplifiedPath)
	infillPaths.append(planeRotated)

def addPointOnPath(path, pathIndex, pixelTable, point, pointIndex, width):
	'Add a point to a path and the pixel table.'
	pointIndexMinusOne = pointIndex - 1
	if pointIndex < len(path) and pointIndexMinusOne >= 0:
		segmentTable = {}
		begin = path[ pointIndexMinusOne ]
		end = path[pointIndex]
		euclidean.addValueSegmentToPixelTable(begin, end, segmentTable, pathIndex, width)
		euclidean.removePixelTableFromPixelTable(segmentTable, pixelTable)
	if pointIndexMinusOne >= 0:
		begin = path[ pointIndexMinusOne ]
		euclidean.addValueSegmentToPixelTable(begin, point, pixelTable, pathIndex, width)
	if pointIndex < len(path):
		end = path[pointIndex]
		euclidean.addValueSegmentToPixelTable(point, end, pixelTable, pathIndex, width)
	path.insert(pointIndex, point)

def addPointOnPathIfFree(path, pathIndex, pixelTable, point, pointIndex, width):
	'Add the closest point to a path, if the point added to a path is free.'
	if isAddedPointOnPathFree(path, pixelTable, point, pointIndex, width):
		addPointOnPath(path, pathIndex, pixelTable, point, pointIndex, width)

def addSparseEndpoints(doubleExtrusionWidth, endpoints, fillLine, horizontalSegmentLists, infillSolidity, removedEndpoints, solidSurfaceThickness, surroundingXIntersections):
	'Add sparse endpoints.'
	horizontalEndpoints = horizontalSegmentLists[fillLine]
	for segment in horizontalEndpoints:
		addSparseEndpointsFromSegment(doubleExtrusionWidth, endpoints, fillLine, horizontalSegmentLists, infillSolidity, removedEndpoints, segment, solidSurfaceThickness, surroundingXIntersections)

def addSparseEndpointsFromSegment(doubleExtrusionWidth, endpoints, fillLine, horizontalSegmentLists, infillSolidity, removedEndpoints, segment, solidSurfaceThickness, surroundingXIntersections):
	'Add sparse endpoints from a segment.'
	endpointFirstPoint = segment[0].point
	endpointSecondPoint = segment[1].point
	if surroundingXIntersections == None:
		endpoints += segment
		return
	if infillSolidity > 0.0:
		if fillLine < 1 or fillLine >= len(horizontalSegmentLists) - 1:
			endpoints += segment
			return
		if int(round(round(fillLine * infillSolidity) / infillSolidity)) == fillLine:
			endpoints += segment
			return
		if abs(endpointFirstPoint - endpointSecondPoint) < doubleExtrusionWidth:
			endpoints += segment
			return
		if not isSegmentAround(horizontalSegmentLists[ fillLine - 1 ], segment):
			endpoints += segment
			return
		if not isSegmentAround(horizontalSegmentLists[ fillLine + 1 ], segment):
			endpoints += segment
			return
	if solidSurfaceThickness == 0:
		removedEndpoints += segment
		return
	if isSegmentCompletelyInAnIntersection(segment, surroundingXIntersections):
		removedEndpoints += segment
		return
	endpoints += segment

def createExtraFillLoops(nestedRing, radius, shouldExtraLoopsBeAdded):
	'Create extra fill loops.'
	for innerNestedRing in nestedRing.innerNestedRings:
		createFillForSurroundings(innerNestedRing.innerNestedRings, radius, shouldExtraLoopsBeAdded)

	loopsToBeFilled = nestedRing.getLoopsToBeFilled()
	allFillLoops = getExtraFillLoops(loopsToBeFilled , radius)
	
	if len(allFillLoops) < 1:
		return
	if shouldExtraLoopsBeAdded:
		nestedRing.extraLoops += allFillLoops
		nestedRing.penultimateFillLoops = nestedRing.lastFillLoops
	nestedRing.lastFillLoops = allFillLoops

def createFillForSurroundings(nestedRings, radius, shouldExtraLoopsBeAdded):
	'Create extra fill loops for surrounding loops.'
	for nestedRing in nestedRings: 
		createExtraFillLoops(nestedRing, radius, shouldExtraLoopsBeAdded)

def getAdditionalLength(path, point, pointIndex):
	'Get the additional length added by inserting a point into a path.'
	if pointIndex == 0:
		return abs(point - path[0])
	if pointIndex == len(path):
		return abs(point - path[-1])
	return abs(point - path[pointIndex - 1]) + abs(point - path[pointIndex]) - abs(path[pointIndex] - path[pointIndex - 1])

def getExtraFillLoops(loops, radius):
	'Get extra loops between inside and outside loops. Extra perimeters'
	greaterThanRadius = radius / 0.7853  #todo was  *1.4 ACT (radius /0.7853)  how much the tight spots are covered by the extra loops
	extraFillLoops = []
	centers = intercircle.getCentersFromPoints(intercircle.getPointsFromLoops(loops, greaterThanRadius), greaterThanRadius)
	for center in centers:
		inset = intercircle.getSimplifiedInsetFromClockwiseLoop(center, radius)
		if intercircle.isLargeSameDirection(inset, center, radius):
			if euclidean.getIsInFilledRegion(loops, euclidean.getLeftPoint(inset)):
				inset.reverse()
				extraFillLoops.append(inset)
	return extraFillLoops

def getLowerLeftCorner(nestedRings):
	'Get the lower left corner from the nestedRings.'
	lowerLeftCorner = Vector3()
	lowestRealPlusImaginary = 987654321.0
	for nestedRing in nestedRings:
		for point in nestedRing.getXYBoundaries():
			realPlusImaginary = point.real + point.imag
			if realPlusImaginary < lowestRealPlusImaginary:
				lowestRealPlusImaginary = realPlusImaginary
				lowerLeftCorner.setToXYZ(point.real, point.imag, nestedRing.z)
	return lowerLeftCorner

def getWithLeastLength(path, point):
	'Insert a point into a path, at the index at which the path would be shortest.'
	if len(path) < 1:
		return 0
	shortestPointIndex = None
	shortestAdditionalLength = 999999999987654321.0
	for pointIndex in xrange(len(path) + 1):
		additionalLength = getAdditionalLength(path, point, pointIndex)
		if additionalLength < shortestAdditionalLength:
			shortestAdditionalLength = additionalLength
			shortestPointIndex = pointIndex
	return shortestPointIndex

def isAddedPointOnPathFree(path, pixelTable, point, pointIndex, width):
	'Determine if the point added to a path is intersecting the pixel table or the path.'
	if pointIndex > 0 and pointIndex < len(path):
		if isSharpCorner((path[pointIndex - 1]), point, (path[pointIndex])):
			return False
	pointIndexMinusOne = pointIndex - 1
	if pointIndexMinusOne >= 0:
		maskTable = {}
		begin = path[ pointIndexMinusOne ]
		if pointIndex < len(path):
			end = path[pointIndex]
			euclidean.addValueSegmentToPixelTable(begin, end, maskTable, None, width)
		segmentTable = {}
		euclidean.addSegmentToPixelTable(point, begin, segmentTable, 0.0, 2.0, width)
		if euclidean.isPixelTableIntersecting(pixelTable, segmentTable, maskTable):
			return False
		if isAddedPointOnPathIntersectingPath(begin, path, point, pointIndexMinusOne):
			return False
	if pointIndex < len(path):
		maskTable = {}
		begin = path[pointIndex]
		if pointIndexMinusOne >= 0:
			end = path[ pointIndexMinusOne ]
			euclidean.addValueSegmentToPixelTable(begin, end, maskTable, None, width)
		segmentTable = {}
		euclidean.addSegmentToPixelTable(point, begin, segmentTable, 0.0, 2.0, width)
		if euclidean.isPixelTableIntersecting(pixelTable, segmentTable, maskTable):
			return False
		if isAddedPointOnPathIntersectingPath(begin, path, point, pointIndex):
			return False
	return True

def isAddedPointOnPathIntersectingPath(begin, path, point, pointIndex):
	'Determine if the point added to a path is intersecting the path by checking line intersection.'
	segment = point - begin
	segmentLength = abs(segment)
	if segmentLength <= 0.0:
		return False
	normalizedSegment = segment / segmentLength
	segmentYMirror = complex(normalizedSegment.real, -normalizedSegment.imag)
	pointRotated = segmentYMirror * point
	beginRotated = segmentYMirror * begin
	if euclidean.isXSegmentIntersectingPath(path[ max(0, pointIndex - 20) : pointIndex ], pointRotated.real, beginRotated.real, segmentYMirror, pointRotated.imag):
		return True
	return euclidean.isXSegmentIntersectingPath(path[ pointIndex + 1 : pointIndex + 21 ], pointRotated.real, beginRotated.real, segmentYMirror, pointRotated.imag)

def isPointAddedAroundClosest(pixelTable, layerExtrusionWidth, paths, removedEndpointPoint, width):
	'Add the closest removed endpoint to the path, with minimal twisting.'
	closestDistanceSquared = 999999999987654321.0
	closestPathIndex = None
	for pathIndex in xrange(len(paths)):
		path = paths[ pathIndex ]
		for pointIndex in xrange(len(path)):
			point = path[pointIndex]
			distanceSquared = abs(point - removedEndpointPoint)
			if distanceSquared < closestDistanceSquared:
				closestDistanceSquared = distanceSquared
				closestPathIndex = pathIndex
	if closestPathIndex == None:
		return
	if closestDistanceSquared < 0.8 * layerExtrusionWidth ** 2 : #todo was 0.8 * layerExtrusionWidth ** 2   maybe 0.88617  the behaviour of fill ends  originally 0.8 * layerExtrusionWidth * layerExtrusionWidth:
		return
	closestPath = paths[ closestPathIndex ]
	closestPointIndex = getWithLeastLength(closestPath, removedEndpointPoint)
	if isAddedPointOnPathFree(closestPath, pixelTable, removedEndpointPoint, closestPointIndex, width):
		addPointOnPath(closestPath, closestPathIndex, pixelTable, removedEndpointPoint, closestPointIndex, width)
		return True
	return isSidePointAdded(pixelTable, closestPath, closestPathIndex, closestPointIndex, layerExtrusionWidth, removedEndpointPoint, width)

def isSegmentAround(aroundSegments, segment):
	'Determine if there is another segment around.'
	for aroundSegment in aroundSegments:
		endpoint = aroundSegment[0]
		if isSegmentInX(segment, endpoint.point.real, endpoint.otherEndpoint.point.real):
			return True
	return False

def isSegmentCompletelyInAnIntersection(segment, xIntersections):
	'Add sparse endpoints from a segment.'
	for xIntersectionIndex in xrange(0, len(xIntersections), 2):
		surroundingXFirst = xIntersections[ xIntersectionIndex ]
		surroundingXSecond = xIntersections[ xIntersectionIndex + 1 ]
		if euclidean.isSegmentCompletelyInX(segment, surroundingXFirst, surroundingXSecond):
			return True
	return False

def isSegmentInX(segment, xFirst, xSecond):
	'Determine if the segment overlaps within x.'
	segmentFirstX = segment[0].point.real
	segmentSecondX = segment[1].point.real
	if min(segmentFirstX, segmentSecondX) > max(xFirst, xSecond):
		return False
	return max(segmentFirstX, segmentSecondX) > min(xFirst, xSecond)

def isSharpCorner(beginComplex, centerComplex, endComplex):
	'Determine if the three complex points form a sharp corner.'
	centerBeginComplex = beginComplex - centerComplex
	centerEndComplex = endComplex - centerComplex
	centerBeginLength = abs(centerBeginComplex)
	centerEndLength = abs(centerEndComplex)
	if centerBeginLength <= 0.0 or centerEndLength <= 0.0:
		return False
	centerBeginComplex /= centerBeginLength
	centerEndComplex /= centerEndLength
	return euclidean.getDotProduct(centerBeginComplex, centerEndComplex) > 0.9

def isSidePointAdded(pixelTable, closestPath, closestPathIndex, closestPointIndex, layerExtrusionWidth, removedEndpointPoint, width):
	'Add side point along with the closest removed endpoint to the path, with minimal twisting.'
	if closestPointIndex <= 0 or closestPointIndex >= len(closestPath):
		return False
	pointBegin = closestPath[ closestPointIndex - 1 ]
	pointEnd = closestPath[ closestPointIndex ]
	removedEndpointPoint = removedEndpointPoint
	closest = pointBegin
	farthest = pointEnd
	removedMinusClosest = removedEndpointPoint - pointBegin
	removedMinusClosestLength = abs(removedMinusClosest)
	if removedMinusClosestLength <= 0.0:
		return False
	removedMinusOther = removedEndpointPoint - pointEnd
	removedMinusOtherLength = abs(removedMinusOther)
	if removedMinusOtherLength <= 0.0:
		return False
	insertPointAfter = None
	insertPointBefore = None
	if removedMinusOtherLength < removedMinusClosestLength:
		closest = pointEnd
		farthest = pointBegin
		removedMinusClosest = removedMinusOther
		removedMinusClosestLength = removedMinusOtherLength
		insertPointBefore = removedEndpointPoint
	else:
		insertPointAfter = removedEndpointPoint
	removedMinusClosestNormalized = removedMinusClosest / removedMinusClosestLength
	perpendicular = removedMinusClosestNormalized * complex(0.0, layerExtrusionWidth)
	sidePoint = removedEndpointPoint + perpendicular
	#extra check in case the line to the side point somehow slips by the line to the perpendicular
	sidePointOther = removedEndpointPoint - perpendicular
	if abs(sidePoint - farthest) > abs(sidePointOther - farthest):
		perpendicular = -perpendicular
		sidePoint = sidePointOther
	maskTable = {}
	closestSegmentTable = {}
	toPerpendicularTable = {}
	euclidean.addValueSegmentToPixelTable(pointBegin, pointEnd, maskTable, None, width)
	euclidean.addValueSegmentToPixelTable(closest, removedEndpointPoint, closestSegmentTable, None, width)
	euclidean.addValueSegmentToPixelTable(sidePoint, farthest, toPerpendicularTable, None, width)
	if euclidean.isPixelTableIntersecting(pixelTable, toPerpendicularTable, maskTable) or euclidean.isPixelTableIntersecting(closestSegmentTable, toPerpendicularTable, maskTable):
		sidePoint = removedEndpointPoint - perpendicular
		toPerpendicularTable = {}
		euclidean.addValueSegmentToPixelTable(sidePoint, farthest, toPerpendicularTable, None, width)
		if euclidean.isPixelTableIntersecting(pixelTable, toPerpendicularTable, maskTable) or euclidean.isPixelTableIntersecting(closestSegmentTable, toPerpendicularTable, maskTable):
			return False
	if insertPointBefore != None:
		addPointOnPathIfFree(closestPath, closestPathIndex, pixelTable, insertPointBefore, closestPointIndex, width)
	addPointOnPathIfFree(closestPath, closestPathIndex, pixelTable, sidePoint, closestPointIndex, width)
	if insertPointAfter != None:
		addPointOnPathIfFree(closestPath, closestPathIndex, pixelTable, insertPointAfter, closestPointIndex, width)
	return True

def removeEndpoints(pixelTable, layerExtrusionWidth, paths, removedEndpoints, aroundWidth):
	'Remove endpoints which are added to the path.'
	for removedEndpointIndex in xrange(len(removedEndpoints) - 1, -1, -1):
		removedEndpoint = removedEndpoints[ removedEndpointIndex ]
		removedEndpointPoint = removedEndpoint.point
		if isPointAddedAroundClosest(pixelTable, layerExtrusionWidth, paths, removedEndpointPoint, aroundWidth):
			removedEndpoints.remove(removedEndpoint)
