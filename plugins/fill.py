"""
Fill is a script to fill the perimeters of a gcode file.
"""

from fabmetheus_utilities.geometry.solids import triangle_mesh
from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from fabmetheus_utilities import intercircle
import math
import sys
import logging
from config import config

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modified by Action68 (ahmetcemturan@gmail.com) SFACT home at reprafordummies.net'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__


def getCraftedText(fileName, gcodeText=''):
	'Fill the inset file or gcode text.'
	gcodeText = archive.getTextIfEmpty(fileName, gcodeText)
	if gcodec.isProcedureDoneOrFileIsEmpty(gcodeText, 'fill'):
		return gcodeText
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return gcodeText
	return FillSkein().getCraftedGcode(gcodeText)

def addAroundGridPoint(arounds, gridPoint, gridPointInsetX, gridPointInsetY, gridPoints, gridSearchRadius, isBothOrNone, isDoubleJunction, isJunctionWide, paths, pixelTable, width):
	'Add the path around the grid point.'
	closestPathIndex = None
	aroundIntersectionPaths = []
	for aroundIndex in xrange(len(arounds)):
		loop = arounds[ aroundIndex ]
		for pointIndex in xrange(len(loop)):
			pointFirst = loop[pointIndex]
			pointSecond = loop[(pointIndex + 1) % len(loop)]
			yIntersection = euclidean.getYIntersectionIfExists(pointFirst, pointSecond, gridPoint.real)
			addYIntersectionPathToList(aroundIndex, pointIndex, gridPoint.imag, yIntersection, aroundIntersectionPaths)
	if len(aroundIntersectionPaths) < 2:
		logger.error('This should never happen, aroundIntersectionPaths is less than 2 in fill.')
		return
	yCloseToCenterArounds = getClosestOppositeIntersectionPaths(aroundIntersectionPaths)
	if len(yCloseToCenterArounds) < 2:
		return
	segmentFirstY = min(yCloseToCenterArounds[0].y, yCloseToCenterArounds[1].y)
	segmentSecondY = max(yCloseToCenterArounds[0].y, yCloseToCenterArounds[1].y)
	yIntersectionPaths = []
	gridPixel = euclidean.getStepKeyFromPoint(gridPoint / width)
	segmentFirstPixel = euclidean.getStepKeyFromPoint(complex(gridPoint.real, segmentFirstY) / width)
	segmentSecondPixel = euclidean.getStepKeyFromPoint(complex(gridPoint.real, segmentSecondY) / width)
	pathIndexTable = {}
	addPathIndexFirstSegment(gridPixel, pathIndexTable, pixelTable, segmentFirstPixel)
	addPathIndexSecondSegment(gridPixel, pathIndexTable, pixelTable, segmentSecondPixel)
	for pathIndex in pathIndexTable.keys():
		path = paths[ pathIndex ]
		for pointIndex in xrange(len(path) - 1):
			pointFirst = path[pointIndex]
			pointSecond = path[pointIndex + 1]
			yIntersection = getYIntersectionInsideYSegment(segmentFirstY, segmentSecondY, pointFirst, pointSecond, gridPoint.real)
			addYIntersectionPathToList(pathIndex, pointIndex, gridPoint.imag, yIntersection, yIntersectionPaths)
	if len(yIntersectionPaths) < 1:
		return
	yCloseToCenterPaths = []
	if isDoubleJunction:
		yCloseToCenterPaths = getClosestOppositeIntersectionPaths(yIntersectionPaths)
	else:
		yIntersectionPaths.sort(compareDistanceFromCenter)
		yCloseToCenterPaths = [ yIntersectionPaths[0] ]
	for yCloseToCenterPath in yCloseToCenterPaths:
		setIsOutside(yCloseToCenterPath, aroundIntersectionPaths)
	if len(yCloseToCenterPaths) < 2:
		yCloseToCenterPaths[0].gridPoint = gridPoint
		insertGridPointPair(gridPoint, gridPointInsetX, gridPoints, isJunctionWide, paths, pixelTable, yCloseToCenterPaths[0], width)
		return
	plusMinusSign = getPlusMinusSign(yCloseToCenterPaths[1].y - yCloseToCenterPaths[0].y)
	yCloseToCenterPaths[0].gridPoint = complex(gridPoint.real, gridPoint.imag - plusMinusSign * gridPointInsetY)
	yCloseToCenterPaths[1].gridPoint = complex(gridPoint.real, gridPoint.imag + plusMinusSign * gridPointInsetY)
	yCloseToCenterPaths.sort(comparePointIndexDescending)
	insertGridPointPairs(gridPoint, gridPointInsetX, gridPoints, yCloseToCenterPaths[0], yCloseToCenterPaths[1], isBothOrNone, isJunctionWide, paths, pixelTable, width)

def addLoop(infillWidth, infillPaths, loop, rotationPlaneAngle):
	'Add simplified path to fill.'
	simplifiedLoop = euclidean.getSimplifiedLoop(loop, infillWidth)
	if len(simplifiedLoop) < 2:
		return
	simplifiedLoop.append(simplifiedLoop[0])
	planeRotated = euclidean.getPointsRoundZAxis(rotationPlaneAngle, simplifiedLoop)
	infillPaths.append(planeRotated)

