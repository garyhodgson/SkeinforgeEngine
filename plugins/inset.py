"""
Inset will inset the outside outlines by half the perimeter width, and outset the inside outlines by the same amount.

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config, config
from fabmetheus_utilities import archive, euclidean, intercircle
from fabmetheus_utilities.geometry.solids import triangle_mesh
from gcode import GcodeCommand, Layer, BoundaryPerimeter, NestedRing
from multiprocessing import Pool, Manager, Process
from utilities import class_pickler
import copy_reg
import logging
import math
import multiprocessing
import os
import sys
import types
from utilities import memory_tracker

logger = logging.getLogger(__name__)
name = __name__

def performAction(gcode):
	"Inset the gcode."
	
	i = InsetSkein(gcode)
	if gcode.runtimeParameters.profileMemory:
            memory_tracker.track_object(i)
	i.inset()
	
	if gcode.runtimeParameters.profileMemory:
		memory_tracker.create_snapshot("After inset")

class InsetSkein:
	
	"A class to inset a skein of extrusions."
	def __init__(self, gcode):
		self.gcode = gcode
		self.overlapRemovalWidthOverPerimeterWidth = config.getfloat(name, 'overlap.removal.scaler')
		self.nozzleDiameter = config.getfloat(name, 'nozzle.diameter')
		self.bridgeWidthMultiplier = config.getfloat(name, 'bridge.width.multiplier.ratio')
		self.loopOrderAscendingArea = config.getboolean(name, 'loop.order.preferloops')
		self.layerThickness = self.gcode.runtimeParameters.layerThickness
		self.perimeterWidth = self.gcode.runtimeParameters.perimeterWidth
		self.halfPerimeterWidth = 0.5 * self.perimeterWidth
		self.overlapRemovalWidth = self.perimeterWidth * (0.7853) * self.overlapRemovalWidthOverPerimeterWidth
		self.multiprocess = config.getboolean(name, 'multiprocess')
		
	def inset(self):
		"Inset the layers"
		
		if self.multiprocess:
			manager = Manager()
			sharedLayers = manager.list(self.gcode.layers.values())
			
			p = Pool()
			resultLayers = p.map(self.addInsetForLayer, sharedLayers)
			p.close()
			p.join()
			
			for resultLayer in resultLayers:
				self.gcode.layers[resultLayer.z] = resultLayer
			
		else:
			
			for x in self.gcode.layers.values():
				self.addInsetForLayer(x)
			
	def addInsetForLayer(self, layer):
		halfWidth = self.halfPerimeterWidth * 0.7853
		if layer.bridgeRotation != None:
			halfWidth = self.bridgeWidthMultiplier * ((2 * self.nozzleDiameter - self.layerThickness) / 2) * 0.7853
		
		alreadyFilledArounds = []
		
		for nestedRing in layer.nestedRings:
			self.addInset(nestedRing, halfWidth, alreadyFilledArounds)
		return layer

	def addInset(self, nestedRing, halfWidth, alreadyFilledArounds):
		"Add inset to the layer."

		# Note: inner nested rings have to come first so the intersecting check below does not give a false positive
		for innerNestedRing in nestedRing.innerNestedRings:
			self.addInset(innerNestedRing, halfWidth, alreadyFilledArounds)
					
		boundary = [nestedRing.getXYBoundaries()]
		insetBoundaryPerimeter = intercircle.getInsetLoopsFromLoops(halfWidth, boundary)
		
		triangle_mesh.sortLoopsInOrderOfArea(not self.loopOrderAscendingArea, insetBoundaryPerimeter)
		
		for loop in insetBoundaryPerimeter:
			centerOutset = intercircle.getLargestCenterOutsetLoopFromLoopRegardless(loop, halfWidth)
			
			"Add the perimeter block remainder of the loop which does not overlap the alreadyFilledArounds loops."
			if self.overlapRemovalWidthOverPerimeterWidth < 0.1:
				nestedRing.boundaryPerimeter.addPathFromThread(centerOutset.center + [centerOutset.center[0]])
				break
			isIntersectingSelf = isIntersectingItself(centerOutset.center, self.overlapRemovalWidth)
			
			if isIntersectingWithinLists(centerOutset.center, alreadyFilledArounds) or isIntersectingSelf:
				self.addGcodeFromPerimeterPaths(nestedRing, isIntersectingSelf, centerOutset.center, alreadyFilledArounds, halfWidth, boundary)
			else:
				nestedRing.boundaryPerimeter.addPathFromThread(centerOutset.center + [centerOutset.center[0]])
			addAlreadyFilledArounds(alreadyFilledArounds, centerOutset.center, self.overlapRemovalWidth)

				
	def addGcodeFromPerimeterPaths(self, nestedRing, isIntersectingSelf, loop, alreadyFilledArounds, halfWidth, boundary):
		"Add the perimeter paths to the output."
		segments = []
		outlines = []
		thickOutlines = []
		allLoopLists = alreadyFilledArounds[:] + [thickOutlines]
		aroundLists = alreadyFilledArounds
		for pointIndex in xrange(len(loop)):
			pointBegin = loop[pointIndex]
			pointEnd = loop[(pointIndex + 1) % len(loop)]
			if isIntersectingSelf:
				if euclidean.isLineIntersectingLoops(outlines, pointBegin, pointEnd):
					segments += getSegmentsFromLoopListsPoints(allLoopLists, pointBegin, pointEnd)
				else:
					segments += getSegmentsFromLoopListsPoints(alreadyFilledArounds, pointBegin, pointEnd)
				addSegmentOutline(False, outlines, pointBegin, pointEnd, self.overlapRemovalWidth)
				addSegmentOutline(True, thickOutlines, pointBegin, pointEnd, self.overlapRemovalWidth)
			else:
				segments += getSegmentsFromLoopListsPoints(alreadyFilledArounds, pointBegin, pointEnd)
		perimeterPaths = []
		path = []
		muchSmallerThanRadius = 0.1 * halfWidth
		segments = getInteriorSegments(boundary, segments)
		for segment in segments:
			pointBegin = segment[0].point
			if not isCloseToLast(perimeterPaths, pointBegin, muchSmallerThanRadius):
				path = [pointBegin]
				perimeterPaths.append(path)
			path.append(segment[1].point)
		if len(perimeterPaths) > 1:
			firstPath = perimeterPaths[0]
			lastPath = perimeterPaths[-1]
			if abs(lastPath[-1] - firstPath[0]) < 0.1 * muchSmallerThanRadius:
				connectedBeginning = lastPath[:-1] + firstPath
				perimeterPaths[0] = connectedBeginning
				perimeterPaths.remove(lastPath)
		muchGreaterThanRadius = 6.0 * halfWidth
		for perimeterPath in perimeterPaths:
			if euclidean.getPathLength(perimeterPath) > muchGreaterThanRadius:
				nestedRing.boundaryPerimeter.addPathFromThread(perimeterPath)

def addAlreadyFilledArounds(alreadyFilledArounds, loop, radius):
	"Add already filled loops around loop to alreadyFilledArounds."
	radius = abs(radius)
	alreadyFilledLoop = []
	slightlyGreaterThanRadius = 1.01 * radius
	muchGreaterThanRadius = 2.5 * radius
	centers = intercircle.getCentersFromLoop(loop, slightlyGreaterThanRadius)
	for center in centers:
		alreadyFilledInset = intercircle.getSimplifiedInsetFromClockwiseLoop(center, radius)
		if intercircle.isLargeSameDirection(alreadyFilledInset, center, radius):
			alreadyFilledLoop.append(alreadyFilledInset)
	if len(alreadyFilledLoop) > 0:
		alreadyFilledArounds.append(alreadyFilledLoop)

def addSegmentOutline(isThick, outlines, pointBegin, pointEnd, width):
	"Add a diamond or hexagonal outline for a line segment."
	width = abs(width)
	exclusionWidth = 0.6 * width
	slope = 0.2
	if isThick:
		slope = 3.0
		exclusionWidth = 0.8 * width
	segment = pointEnd - pointBegin
	segmentLength = abs(segment)
	if segmentLength == 0.0:
		return
	normalizedSegment = segment / segmentLength
	outline = []
	segmentYMirror = complex(normalizedSegment.real, -normalizedSegment.imag)
	pointBeginRotated = segmentYMirror * pointBegin
	pointEndRotated = segmentYMirror * pointEnd
	along = 0.05
	alongLength = along * segmentLength
	if alongLength > 0.1 * exclusionWidth:
		along *= 0.1 * exclusionWidth / alongLength
	alongEnd = 1.0 - along
	remainingToHalf = 0.5 - along
	alongToWidth = exclusionWidth / slope / segmentLength
	pointBeginIntermediate = euclidean.getIntermediateLocation(along, pointBeginRotated, pointEndRotated)
	pointEndIntermediate = euclidean.getIntermediateLocation(alongEnd, pointBeginRotated, pointEndRotated)
	outline.append(pointBeginIntermediate)
	verticalWidth = complex(0.0, exclusionWidth)
	if alongToWidth > 0.9 * remainingToHalf:
		verticalWidth = complex(0.0, slope * remainingToHalf * segmentLength)
		middle = (pointBeginIntermediate + pointEndIntermediate) * 0.5
		middleDown = middle - verticalWidth
		middleUp = middle + verticalWidth
		outline.append(middleUp)
		outline.append(pointEndIntermediate)
		outline.append(middleDown)
	else:
		alongOutsideBegin = along + alongToWidth
		alongOutsideEnd = alongEnd - alongToWidth
		outsideBeginCenter = euclidean.getIntermediateLocation(alongOutsideBegin, pointBeginRotated, pointEndRotated)
		outsideBeginCenterDown = outsideBeginCenter - verticalWidth
		outsideBeginCenterUp = outsideBeginCenter + verticalWidth
		outsideEndCenter = euclidean.getIntermediateLocation(alongOutsideEnd, pointBeginRotated, pointEndRotated)
		outsideEndCenterDown = outsideEndCenter - verticalWidth
		outsideEndCenterUp = outsideEndCenter + verticalWidth
		outline.append(outsideBeginCenterUp)
		outline.append(outsideEndCenterUp)
		outline.append(pointEndIntermediate)
		outline.append(outsideEndCenterDown)
		outline.append(outsideBeginCenterDown)
	outlines.append(euclidean.getPointsRoundZAxis(normalizedSegment, outline))

def getInteriorSegments(loops, segments):
	'Get segments inside the loops.'
	interiorSegments = []
	for segment in segments:
		center = 0.5 * (segment[0].point + segment[1].point)
		if euclidean.getIsInFilledRegion(loops, center):
			interiorSegments.append(segment)
	return interiorSegments

def getIsIntersectingWithinList(loop, loopList):
	"Determine if the loop is intersecting or is within the loop list."
	leftPoint = euclidean.getLeftPoint(loop)
	for otherLoop in loopList:
		if euclidean.getNumberOfIntersectionsToLeft(otherLoop, leftPoint) % 2 == 1:
			return True
	return euclidean.isLoopIntersectingLoops(loop, loopList)


def getSegmentsFromLoopListsPoints(loopLists, pointBegin, pointEnd):
	"Get endpoint segments from the beginning and end of a line segment."
	normalizedSegment = pointEnd - pointBegin
	normalizedSegmentLength = abs(normalizedSegment)
	if normalizedSegmentLength == 0.0:
		return []
	normalizedSegment /= normalizedSegmentLength
	segmentYMirror = complex(normalizedSegment.real, -normalizedSegment.imag)
	pointBeginRotated = segmentYMirror * pointBegin
	pointEndRotated = segmentYMirror * pointEnd
	rotatedLoopLists = []
	for loopList in loopLists:
		rotatedLoopList = []
		rotatedLoopLists.append(rotatedLoopList)
		for loop in loopList:
			rotatedLoop = euclidean.getPointsRoundZAxis(segmentYMirror, loop)
			rotatedLoopList.append(rotatedLoop)
	xIntersectionIndexList = []
	xIntersectionIndexList.append(euclidean.XIntersectionIndex(-1, pointBeginRotated.real))
	xIntersectionIndexList.append(euclidean.XIntersectionIndex(-1, pointEndRotated.real))
	euclidean.addXIntersectionIndexesFromLoopListsY(rotatedLoopLists, xIntersectionIndexList, pointBeginRotated.imag)
	segments = euclidean.getSegmentsFromXIntersectionIndexes(xIntersectionIndexList, pointBeginRotated.imag)
	for segment in segments:
		for endpoint in segment:
			endpoint.point *= normalizedSegment
	return segments

def isCloseToLast(paths, point, radius):
	"Determine if the point is close to the last point of the last path."
	if len(paths) < 1:
		return False
	lastPath = paths[-1]
	return abs(lastPath[-1] - point) < radius

def isIntersectingItself(loop, width):
	"Determine if the loop is intersecting itself."
	outlines = []
	for pointIndex in xrange(len(loop)):
		pointBegin = loop[pointIndex]
		pointEnd = loop[(pointIndex + 1) % len(loop)]
		if euclidean.isLineIntersectingLoops(outlines, pointBegin, pointEnd):
			return True
		addSegmentOutline(False, outlines, pointBegin, pointEnd, width)
	return False

def isIntersectingWithinLists(loop, loopLists):
	"Determine if the loop is intersecting or is within the loop lists."
	for loopList in loopLists:
		if getIsIntersectingWithinList(loop, loopList):
			return True
	return False

copy_reg.pickle(types.MethodType, class_pickler._pickle_method, class_pickler._unpickle_method)
