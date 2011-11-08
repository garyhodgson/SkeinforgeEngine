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


def performAction(gcode):
	"Modify the travel paths of a skein to remove strings"
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return text
	return CombSkein(gcode.runtimeParameters).comb()

class CombSkein:
	"A class to comb a skein of extrusions."
	def __init__(self,runtimeParameters):
		'Initialize'
		self.isAlteration = False
		self.betweenTable = {}
		self.boundaryLoop = None
		#self.gcode = gcode
		self.runtimeParameters = runtimeParameters
		self.extruderActive = False
		self.layer = None
		self.layerCount = 0
		self.layerTable = {}
		self.layerZ = None
		self.lineIndex = 0
		self.lines = None
		self.nextLayerZ = None
		self.oldLocation = None
		self.oldZ = None
		self.operatingFeedRatePerMinute = None
		self.travelFeedRateMinute = None
		
		self.perimeterWidth = self.runtimeParameters.perimeterWidth
		self.combInset = 0.7 * self.perimeterWidth
		self.betweenInset = 0.4 * self.perimeterWidth
		self.uTurnWidth = 0.5 * self.betweenInset
		self.travelFeedRateMinute = self.runtimeParameters.travelFeedRateMinute
		

	def comb(self):
		"Modify the travel paths of a skein to remove strings"
		
		None
#		for lineIndex in xrange(self.lineIndex, len(self.lines)):
#			line = self.lines[lineIndex]
#			self.parseBoundariesLayers(line)
#		for lineIndex in xrange(self.lineIndex, len(self.lines)):
#			line = self.lines[lineIndex]
#			self.parseLine(line)
	
	
	def parseBoundariesLayers(self, line):
		"Parse a gcode line."
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == 'M103':
			self.boundaryLoop = None
		elif firstWord == '(<boundaryPoint>':
			location = gcodec.getLocationFromSplitLine(None, splitLine)
			self.addToLoop(location)
		elif firstWord == '(<layer>':
			self.boundaryLoop = None
			self.layer = None
			self.oldZ = float(splitLine[1])

	def parseLine(self, line):
		"Parse a gcode line and add it to the comb skein."
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == 'G1':
			self.addIfTravel(splitLine)
			self.layerZ = self.nextLayerZ
		elif firstWord == 'M101':
			self.extruderActive = True
		elif firstWord == 'M103':
			self.extruderActive = False
		elif firstWord == '(<alteration>)':
			self.isAlteration = True
		elif firstWord == '(</alteration>)':
			self.isAlteration = False
		elif firstWord == '(<layer>':
			self.layerCount = self.layerCount + 1
			#logger.info('layer: %s', self.layerCount)
			self.nextLayerZ = float(splitLine[1])
			if self.layerZ == None:
				self.layerZ = self.nextLayerZ
		self.gcode.addLine(line)


	def addGcodePathZ(self, feedRateMinute, path, z):
		"Add a gcode path, without modifying the extruder, to the output."
		for point in path:
			self.gcode.addGcodeMovementZWithFeedRate(feedRateMinute, point, z)

	def addIfTravel(self, splitLine):
		"Add travel move around loops if the extruder is off."
		location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
		if not self.isAlteration and not self.extruderActive and self.oldLocation != None:
			if len(self.getBoundaries()) > 0:
				highestZ = max(location.z, self.oldLocation.z)
				self.addGcodePathZ(self.travelFeedRateMinute, self.getPathsBetween(self.oldLocation.dropAxis(), location.dropAxis()), highestZ)
		self.oldLocation = location

	def addToLoop(self, location):
		"Add a location to loop."
		if self.layer == None:
			if not self.oldZ in self.layerTable:
				self.layerTable[ self.oldZ ] = []
			self.layer = self.layerTable[ self.oldZ ]
		if self.boundaryLoop == None:
			self.boundaryLoop = [] #starting with an empty array because a closed loop does not have to restate its beginning
			self.layer.append(self.boundaryLoop)
		if self.boundaryLoop != None:
			self.boundaryLoop.append(location.dropAxis())

	def getBetweens(self):
		"Set betweens for the layer."
		if self.layerZ in self.betweenTable:
			return self.betweenTable[ self.layerZ ]
		if self.layerZ not in self.layerTable:
			return []
		self.betweenTable[ self.layerZ ] = []
		for boundaryLoop in self.layerTable[ self.layerZ ]:
			self.betweenTable[ self.layerZ ] += intercircle.getInsetLoopsFromLoop(boundaryLoop, self.betweenInset)
		return self.betweenTable[ self.layerZ ]

	def getBoundaries(self):
		"Get boundaries for the layer."
		if self.layerZ in self.layerTable:
			return self.layerTable[ self.layerZ ]
		return []

	

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

	def getPathsBetween(self, begin, end):
		"Insert paths between the perimeter and the fill."
		aroundBetweenPath = []
		points = [begin]
		lineX = []
		switchX = []
		segment = euclidean.getNormalized(end - begin)
		segmentYMirror = complex(segment.real, -segment.imag)
		beginRotated = segmentYMirror * begin
		endRotated = segmentYMirror * end
		y = beginRotated.imag
		boundaries = self.getBoundaries()
		for boundaryIndex in xrange(len(boundaries)):
			boundary = boundaries[ boundaryIndex ]
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
#		pathBetweenAdded = False
		while lineXIndex < len(lineX) - 1:
			lineXFirst = lineX[lineXIndex]
			lineXSecond = lineX[lineXIndex + 1]
			loopFirst = boundaries[lineXFirst.index]
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