def addPath(infillWidth, infillPaths, path, rotationPlaneAngle):
	'Add simplified path to fill.'
	simplifiedPath = euclidean.getSimplifiedPath(path, infillWidth)
	if len(simplifiedPath) < 2:
		return
	planeRotated = euclidean.getPointsRoundZAxis(rotationPlaneAngle, simplifiedPath)
	infillPaths.append(planeRotated)

def addPathIndexFirstSegment(gridPixel, pathIndexTable, pixelTable, segmentFirstPixel):
	'Add the path index of the closest segment found toward the second segment.'
	for yStep in xrange(gridPixel[1], segmentFirstPixel[1] - 1, -1):
		if getKeyIsInPixelTableAddValue((gridPixel[0], yStep), pathIndexTable, pixelTable):
			return

def addPathIndexSecondSegment(gridPixel, pathIndexTable, pixelTable, segmentSecondPixel):
	'Add the path index of the closest segment found toward the second segment.'
	for yStep in xrange(gridPixel[1], segmentSecondPixel[1] + 1):
		if getKeyIsInPixelTableAddValue((gridPixel[0], yStep), pathIndexTable, pixelTable):
			return

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

def addYIntersectionPathToList(pathIndex, pointIndex, y, yIntersection, yIntersectionPaths):
	'Add the y intersection path to the y intersection paths.'
	if yIntersection == None:
		return
	yIntersectionPath = YIntersectionPath(pathIndex, pointIndex, yIntersection)
	yIntersectionPath.yMinusCenter = yIntersection - y
	yIntersectionPaths.append(yIntersectionPath)

def compareDistanceFromCenter(self, other):
	'Get comparison in order to sort y intersections in ascending order of distance from the center.'
	distanceFromCenter = abs(self.yMinusCenter)
	distanceFromCenterOther = abs(other.yMinusCenter)
	if distanceFromCenter > distanceFromCenterOther:
		return 1
	if distanceFromCenter < distanceFromCenterOther:
		return -1
	return 0

def comparePointIndexDescending(self, other):
	'Get comparison in order to sort y intersections in descending order of point index.'
	if self.pointIndex > other.pointIndex:
		return -1
	if self.pointIndex < other.pointIndex:
		return 1
	return 0

def createExtraFillLoops(nestedRing, radius, shouldExtraLoopsBeAdded):
	'Create extra fill loops.'
	for innerNestedRing in nestedRing.innerNestedRings:
		createFillForSurroundings(innerNestedRing.innerNestedRings, radius, shouldExtraLoopsBeAdded)
	allFillLoops = getExtraFillLoops(nestedRing.getLoopsToBeFilled(), radius)
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

def getClosestOppositeIntersectionPaths(yIntersectionPaths):
	'Get the close to center paths, starting with the first and an additional opposite if it exists.'
	yIntersectionPaths.sort(compareDistanceFromCenter)
	beforeFirst = yIntersectionPaths[0].yMinusCenter < 0.0
	yCloseToCenterPaths = [ yIntersectionPaths[0] ]
	for yIntersectionPath in yIntersectionPaths[1 :]:
		beforeSecond = yIntersectionPath.yMinusCenter < 0.0
		if beforeFirst != beforeSecond:
			yCloseToCenterPaths.append(yIntersectionPath)
			return yCloseToCenterPaths
	return yCloseToCenterPaths

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

def getKeyIsInPixelTableAddValue(key, pathIndexTable, pixelTable):
	'Determine if the key is in the pixel table, and if it is and if the value is not None add it to the path index table.'
	if key in pixelTable:
		value = pixelTable[key]
		if value != None:
			pathIndexTable[value] = None
		return True
	return False

def getLowerLeftCorner(nestedRings):
	'Get the lower left corner from the nestedRings.'
	lowerLeftCorner = Vector3()
	lowestRealPlusImaginary = 987654321.0
	for nestedRing in nestedRings:
		for point in nestedRing.boundary:
			realPlusImaginary = point.real + point.imag
			if realPlusImaginary < lowestRealPlusImaginary:
				lowestRealPlusImaginary = realPlusImaginary
				lowerLeftCorner.setToXYZ(point.real, point.imag, nestedRing.z)
	return lowerLeftCorner

def getNonIntersectingGridPointLine(gridPointInsetX, isJunctionWide, paths, pixelTable, yIntersectionPath, width):
	'Get the points around the grid point that is junction wide that do not intersect.'
	pointIndexPlusOne = yIntersectionPath.getPointIndexPlusOne()
	path = yIntersectionPath.getPath(paths)
	begin = path[ yIntersectionPath.pointIndex ]
	end = path[ pointIndexPlusOne ]
	plusMinusSign = getPlusMinusSign(end.real - begin.real)
	if isJunctionWide:
		gridPointXFirst = complex(yIntersectionPath.gridPoint.real - plusMinusSign * gridPointInsetX, yIntersectionPath.gridPoint.imag)
		gridPointXSecond = complex(yIntersectionPath.gridPoint.real + plusMinusSign * gridPointInsetX, yIntersectionPath.gridPoint.imag)
		if isAddedPointOnPathFree(path, pixelTable, gridPointXSecond, pointIndexPlusOne, width):
			if isAddedPointOnPathFree(path, pixelTable, gridPointXFirst, pointIndexPlusOne, width):
				return [ gridPointXSecond, gridPointXFirst ]
			if isAddedPointOnPathFree(path, pixelTable, yIntersectionPath.gridPoint, pointIndexPlusOne, width):
				return [ gridPointXSecond, yIntersectionPath.gridPoint ]
			return [ gridPointXSecond ]
	if isAddedPointOnPathFree(path, pixelTable, yIntersectionPath.gridPoint, pointIndexPlusOne, width):
		return [ yIntersectionPath.gridPoint ]
	return []

