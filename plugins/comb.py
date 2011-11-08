"""
Comb the extrusion hair of a gcode file.  Modifies the travel paths so the nozzle does not go over empty spaces, thus reducing the strings that may build up.

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from fabmetheus_utilities import archive, euclidean, intercircle
import logging
import math

name = __name__
logger = logging.getLogger(name)

class CombSkein:
	"A class to comb a skein of extrusions."
	def __init__(self, layer):
		'Initialize'
		self.betweenTable = {}
		self.z = layer.z
		
		self.perimeterWidth = layer.runtimeParameters.perimeterWidth
		self.combInset = 0.7 * self.perimeterWidth
		self.betweenInset = 0.4 * self.perimeterWidth
		self.uTurnWidth = 0.5 * self.betweenInset
		self.travelFeedRateMinute = layer.runtimeParameters.travelFeedRateMinute
		
		self.boundaries = []
		perimeters = []
		layer.getPerimeterPaths(perimeters)
		for perimeter in perimeters:
			x = []
			for boundaryPoint in perimeter.boundaryPoints:
				x.append(boundaryPoint.dropAxis())
			self.boundaries.append(x)
				
	def getBetweens(self):
		"Set betweens for the layer."
		if self.z in self.betweenTable:
			return self.betweenTable[ self.z ]
		if len(self.boundaries) == 0:
			return []
		self.betweenTable[ self.z ] = []
		for boundaryLoop in self.boundaries:
			self.betweenTable[ self.z ] += intercircle.getInsetLoopsFromLoop(boundaryLoop, self.betweenInset)
		return self.betweenTable[ self.z ]

	def getIsAsFarAndNotIntersecting(self, begin, end):
		"Determine if the point on the line is at least as far from the loop as the center point."
		if begin == end:
			print('this should never happen but it does not really matter, begin == end in getIsAsFarAndNotIntersecting in comb.')
			print(begin)
			return True
		return not euclidean.isLineIntersectingLoops(self.getBetweens(), begin, end)

	def getIsRunningJumpPathAdded(self, betweens, end, lastPoint, nearestEndMinusLastSegment, pathAround, penultimatePoint, runningJumpSpace):
		"Add a running jump path if possible, and return if it was added."
		jumpStartPoint = lastPoint - nearestEndMinusLastSegment * runningJumpSpace
		if euclidean.isLineIntersectingLoops(betweens, penultimatePoint, jumpStartPoint):
			return False
		pathAround[-1] = jumpStartPoint
		return True

	def getPathsByIntersectedLoop(self, begin, end, loop):
		"Get both paths along the loop from the point nearest to the begin to the point nearest to the end."
		nearestBeginDistanceIndex = euclidean.getNearestDistanceIndex(begin, loop)
		nearestEndDistanceIndex = euclidean.getNearestDistanceIndex(end, loop)
		beginIndex = (nearestBeginDistanceIndex.index + 1) % len(loop)
		endIndex = (nearestEndDistanceIndex.index + 1) % len(loop)
		nearestBegin = euclidean.getNearestPointOnSegment(loop[ nearestBeginDistanceIndex.index ], loop[ beginIndex ], begin)
		nearestEnd = euclidean.getNearestPointOnSegment(loop[ nearestEndDistanceIndex.index ], loop[ endIndex ], end)
		clockwisePath = [ nearestBegin ]
		widdershinsPath = [ nearestBegin ]
		if nearestBeginDistanceIndex.index != nearestEndDistanceIndex.index:
			widdershinsPath += euclidean.getAroundLoop(beginIndex, endIndex, loop)
			clockwisePath += euclidean.getAroundLoop(endIndex, beginIndex, loop)[: :-1]
		clockwisePath.append(nearestEnd)
		widdershinsPath.append(nearestEnd)
		return [ clockwisePath, widdershinsPath ]

	def getPathBetween(self, loop, points):
		"Add a path between the perimeter and the fill."
		paths = self.getPathsByIntersectedLoop(points[1], points[2], loop)
		shortestPath = paths[int(euclidean.getPathLength(paths[1]) < euclidean.getPathLength(paths[0]))]
		if len(shortestPath) < 2:
			return shortestPath
		if abs(points[1] - shortestPath[0]) > abs(points[1] - shortestPath[-1]):
			shortestPath.reverse()
		loopWiddershins = euclidean.isWiddershins(loop)
		pathBetween = []
		for pointIndex in xrange(len(shortestPath)):
			center = shortestPath[pointIndex]
			centerPerpendicular = None
			beginIndex = pointIndex - 1
			if beginIndex >= 0:
				begin = shortestPath[beginIndex]
				centerPerpendicular = intercircle.getWiddershinsByLength(center, begin, self.combInset)
			centerEnd = None
			endIndex = pointIndex + 1
			if endIndex < len(shortestPath):
				end = shortestPath[endIndex]
				centerEnd = intercircle.getWiddershinsByLength(end, center, self.combInset)
			if centerPerpendicular == None:
				centerPerpendicular = centerEnd
			elif centerEnd != None:
				centerPerpendicular = 0.5 * (centerPerpendicular + centerEnd)
			between = None
			if centerPerpendicular == None:
				between = center
			if between == None:
				centerSideWiddershins = center + centerPerpendicular
				if euclidean.isPointInsideLoop(loop, centerSideWiddershins) == loopWiddershins:
					between = centerSideWiddershins
			if between == None:
				centerSideClockwise = center - centerPerpendicular
				if euclidean.isPointInsideLoop(loop, centerSideClockwise) == loopWiddershins:
					between = centerSideClockwise
			if between == None:
				between = center
			pathBetween.append(between)
		return pathBetween

	def getPathsBetween(self, z, begin, end):
		"Insert paths between the perimeter and the fill."
		self.z = z
		aroundBetweenPath = []
		points = [begin]
		lineX = []
		switchX = []
		segment = euclidean.getNormalized(end - begin)
		segmentYMirror = complex(segment.real, -segment.imag)
		beginRotated = segmentYMirror * begin
		endRotated = segmentYMirror * end
		y = beginRotated.imag
		
		for boundaryIndex in xrange(len(self.boundaries)):
			boundary = self.boundaries[ boundaryIndex ]
			boundaryRotated = euclidean.getPointsRoundZAxis(segmentYMirror, boundary)
			euclidean.addXIntersectionIndexesFromLoopY(boundaryRotated, boundaryIndex, switchX, y)
		switchX.sort()
		maximumX = max(beginRotated.real, endRotated.real)
		minimumX = min(beginRotated.real, endRotated.real)
		for xIntersection in switchX:
			if xIntersection.x > minimumX and xIntersection.x < maximumX:
				point = segment * complex(xIntersection.x, y)
				points.append(point)
				lineX.append(xIntersection)
		points.append(end)
		lineXIndex = 0
		while lineXIndex < len(lineX) - 1:
			lineXFirst = lineX[lineXIndex]
			lineXSecond = lineX[lineXIndex + 1]
			loopFirst = self.boundaries[lineXFirst.index]
			if lineXSecond.index == lineXFirst.index:
				pathBetween = self.getPathBetween(loopFirst, points[lineXIndex : lineXIndex + 4])
				pathBetween = self.getSimplifiedAroundPath(points[lineXIndex], points[lineXIndex + 3], loopFirst, pathBetween)
				aroundBetweenPath += pathBetween
				lineXIndex += 2
			else:
				lineXIndex += 1
		return aroundBetweenPath

	def getSimplifiedAroundPath(self, begin, end, loop, pathAround):
		"Get the simplified path between the perimeter and the fill."
		pathAround = self.getSimplifiedBeginPath(begin, loop, pathAround)
		return self.getSimplifiedEndPath(end, loop, pathAround)

	def getSimplifiedBeginPath(self, begin, loop, pathAround):
		"Get the simplified begin path between the perimeter and the fill."
		if len(pathAround) < 2:
			return pathAround
		pathIndex = 0
		while pathIndex < len(pathAround) - 1:
			if not self.getIsAsFarAndNotIntersecting(begin, pathAround[pathIndex + 1]):
				return pathAround[pathIndex :]
			pathIndex += 1
		return pathAround[-1 :]

	def getSimplifiedEndPath(self, end, loop, pathAround):
		"Get the simplified end path between the perimeter and the fill."
		if len(pathAround) < 2:
			return pathAround
		pathIndex = len(pathAround) - 1
		while pathIndex > 0:
			if not self.getIsAsFarAndNotIntersecting(end, pathAround[pathIndex - 1]):
				return pathAround[: pathIndex + 1]
			pathIndex -= 1
		return pathAround[: 1]