def getPlusMinusSign(number):
	'Get one if the number is zero or positive else negative one.'
	if number >= 0.0:
		return 1.0
	return -1.0

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

def getYIntersectionInsideYSegment(segmentFirstY, segmentSecondY, beginComplex, endComplex, x):
	'Get the y intersection inside the y segment if it does, else none.'
	yIntersection = euclidean.getYIntersectionIfExists(beginComplex, endComplex, x)
	if yIntersection == None:
		return None
	if yIntersection < min(segmentFirstY, segmentSecondY):
		return None
	if yIntersection <= max(segmentFirstY, segmentSecondY):
		return yIntersection
	return None

def insertGridPointPair(gridPoint, gridPointInsetX, gridPoints, isJunctionWide, paths, pixelTable, yIntersectionPath, width):
	'Insert a pair of points around the grid point is is junction wide, otherwise inset one point.'
	linePath = getNonIntersectingGridPointLine(gridPointInsetX, isJunctionWide, paths, pixelTable, yIntersectionPath, width)
	insertGridPointPairWithLinePath(gridPoint, gridPointInsetX, gridPoints, isJunctionWide, linePath, paths, pixelTable, yIntersectionPath, width)

def insertGridPointPairs(gridPoint, gridPointInsetX, gridPoints, intersectionPathFirst, intersectionPathSecond, isBothOrNone, isJunctionWide, paths, pixelTable, width):
	'Insert a pair of points around a pair of grid points.'
	gridPointLineFirst = getNonIntersectingGridPointLine(gridPointInsetX, isJunctionWide, paths, pixelTable, intersectionPathFirst, width)
	if len(gridPointLineFirst) < 1:
		if isBothOrNone:
			return
		intersectionPathSecond.gridPoint = gridPoint
		insertGridPointPair(gridPoint, gridPointInsetX, gridPoints, isJunctionWide, paths, pixelTable, intersectionPathSecond, width)
		return
	gridPointLineSecond = getNonIntersectingGridPointLine(gridPointInsetX, isJunctionWide, paths, pixelTable, intersectionPathSecond, width)
	if len(gridPointLineSecond) > 0:
		insertGridPointPairWithLinePath(gridPoint, gridPointInsetX, gridPoints, isJunctionWide, gridPointLineFirst, paths, pixelTable, intersectionPathFirst, width)
		insertGridPointPairWithLinePath(gridPoint, gridPointInsetX, gridPoints, isJunctionWide, gridPointLineSecond, paths, pixelTable, intersectionPathSecond, width)
		return
	if isBothOrNone:
		return
	originalGridPointFirst = intersectionPathFirst.gridPoint
	intersectionPathFirst.gridPoint = gridPoint
	gridPointLineFirstCenter = getNonIntersectingGridPointLine(gridPointInsetX, isJunctionWide, paths, pixelTable, intersectionPathFirst, width)
	if len(gridPointLineFirstCenter) > 0:
		insertGridPointPairWithLinePath(gridPoint, gridPointInsetX, gridPoints, isJunctionWide, gridPointLineFirstCenter, paths, pixelTable, intersectionPathFirst, width)
		return
	intersectionPathFirst.gridPoint = originalGridPointFirst
	insertGridPointPairWithLinePath(gridPoint, gridPointInsetX, gridPoints, isJunctionWide, gridPointLineFirst, paths, pixelTable, intersectionPathFirst, width)

def insertGridPointPairWithLinePath(gridPoint, gridPointInsetX, gridPoints, isJunctionWide, linePath, paths, pixelTable, yIntersectionPath, width):
	'Insert a pair of points around the grid point is is junction wide, otherwise inset one point.'
	if len(linePath) < 1:
		return
	if gridPoint in gridPoints:
		gridPoints.remove(gridPoint)
	intersectionBeginPoint = None
	moreThanInset = 2.1 * gridPointInsetX
	path = yIntersectionPath.getPath(paths)
	begin = path[ yIntersectionPath.pointIndex ]
	end = path[ yIntersectionPath.getPointIndexPlusOne() ]
	if yIntersectionPath.isOutside:
		distanceX = end.real - begin.real
		if abs(distanceX) > 2.1 * moreThanInset:
			intersectionBeginXDistance = yIntersectionPath.gridPoint.real - begin.real
			endIntersectionXDistance = end.real - yIntersectionPath.gridPoint.real
			intersectionPoint = begin * endIntersectionXDistance / distanceX + end * intersectionBeginXDistance / distanceX
			distanceYAbsoluteInset = max(abs(yIntersectionPath.gridPoint.imag - intersectionPoint.imag), moreThanInset)
			intersectionEndSegment = end - intersectionPoint
			intersectionEndSegmentLength = abs(intersectionEndSegment)
			if intersectionEndSegmentLength > 1.1 * distanceYAbsoluteInset:
				intersectionEndPoint = intersectionPoint + intersectionEndSegment * distanceYAbsoluteInset / intersectionEndSegmentLength
				path.insert(yIntersectionPath.getPointIndexPlusOne(), intersectionEndPoint)
			intersectionBeginSegment = begin - intersectionPoint
			intersectionBeginSegmentLength = abs(intersectionBeginSegment)
			if intersectionBeginSegmentLength > 1.1 * distanceYAbsoluteInset:
				intersectionBeginPoint = intersectionPoint + intersectionBeginSegment * distanceYAbsoluteInset / intersectionBeginSegmentLength
	for point in linePath:
		addPointOnPath(path, yIntersectionPath.pathIndex, pixelTable, point, yIntersectionPath.getPointIndexPlusOne(), width)
	if intersectionBeginPoint != None:
		addPointOnPath(path, yIntersectionPath.pathIndex, pixelTable, intersectionBeginPoint, yIntersectionPath.getPointIndexPlusOne(), width)

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

def isIntersectingLoopsPaths(loops, paths, pointBegin, pointEnd):
	'Determine if the segment between the first and second point is intersecting the loop list.'
	normalizedSegment = pointEnd.dropAxis() - pointBegin.dropAxis()
	normalizedSegmentLength = abs(normalizedSegment)
	if normalizedSegmentLength == 0.0:
		return False
	normalizedSegment /= normalizedSegmentLength
	segmentYMirror = complex(normalizedSegment.real, -normalizedSegment.imag)
	pointBeginRotated = euclidean.getRoundZAxisByPlaneAngle(segmentYMirror, pointBegin)
	pointEndRotated = euclidean.getRoundZAxisByPlaneAngle(segmentYMirror, pointEnd)
	if euclidean.isLoopListIntersectingInsideXSegment(loops, pointBeginRotated.real, pointEndRotated.real, segmentYMirror, pointBeginRotated.imag):
		return True
	return euclidean.isXSegmentIntersectingPaths(paths, pointBeginRotated.real, pointEndRotated.real, segmentYMirror, pointBeginRotated.imag)

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

def setIsOutside(yCloseToCenterPath, yIntersectionPaths):
	'Determine if the yCloseToCenterPath is outside.'
	beforeClose = yCloseToCenterPath.yMinusCenter < 0.0
	for yIntersectionPath in yIntersectionPaths:
		if yIntersectionPath != yCloseToCenterPath:
			beforePath = yIntersectionPath.yMinusCenter < 0.0
			if beforeClose == beforePath:
				yCloseToCenterPath.isOutside = False
				return
	yCloseToCenterPath.isOutside = True

class FillSkein:
	'A class to fill a skein of extrusions.'
	def __init__(self):
		self.bridgeWidthMultiplier = 1.0
		self.gcode = gcodec.Gcode()
		self.extruderActive = False
		self.fillInset = 0.18
		self.isPerimeter = False
		self.lastExtraShells = -1
		self.lineIndex = 0
		self.oldLocation = None
		self.oldOrderedLocation = None
		self.perimeterWidth = None
		self.rotatedLayer = None
		self.rotatedLayers = []
		self.shutdownLineIndex = sys.maxint
		self.nestedRing = None
		self.thread = None
		
		self.activateFill = config.getboolean(name, 'active')
		self.infillSolidity = config.getfloat(name, 'infill.solidity.ratio')
		self.infillWidthOverThickness = config.getfloat(name, 'extrusion.lines.extra.spacer.scaler')
		self.infillPerimeterOverlap = config.getfloat(name, 'infill.overlap.over.perimeter.scaler')
		self.extraShellsAlternatingSolidLayer = config.getint(name, 'shells.alternating.solid')
		self.extraShellsBase = config.getint(name, 'shells.base')
		self.extraShellsSparseLayer = config.getint(name, 'shells.sparse')
		self.solidSurfaceThickness = config.getint(name, 'fully.filled.layers')
		self.startFromChoice = config.get(name, 'extrusion.sequence.start.layer')
		self.threadSequenceChoice = config.get(name, 'extrusion.sequence.print.order')
		self.infillPattern = config.get(name, 'infill.pattern')
		self.gridExtraOverlap = config.getfloat(name, 'grid.extra.overlap')
		self.diaphragmPeriod = config.getint(name, 'diaphragm.every.n.layers')
		self.diaphragmThickness = config.getint(name, 'diaphragm.thickness')
		self.infillBeginRotation = math.radians(config.getfloat(name, 'infill.rotation.begin'))
		self.infillBeginRotationRepeat = config.getint(name, 'infill.rotation.repeat')
		self.infillOddLayerExtraRotation = math.radians(config.getfloat(name, 'infill.rotation.odd.layer'))

	def addFill(self, layerIndex):
		'Add fill to the carve layer.'
		alreadyFilledArounds = []
		pixelTable = {}
		arounds = []
		betweenWidth = self.perimeterWidth / 1.7594801994   # this really sucks I cant find hwe#(self.repository.infillWidthOverThickness.value * self.perimeterWidth *(0.7853))/1.5 #- 0.0866#todo todo TODO *0.5 is the distance between the outer loops..
		self.layerExtrusionWidth = self.infillWidth # spacing between fill lines
		layerFillInset = self.fillInset  # the distance between perimeter incl loops and the fill pattern
		rotatedLayer = self.rotatedLayers[layerIndex]
		self.gcode.addLine('(<layer> %s )' % rotatedLayer.z)
		layerRotation = self.getLayerRotation(layerIndex)
		reverseRotation = complex(layerRotation.real, -layerRotation.imag)
		surroundingCarves = []
		layerRemainder = layerIndex % self.diaphragmPeriod
		logger.info('filling Layer %s', layerIndex + 1)
		if layerRemainder >= self.diaphragmThickness and rotatedLayer.rotation == None:
			for surroundingIndex in xrange(1, self.solidSurfaceThickness + 1):
				self.addRotatedCarve(layerIndex, -surroundingIndex, reverseRotation, surroundingCarves)
				self.addRotatedCarve(layerIndex, surroundingIndex, reverseRotation, surroundingCarves)
		extraShells = self.extraShellsSparseLayer
		if len(surroundingCarves) < self.doubleSolidSurfaceThickness:
			extraShells = self.extraShellsAlternatingSolidLayer
			if self.lastExtraShells != self.extraShellsBase:
				extraShells = self.extraShellsBase
		if rotatedLayer.rotation != None:
			extraShells = 0
			betweenWidth *= self.bridgeWidthMultiplier#/0.7853  #todo check what is better with or without the normalizer
			self.layerExtrusionWidth *= self.bridgeWidthMultiplier
			layerFillInset *= self.bridgeWidthMultiplier
			self.gcode.addLine('(<bridgeRotation> %s )' % rotatedLayer.rotation)
		aroundInset = 0.25 * self.layerExtrusionWidth
		aroundWidth = 0.25 * self.layerExtrusionWidth
		self.lastExtraShells = extraShells
		gridPointInsetX = 0.5 * layerFillInset
		doubleExtrusionWidth = 2.0 * self.layerExtrusionWidth
		endpoints = []
		infillPaths = []
		layerInfillSolidity = self.infillSolidity
		self.isDoubleJunction = True
		self.isJunctionWide = True
		rotatedLoops = []
		nestedRings = euclidean.getOrderedNestedRings(rotatedLayer.nestedRings)
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
		gridCircular = False
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
		if gridCircular:
			startAngle = euclidean.globalGoldenAngle * float(layerIndex)
			for gridPoint in self.getGridPoints(fillLoops, reverseRotation):
				self.addGridCircle(gridPoint, infillPaths, layerRotation, pixelTable, rotatedLoops, layerRotation, aroundWidth)
		else:
			if self.isGridToBeExtruded():
				self.addGrid(
					arounds, fillLoops, gridPointInsetX, layerIndex, paths, pixelTable, reverseRotation, surroundingCarves, aroundWidth)
			oldRemovedEndpointLength = len(removedEndpoints) + 1
			while oldRemovedEndpointLength - len(removedEndpoints) > 0:
				oldRemovedEndpointLength = len(removedEndpoints)
				removeEndpoints(pixelTable, self.layerExtrusionWidth, paths, removedEndpoints, aroundWidth)
			paths = euclidean.getConnectedPaths(paths, pixelTable, aroundWidth)
		for path in paths:
			addPath(self.layerExtrusionWidth, infillPaths, path, layerRotation)
		euclidean.transferPathsToSurroundingLoops(nestedRings, infillPaths)
		self.addThreadsBridgeLayer(layerIndex, nestedRings, rotatedLayer)

	def addGcodeFromThreadZ(self, thread, z):
		'Add a gcode thread to the output.'
		self.gcode.addGcodeFromThreadZ(thread, z)

	def addGrid(self, arounds, fillLoops, gridPointInsetX, layerIndex, paths, pixelTable, reverseRotation, surroundingCarves, width):
		'Add the grid to the infill layer.'
		if len(surroundingCarves) < self.doubleSolidSurfaceThickness:
			return
		explodedPaths = []
		pathGroups = []
		for path in paths:
			pathIndexBegin = len(explodedPaths)
			for pointIndex in xrange(len(path) - 1):
				pathSegment = [ path[pointIndex], path[pointIndex + 1] ]
				explodedPaths.append(pathSegment)
			pathGroups.append((pathIndexBegin, len(explodedPaths)))
		for pathIndex in xrange(len(explodedPaths)):
			explodedPath = explodedPaths[ pathIndex ]
			euclidean.addPathToPixelTable(explodedPath, pixelTable, pathIndex, width)
		gridPoints = self.getGridPoints(fillLoops, reverseRotation)
		gridPointInsetY = gridPointInsetX * (1.0 - self.gridExtraOverlap)
		
		oldGridPointLength = len(gridPoints) + 1
		while oldGridPointLength - len(gridPoints) > 0:
			oldGridPointLength = len(gridPoints)
			self.addRemainingGridPoints(arounds, gridPointInsetX, gridPointInsetY, gridPoints, True, explodedPaths, pixelTable, width)
		oldGridPointLength = len(gridPoints) + 1
		while oldGridPointLength - len(gridPoints) > 0:
			oldGridPointLength = len(gridPoints)
			self.addRemainingGridPoints(arounds, gridPointInsetX, gridPointInsetY, gridPoints, False, explodedPaths, pixelTable, width)
		for pathGroupIndex in xrange(len(pathGroups)):
			pathGroup = pathGroups[ pathGroupIndex ]
			paths[ pathGroupIndex ] = []
			for explodedPathIndex in xrange(pathGroup[0], pathGroup[1]):
				explodedPath = explodedPaths[ explodedPathIndex ]
				if len(paths[ pathGroupIndex ]) == 0:
					paths[ pathGroupIndex ] = explodedPath
				else:
					paths[ pathGroupIndex ] += explodedPath[1 :]

	def addGridCircle(self, center, infillPaths, layerRotation, pixelTable, rotatedLoops, startRotation, width):
		'Add circle to the grid.'
		startAngle = -math.atan2(startRotation.imag, startRotation.real)
		loop = euclidean.getComplexPolygon(center, self.gridCircleRadius, 17, startAngle)
		loopPixelDictionary = {}
		euclidean.addLoopToPixelTable(loop, loopPixelDictionary, width)
		if not euclidean.isPixelTableIntersecting(pixelTable, loopPixelDictionary):
			if euclidean.getIsInFilledRegion(rotatedLoops, euclidean.getLeftPoint(loop)):
				addLoop(self.layerExtrusionWidth, infillPaths, loop, layerRotation)
				return
		insideIndexPaths = []
		insideIndexPath = None
		for pointIndex, point in enumerate(loop):
			nextPoint = loop[(pointIndex + 1) % len(loop)]
			segmentDictionary = {}
			euclidean.addValueSegmentToPixelTable(point, nextPoint, segmentDictionary, None, width)
			euclidean.addSquareTwoToPixelDictionary(segmentDictionary, point, None, width)
			euclidean.addSquareTwoToPixelDictionary(segmentDictionary, nextPoint, None, width)
			shouldAddLoop = not euclidean.isPixelTableIntersecting(pixelTable, segmentDictionary)
			if shouldAddLoop:
				shouldAddLoop = euclidean.getIsInFilledRegion(rotatedLoops, point)
			if shouldAddLoop:
				if insideIndexPath == None:
					insideIndexPath = [pointIndex]
					insideIndexPaths.append(insideIndexPath)
				else:
					insideIndexPath.append(pointIndex)
			else:
				insideIndexPath = None
		if len(insideIndexPaths) > 1:
			insideIndexPathFirst = insideIndexPaths[0]
			insideIndexPathLast = insideIndexPaths[-1]
			if insideIndexPathFirst[0] == 0 and insideIndexPathLast[-1] == len(loop) - 1:
				insideIndexPaths[0] = insideIndexPathLast + insideIndexPathFirst
				del insideIndexPaths[-1]
		for insideIndexPath in insideIndexPaths:
			path = []
			for insideIndex in insideIndexPath:
				if len(path) == 0:
					path.append(loop[insideIndex])
				path.append(loop[(insideIndex + 1) % len(loop)])
			addPath(self.layerExtrusionWidth, infillPaths, path, layerRotation)

	def addGridLinePoints(self, begin, end, gridPoints, gridRotationAngle, offset, y):
		'Add the segments of one line of a grid to the infill.'
		if self.gridRadius == 0.0:
			return
		gridXStep = int(math.floor((begin) / self.gridXStepSize)) - 3
		gridXOffset = offset + self.gridXStepSize * float(gridXStep)
		while gridXOffset < end:
			if gridXOffset >= begin:
				gridPointComplex = complex(gridXOffset, y) * gridRotationAngle
				if self.isPointInsideLineSegments(gridPointComplex):
					gridPoints.append(gridPointComplex)
			gridXStep = self.getNextGripXStep(gridXStep)
			gridXOffset = offset + self.gridXStepSize * float(gridXStep)

	def addRemainingGridPoints(self, arounds, gridPointInsetX, gridPointInsetY, gridPoints, isBothOrNone, paths, pixelTable, width):
		'Add the remaining grid points to the grid point list.'
		for gridPointIndex in xrange(len(gridPoints) - 1, -1, -1):
			gridPoint = gridPoints[ gridPointIndex ]
			addAroundGridPoint(arounds, gridPoint, gridPointInsetX, gridPointInsetY, gridPoints, self.gridRadius, isBothOrNone, self.isDoubleJunction, self.isJunctionWide, paths, pixelTable, width)

	def addRotatedCarve(self, currentLayer, layerDelta, reverseRotation, surroundingCarves):
		'Add a rotated carve to the surrounding carves.'
		layerIndex = currentLayer + layerDelta
		if layerIndex < 0 or layerIndex >= len(self.rotatedLayers):
			return
		nestedRings = self.rotatedLayers[layerIndex].nestedRings
		rotatedCarve = []
		for nestedRing in nestedRings:
			planeRotatedLoop = euclidean.getPointsRoundZAxis(reverseRotation, nestedRing.boundary)
			rotatedCarve.append(planeRotatedLoop)
		outsetRadius = float(abs(layerDelta)) * self.perimeterWidth #todo investigate was   float(abs(layerDelta)) * self.layerThickness
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
		euclidean.addToThreadsRemove(extrusionHalfWidth, nestedRings, self.oldOrderedLocation, self, threadSequence)
		if rotatedLayer.rotation != None:
			self.gcode.addLine('(</bridgeRotation>)')
		self.gcode.addLine('(</layer>)')

	def addToThread(self, location):
		'Add a location to thread.'
		if self.oldLocation == None:
			return
		if self.isPerimeter:
			self.nestedRing.addToLoop(location)
			return
		if self.thread == None:
			self.thread = [ self.oldLocation.dropAxis() ]
			self.nestedRing.perimeterPaths.append(self.thread)
		self.thread.append(location.dropAxis())

	def getCraftedGcode(self, gcodeText):
		'Parse gcode text and store the bevel gcode.'
		self.lines = archive.getTextLines(gcodeText)
		self.threadSequence = self.threadSequenceChoice.split(",")
		self.parseInitialization()
		if self.perimeterWidth == None:
			logger.warning('Nothing will be done because self.perimeterWidth in getCraftedGcode in FillSkein was None.')
			return ''
		self.betweenWidth = self.perimeterWidth * self.infillWidthOverThickness * (0.7853)
		self.fillInset = self.infillWidth # * self.repository.infillPerimeterOverlap.value #self.infillWidth / self.repository.infillPerimeterOverlap.value #todo was :self.infillWidth - self.infillWidth * self.repository.infillPerimeterOverlap.value
		if self.isGridToBeExtruded():
			self.setGridVariables()
		
		self.doubleSolidSurfaceThickness = self.solidSurfaceThickness + self.solidSurfaceThickness
		for lineIndex in xrange(self.lineIndex, len(self.lines)):
			self.parseLine(lineIndex)
		for layerIndex in xrange(len(self.rotatedLayers)):
			self.addFill(layerIndex)
		self.gcode.addLines(self.lines[ self.shutdownLineIndex : ])
		return self.gcode.output.getvalue()

	def getGridPoints(self, fillLoops, reverseRotation):
		'Get the grid points.'
		if self.infillSolidity > 0.8:
			return []
		rotationBaseAngle = euclidean.getWiddershinsUnitPolar(self.infillBeginRotation)
		reverseRotationBaseAngle = complex(rotationBaseAngle.real, -rotationBaseAngle.imag)
		gridRotationAngle = reverseRotation * rotationBaseAngle
		slightlyGreaterThanFill = 1.001 * self.gridInset #todo 1.01 or 0.99
		rotatedLoops = []
		triangle_mesh.sortLoopsInOrderOfArea(True, fillLoops)
		for fillLoop in fillLoops:
			rotatedLoops.append(euclidean.getPointsRoundZAxis(reverseRotationBaseAngle, fillLoop))
		return self.getGridPointsByLoops(gridRotationAngle, intercircle.getInsetSeparateLoopsFromLoops(self.gridInset, rotatedLoops))

	def getGridPointsByLoops(self, gridRotationAngle, loops):
		'Get the grid points by loops.'
		gridIntersectionsDictionary = {}
		gridPoints = []
		euclidean.addXIntersectionsFromLoopsForTable(loops, gridIntersectionsDictionary, self.gridRadius)
		for gridIntersectionsKey in gridIntersectionsDictionary:
			y = gridIntersectionsKey * self.gridRadius + self.gridRadius * 0.5
			gridIntersections = gridIntersectionsDictionary[gridIntersectionsKey]
			gridIntersections.sort()
			gridIntersectionsLength = len(gridIntersections)
			if gridIntersectionsLength % 2 == 1:
				gridIntersectionsLength -= 1
			for gridIntersectionIndex in xrange(0, gridIntersectionsLength, 2):
				begin = gridIntersections[gridIntersectionIndex]
				end = gridIntersections[gridIntersectionIndex + 1]
				offset = self.offsetMultiplier * (gridIntersectionsKey % 2) + self.offsetBaseX
				self.addGridLinePoints(begin, end, gridPoints, gridRotationAngle, offset, y)
		return gridPoints

	def getLayerRotation(self, layerIndex):
		'Get the layer rotation.'
		rotation = self.rotatedLayers[layerIndex].rotation
		if rotation != None:
			return rotation
		infillOddLayerRotationMultiplier = float(layerIndex % (self.infillBeginRotationRepeat + 1) == self.infillBeginRotationRepeat)
		layerAngle = self.infillBeginRotation + infillOddLayerRotationMultiplier * self.infillOddLayerExtraRotation
		return euclidean.getWiddershinsUnitPolar(layerAngle)

	def getNextGripXStep(self, gridXStep):
		'Get the next grid x step, increment by an extra one every three if hexagonal grid is chosen.'
		gridXStep += 1
		return gridXStep

	def isGridToBeExtruded(self):
		'Determine if the grid is to be extruded.'
		return False

	def isPointInsideLineSegments(self, gridPoint):
		'Is the point inside the line segments of the loops.'
		if self.solidSurfaceThickness <= 0:
			return True
		fillLine = int(round(gridPoint.imag / self.layerExtrusionWidth - self.frontOverWidth))
		if fillLine >= len(self.horizontalSegmentLists) or fillLine < 0:
			return False
		lineSegments = self.horizontalSegmentLists[fillLine]
		surroundingXIntersections = self.surroundingXIntersectionLists[fillLine]
		for lineSegment in lineSegments:
			if isSegmentCompletelyInAnIntersection(lineSegment, surroundingXIntersections):
				xFirst = lineSegment[0].point.real
				xSecond = lineSegment[1].point.real
				if gridPoint.real > min(xFirst, xSecond) and gridPoint.real < max(xFirst, xSecond):
					return True
		return False

	def linearMove(self, splitLine):
		'Add a linear move to the thread.'
		location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
		if self.extruderActive:
			self.addToThread(location)
		self.oldLocation = location

	def parseInitialization(self):
		'Parse gcode initialization and store the parameters.'
		for self.lineIndex in xrange(len(self.lines)):
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.gcode.parseSplitLine(firstWord, splitLine)
			if firstWord == '(<perimeterWidth>':
				self.perimeterWidth = float(splitLine[1])
				threadSequenceString = ' '.join(self.threadSequence)
				self.gcode.addTagBracketedLine('threadSequenceString', threadSequenceString)
				self.infillWidth = self.perimeterWidth * self.infillWidthOverThickness * (0.7853)
				self.gcode.addTagRoundedLine('infillWidth', self.infillWidth)
			elif firstWord == '(</extruderInitialization>)':
				self.gcode.addLine('(<procedureName> fill </procedureName>)')
			elif firstWord == '(<crafting>)':
				self.gcode.addLine(line)
				return
			elif firstWord == '(<bridgeWidthMultiplier>':
				self.bridgeWidthMultiplier = float(splitLine[1])
			elif firstWord == '(<layerThickness>':
				self.layerThickness = float(splitLine[1])
			self.gcode.addLine(line)

	def parseLine(self, lineIndex):
		'Parse a gcode line and add it to the fill skein.'
		line = self.lines[lineIndex]
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == 'G1':
			self.linearMove(splitLine)
		elif firstWord == 'M101':
			self.extruderActive = True
		elif firstWord == 'M103':
			self.extruderActive = False
			self.thread = None
			self.isPerimeter = False
		elif firstWord == '(<boundaryPerimeter>)':
			self.nestedRing = euclidean.NestedBand()
			self.rotatedLayer.nestedRings.append(self.nestedRing)
		elif firstWord == '(</boundaryPerimeter>)':
			self.nestedRing = None
		elif firstWord == '(<boundaryPoint>':
			location = gcodec.getLocationFromSplitLine(None, splitLine)
			self.nestedRing.addToBoundary(location)
		elif firstWord == '(<bridgeRotation>':
			secondWordWithoutBrackets = splitLine[1].replace('(', '').replace(')', '')
			self.rotatedLayer.rotation = complex(secondWordWithoutBrackets)
		elif firstWord == '(</crafting>)':
			self.shutdownLineIndex = lineIndex
		elif firstWord == '(<layer>':
			self.rotatedLayer = RotatedLayer(float(splitLine[1]))
			self.rotatedLayers.append(self.rotatedLayer)
			self.thread = None
		elif firstWord == '(<perimeter>':
			self.isPerimeter = True

	def setGridVariables(self):
		'Set the grid variables.'
		self.gridInset = 1.2 * self.infillWidth
		self.gridRadius = self.infillWidth / self.infillSolidity
		self.gridXStepSize = 2.0 * self.gridRadius
 		self.offsetMultiplier = self.gridRadius
		self.offsetBaseX = 0.25 * self.gridXStepSize

class RotatedLayer:
	'A rotated layer.'
	def __init__(self, z):
		self.rotation = None
		self.nestedRings = []
		self.z = z

	def __repr__(self):
		'Get the string representation of this RotatedLayer.'
		return '%s, %s, %s' % (self.z, self.rotation, self.nestedRings)


class YIntersectionPath:
	'A class to hold the y intersection position, the loop which it intersected and the point index of the loop which it intersected.'
	def __init__(self, pathIndex, pointIndex, y):
		'Initialize from the path, point index, and y.'
		self.pathIndex = pathIndex
		self.pointIndex = pointIndex
		self.y = y

	def __repr__(self):
		'Get the string representation of this y intersection.'
		return '%s, %s, %s' % (self.pathIndex, self.pointIndex, self.y)

	def getPath(self, paths):
		'Get the path from the paths and path index.'
		return paths[ self.pathIndex ]

	def getPointIndexPlusOne(self):
		'Get the point index plus one.'
		return self.pointIndex + 1
