"""
Triangle Mesh holds the faces and edges of a triangular mesh.

"""

from fabmetheus_utilities.geometry.geometry_tools import face
from fabmetheus_utilities.geometry.geometry_tools import vertex
from fabmetheus_utilities.geometry.geometry_utilities import evaluate
from fabmetheus_utilities.geometry.geometry_utilities import matrix
from fabmetheus_utilities.geometry.solids import group
from fabmetheus_utilities import xml_simple_writer
from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities.vector3index import Vector3Index
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import intercircle
import cmath
import math


__author__ = 'Enrique Perez (perez_enrique@yahoo.com)'
__credits__ = 'Art of Illusion <http://www.artofillusion.org/>'
__date__ = '$Date: 2008/02/05 $'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'


def addEdgePair( edgePairTable, edges, faceEdgeIndex, remainingEdgeIndex, remainingEdgeTable ):
	'Add edge pair to the edge pair table.'
	if faceEdgeIndex == remainingEdgeIndex:
		return
	if not faceEdgeIndex in remainingEdgeTable:
		return
	edgePair = EdgePair().getFromIndexesEdges( [ remainingEdgeIndex, faceEdgeIndex ], edges )
	edgePairTable[ str( edgePair ) ] = edgePair

def addFacesByConcaveLoop(faces, indexedLoop):
	'Add faces from a polygon which is concave.'
	if len(indexedLoop) < 3:
		return
	remainingLoop = indexedLoop[:]
	while len(remainingLoop) > 2:
		remainingLoop = getRemainingLoopAddFace(faces, remainingLoop)

def addFacesByConvex(faces, indexedLoop):
	'Add faces from a convex polygon.'
	if len(indexedLoop) < 3:
		return
	indexBegin = indexedLoop[0].index
	for indexedPointIndex in xrange(1, len(indexedLoop) - 1):
		indexCenter = indexedLoop[indexedPointIndex].index
		indexEnd = indexedLoop[(indexedPointIndex + 1) % len(indexedLoop) ].index
		if indexBegin != indexCenter and indexCenter != indexEnd and indexEnd != indexBegin:
			faceFromConvex = face.Face()
			faceFromConvex.index = len(faces)
			faceFromConvex.vertexIndexes.append(indexBegin)
			faceFromConvex.vertexIndexes.append(indexCenter)
			faceFromConvex.vertexIndexes.append(indexEnd)
			faces.append(faceFromConvex)

def addFacesByConvexBottomTopLoop(faces, indexedLoopBottom, indexedLoopTop):
	'Add faces from loops.'
	for indexedLoopIndex in xrange(max(len(indexedLoopBottom), len(indexedLoopTop))):
		indexedLoopIndexEnd = (indexedLoopIndex + 1) % len(indexedLoopBottom)
		indexedConvex = []
		if len(indexedLoopBottom) > 1:
			indexedConvex.append(indexedLoopBottom[indexedLoopIndex])
			indexedConvex.append(indexedLoopBottom[(indexedLoopIndex + 1) % len(indexedLoopBottom)])
		else:
			indexedConvex.append(indexedLoopBottom[0])
		if len(indexedLoopTop) > 1:
			indexedConvex.append(indexedLoopTop[(indexedLoopIndex + 1) % len(indexedLoopTop)])
			indexedConvex.append(indexedLoopTop[indexedLoopIndex])
		else:
			indexedConvex.append(indexedLoopTop[0])
		addFacesByConvex(faces, indexedConvex)

def addFacesByConvexLoops(faces, indexedLoops):
	'Add faces from loops.'
	if len(indexedLoops) < 2:
		return
	for indexedLoopsIndex in xrange(len(indexedLoops) - 2):
		addFacesByConvexBottomTopLoop(faces, indexedLoops[indexedLoopsIndex], indexedLoops[indexedLoopsIndex + 1])
	indexedLoopBottom = indexedLoops[-2]
	indexedLoopTop = indexedLoops[-1]
	if len(indexedLoopTop) < 1:
		indexedLoopTop = indexedLoops[0]
	addFacesByConvexBottomTopLoop(faces, indexedLoopBottom, indexedLoopTop)

def addFacesByConvexReversed(faces, indexedLoop):
	'Add faces from a reversed convex polygon.'
	addFacesByConvex(faces, indexedLoop[: : -1])

def addFacesByGrid(faces, grid):
	'Add faces from grid.'
	cellTopLoops = getIndexedCellLoopsFromIndexedGrid(grid)
	for cellTopLoop in cellTopLoops:
		addFacesByConvex(faces, cellTopLoop)

def addFacesByLoop(faces, indexedLoop):
	'Add faces from a polygon which may be concave.'
	if len(indexedLoop) < 3:
		return
	lastNormal = None
	for pointIndex, point in enumerate(indexedLoop):
		center = indexedLoop[(pointIndex + 1) % len(indexedLoop)]
		end = indexedLoop[(pointIndex + 2) % len(indexedLoop)]
		normal = euclidean.getNormalWeighted(point, center, end)
		if abs(normal) > 0.0:
			if lastNormal != None:
				if lastNormal.dot(normal) < 0.0:
					addFacesByConcaveLoop(faces, indexedLoop)
					return
			lastNormal = normal
#	totalNormal = Vector3()
#	for pointIndex, point in enumerate(indexedLoop):
#		center = indexedLoop[(pointIndex + 1) % len(indexedLoop)]
#		end = indexedLoop[(pointIndex + 2) % len(indexedLoop)]
#		totalNormal += euclidean.getNormalWeighted(point, center, end)
#	totalNormal.normalize()
	addFacesByConvex(faces, indexedLoop)

def addFacesByLoopReversed(faces, indexedLoop):
	'Add faces from a reversed convex polygon.'
	addFacesByLoop(faces, indexedLoop[: : -1])

def addLoopToPointTable(loop, pointTable):
	'Add the points in the loop to the point table.'
	for point in loop:
		pointTable[point] = None

def addPillarByLoops(faces, indexedLoops):
	'Add pillar by loops which may be concave.'
	if len(indexedLoops) < 1:
		return
	if len(indexedLoops[-1]) < 1:
		addFacesByConvexLoops(faces, indexedLoops)
		return
	addFacesByLoopReversed(faces, indexedLoops[0])
	addFacesByConvexLoops(faces, indexedLoops)
	addFacesByLoop(faces, indexedLoops[-1])

def addPillarFromConvexLoopsGrids(faces, indexedGrids, indexedLoops):
	'Add pillar from convex loops and grids.'
	cellBottomLoops = getIndexedCellLoopsFromIndexedGrid(indexedGrids[0])
	for cellBottomLoop in cellBottomLoops:
		addFacesByConvexReversed(faces, cellBottomLoop)
	addFacesByConvexLoops(faces, indexedLoops)
	addFacesByGrid(faces, indexedGrids[-1])

def addPillarFromConvexLoopsGridTop(faces, indexedGridTop, indexedLoops):
	'Add pillar from convex loops and grid top.'
	addFacesByLoopReversed(faces, indexedLoops[0])
	addFacesByConvexLoops(faces, indexedLoops)
	addFacesByGrid(faces, indexedGridTop)

def addPointsAtZ(edgePair, points, radius, vertexes, z):
	'Add point complexes on the segment between the edge intersections with z.'
	carveIntersectionFirst = getCarveIntersectionFromEdge(edgePair.edges[0], vertexes, z)
	carveIntersectionSecond = getCarveIntersectionFromEdge(edgePair.edges[1], vertexes, z)
	# threshold radius above 0.8 can create extra holes on Screw Holder, 0.7 should be safe for everything
	intercircle.addPointsFromSegment(carveIntersectionFirst, carveIntersectionSecond, points, radius, 0.7)

def addSymmetricXPath(outputs, path, x):
	'Add x path output to outputs.'
	vertexes = []
	loops = [getSymmetricXLoop(path, vertexes, -x), getSymmetricXLoop(path, vertexes, x)]
	outputs.append(getPillarOutput(loops))

def addSymmetricXPaths(outputs, paths, x):
	'Add x paths outputs to outputs.'
	for path in paths:
		addSymmetricXPath(outputs, path, x)

def addSymmetricYPath(outputs, path, y):
	'Add y path output to outputs.'
	vertexes = []
	loops = [getSymmetricYLoop(path, vertexes, -y), getSymmetricYLoop(path, vertexes, y)]
	outputs.append(getPillarOutput(loops))

def addSymmetricYPaths(outputs, paths, y):
	'Add y paths outputs to outputs.'
	for path in paths:
		addSymmetricYPath(outputs, path, y)

def addWithLeastLength(importRadius, loops, point):
	'Insert a point into a loop, at the index at which the loop would be shortest.'
	close = importRadius + importRadius
	shortestAdditionalLength = close
	shortestLoop = None
	shortestPointIndex = None
	for loop in loops:
		if len(loop) > 3:
			for pointIndex in xrange(len(loop)):
				additionalLoopLength = getAdditionalLoopLength(loop, point, pointIndex)
				if additionalLoopLength < shortestAdditionalLength:
					if getIsPointCloseInline(close, loop, point, pointIndex):
						shortestAdditionalLength = additionalLoopLength
						shortestLoop = loop
						shortestPointIndex = pointIndex
	if shortestPointIndex != None:
		shortestLoop.insert( shortestPointIndex, point )

def convertXMLElement(geometryOutput, xmlElement):
	'Convert the xml element to a TriangleMesh xml element.'
	xmlElement.linkObject(TriangleMesh())
	matrix.getBranchMatrixSetXMLElement(xmlElement)
	vertex.addGeometryList(geometryOutput['vertex'], xmlElement)
	face.addGeometryList(geometryOutput['face'], xmlElement)
	xmlElement.getXMLProcessor().processChildNodes(xmlElement)

def getAddIndexedGrid( grid, vertexes, z ):
	'Get and add an indexed grid.'
	indexedGrid = []
	for row in grid:
		indexedRow = []
		indexedGrid.append( indexedRow )
		for pointComplex in row:
			vector3index = Vector3Index( len(vertexes), pointComplex.real, pointComplex.imag, z )
			indexedRow.append(vector3index)
			vertexes.append(vector3index)
	return indexedGrid

def getAddIndexedLoop(loop, vertexes, z):
	'Get and add an indexed loop.'
	indexedLoop = []
	for index in xrange(len(loop)):
		pointComplex = loop[index]
		vector3index = Vector3Index(len(vertexes), pointComplex.real, pointComplex.imag, z)
		indexedLoop.append(vector3index)
		vertexes.append(vector3index)
	return indexedLoop

def getAddIndexedLoops( loop, vertexes, zList ):
	'Get and add indexed loops.'
	indexedLoops = []
	for z in zList:
		indexedLoop = getAddIndexedLoop( loop, vertexes, z )
		indexedLoops.append(indexedLoop)
	return indexedLoops

def getAdditionalLoopLength(loop, point, pointIndex):
	'Get the additional length added by inserting a point into a loop.'
	afterPoint = loop[pointIndex]
	beforePoint = loop[(pointIndex + len(loop) - 1) % len(loop)]
	return abs(point - beforePoint) + abs(point - afterPoint) - abs(afterPoint - beforePoint)

def getBridgeDirection( belowLoops, layerLoops, layerThickness ):
	'Get span direction for the majority of the overhanging extrusion perimeter, if any.'
	if len( belowLoops ) < 1:
		return None
	belowOutsetLoops = []
	overhangInset = 1.875 * layerThickness
	slightlyGreaterThanOverhang = 1.1 * overhangInset
	for loop in belowLoops:
		centers = intercircle.getCentersFromLoopDirection( True, loop, slightlyGreaterThanOverhang )
		for center in centers:
			outset = intercircle.getSimplifiedInsetFromClockwiseLoop( center, overhangInset )
			if intercircle.isLargeSameDirection( outset, center, overhangInset ):
				belowOutsetLoops.append( outset )
	bridgeRotation = complex()
	for loop in layerLoops:
		for pointIndex in xrange(len(loop)):
			previousIndex = ( pointIndex + len(loop) - 1 ) % len(loop)
			bridgeRotation += getOverhangDirection( belowOutsetLoops, loop[ previousIndex ], loop[pointIndex] )
	if abs( bridgeRotation ) < 0.7853 * layerThickness:
		return None
	else:
		bridgeRotation /= abs( bridgeRotation )
		return cmath.sqrt( bridgeRotation )

def getBridgeLoops( layerThickness, loop ):
	'Get the inset bridge loops from the loop.'
	halfWidth = 1.5 * layerThickness
	slightlyGreaterThanHalfWidth = 1.1 * halfWidth
	extrudateLoops = []
	centers = intercircle.getCentersFromLoop( loop, slightlyGreaterThanHalfWidth )
	for center in centers:
		extrudateLoop = intercircle.getSimplifiedInsetFromClockwiseLoop( center, halfWidth )
		if intercircle.isLargeSameDirection( extrudateLoop, center, halfWidth ):
			if euclidean.isPathInsideLoop( loop, extrudateLoop ) == euclidean.isWiddershins(loop):
				extrudateLoop.reverse()
				extrudateLoops.append( extrudateLoop )
	return extrudateLoops

def getCarveIntersectionFromEdge(edge, vertexes, z):
	'Get the complex where the carve intersects the edge.'
	firstVertex = vertexes[ edge.vertexIndexes[0] ]
	firstVertexComplex = firstVertex.dropAxis()
	secondVertex = vertexes[ edge.vertexIndexes[1] ]
	secondVertexComplex = secondVertex.dropAxis()
	zMinusFirst = z - firstVertex.z
	up = secondVertex.z - firstVertex.z
	return zMinusFirst * ( secondVertexComplex - firstVertexComplex ) / up + firstVertexComplex

def getDescendingAreaLoops(allPoints, corners, importRadius):
	'Get descending area loops which include most of the points.'
	loops = intercircle.getCentersFromPoints(allPoints, importRadius)
	descendingAreaLoops = []
	sortLoopsInOrderOfArea(True, loops)
	pointDictionary = {}
	for loop in loops:
		if len(loop) > 2 and getOverlapRatio(loop, pointDictionary) < 0.2:
			intercircle.directLoop(not euclidean.getIsInFilledRegion(descendingAreaLoops, loop[0]), loop)
			descendingAreaLoops.append(loop)
			addLoopToPointTable(loop, pointDictionary)
	descendingAreaLoops = euclidean.getSimplifiedLoops(descendingAreaLoops, importRadius)
	return getLoopsWithCorners(corners, importRadius, descendingAreaLoops, pointDictionary)

def getDescendingAreaOrientedLoops(allPoints, corners, importRadius):
	'Get descending area oriented loops which include most of the points.'
	return getOrientedLoops(getDescendingAreaLoops(allPoints, corners, importRadius))

def getDoubledRoundZ( overhangingSegment, segmentRoundZ ):
	'Get doubled plane angle around z of the overhanging segment.'
	endpoint = overhangingSegment[0]
	roundZ = endpoint.point - endpoint.otherEndpoint.point
	roundZ *= segmentRoundZ
	if abs( roundZ ) == 0.0:
		return complex()
	if roundZ.real < 0.0:
		roundZ *= - 1.0
	roundZLength = abs( roundZ )
	return roundZ * roundZ / roundZLength

def getGeometryOutputByFacesVertexes(faces, vertexes):
	'Get geometry output dictionary by faces and vertexes.'
	return {'trianglemesh' : {'vertex' : vertexes, 'face' : faces}}

def getGeometryOutputCopy(object):
	'Get the geometry output copy.'
	objectClass = object.__class__
	if objectClass == dict:
		objectCopy = {}
		for key in object:
			objectCopy[key] = getGeometryOutputCopy(object[key])
		return objectCopy
	if objectClass == list:
		objectCopy = []
		for value in object:
			objectCopy.append(getGeometryOutputCopy(value))
		return objectCopy
	if objectClass == face.Face or objectClass == Vector3 or objectClass == Vector3Index:
		return object.copy()
	return object

def getIndexedCellLoopsFromIndexedGrid( grid ):
	'Get indexed cell loops from an indexed grid.'
	indexedCellLoops = []
	for rowIndex in xrange( len( grid ) - 1 ):
		rowBottom = grid[ rowIndex ]
		rowTop = grid[ rowIndex + 1 ]
		for columnIndex in xrange( len( rowBottom ) - 1 ):
			columnIndexEnd = columnIndex + 1
			indexedConvex = []
			indexedConvex.append( rowBottom[ columnIndex ] )
			indexedConvex.append( rowBottom[ columnIndex + 1 ] )
			indexedConvex.append( rowTop[ columnIndex + 1 ] )
			indexedConvex.append( rowTop[ columnIndex ] )
			indexedCellLoops.append( indexedConvex )
	return indexedCellLoops

def getIndexedLoopFromIndexedGrid( indexedGrid ):
	'Get indexed loop from around the indexed grid.'
	indexedLoop = indexedGrid[0][:]
	for row in indexedGrid[1 : -1]:
		indexedLoop.append( row[-1] )
	indexedLoop += indexedGrid[-1][: : -1]
	for row in indexedGrid[ len( indexedGrid ) - 2 : 0 : - 1 ]:
		indexedLoop.append( row[0] )
	return indexedLoop

def getInsetPoint( loop, tinyRadius ):
	'Get the inset vertex.'
	pointIndex = getWideAnglePointIndex(loop)
	point = loop[ pointIndex % len(loop) ]
	afterPoint = loop[(pointIndex + 1) % len(loop)]
	beforePoint = loop[ ( pointIndex - 1 ) % len(loop) ]
	afterSegmentNormalized = euclidean.getNormalized( afterPoint - point )
	beforeSegmentNormalized = euclidean.getNormalized( beforePoint - point )
	afterClockwise = complex( afterSegmentNormalized.imag, - afterSegmentNormalized.real )
	beforeWiddershins = complex( - beforeSegmentNormalized.imag, beforeSegmentNormalized.real )
	midpoint = afterClockwise + beforeWiddershins
	midpointNormalized = midpoint / abs( midpoint )
	return point + midpointNormalized * tinyRadius

def getIsPointCloseInline(close, loop, point, pointIndex):
	'Insert a point into a loop, at the index at which the loop would be shortest.'
	afterCenterComplex = loop[pointIndex]
	if abs(afterCenterComplex - point) > close:
		return False
	afterEndComplex = loop[(pointIndex + 1) % len(loop)]
	if not isInline( point, afterCenterComplex, afterEndComplex ):
		return False
	beforeCenterComplex = loop[(pointIndex + len(loop) - 1) % len(loop)]
	if abs(beforeCenterComplex - point) > close:
		return False
	beforeEndComplex = loop[(pointIndex + len(loop) - 2) % len(loop)]
	return isInline(point, beforeCenterComplex, beforeEndComplex)

def getIsPathEntirelyOutsideTriangle(begin, center, end, vector3Path):
	'Determine if a path is entirely outside another loop.'
	loop = [begin.dropAxis(), center.dropAxis(), end.dropAxis()]
	for vector3 in vector3Path:
		point = vector3.dropAxis()
		if euclidean.isPointInsideLoop(loop, point):
			return False
	return True

def getLoopsFromCorrectMesh( edges, faces, vertexes, z ):
	'Get loops from a carve of a correct mesh.'
	remainingEdgeTable = getRemainingEdgeTable(edges, vertexes, z)
	remainingValues = remainingEdgeTable.values()
	for edge in remainingValues:
		if len( edge.faceIndexes ) < 2:
			print('This should never happen, there is a hole in the triangle mesh, each edge should have two faces.')
			print(edge)
			print('Something will still be printed, but there is no guarantee that it will be the correct shape.' )
			print('Once the gcode is saved, you should check over the layer with a z of:')
			print(z)
			return []
	loops = []
	while isPathAdded( edges, faces, loops, remainingEdgeTable, vertexes, z ):
		pass
	if euclidean.isLoopListIntersecting(loops):
		print('Warning, the triangle mesh slice intersects itself in getLoopsFromCorrectMesh in triangle_mesh.')
		print('Something will still be printed, but there is no guarantee that it will be the correct shape.')
		print('Once the gcode is saved, you should check over the layer with a z of:')
		print(z)
		return []
	return loops
#	untouchables = []
#	for boundingLoop in boundingLoops:
#		if not boundingLoop.isIntersectingList( untouchables ):
#			untouchables.append( boundingLoop )
#	if len( untouchables ) < len( boundingLoops ):
#		print('This should never happen, the carve layer intersects itself. Something will still be printed, but there is no guarantee that it will be the correct shape.')
#		print('Once the gcode is saved, you should check over the layer with a z of:')
#		print(z)
#	remainingLoops = []
#	for untouchable in untouchables:
#		remainingLoops.append( untouchable.loop )
#	return remainingLoops

def getLoopsFromUnprovenMesh(edges, faces, importRadius, vertexes, z):
	'Get loops from a carve of an unproven mesh.'
	edgePairTable = {}
	corners = []
	remainingEdgeTable = getRemainingEdgeTable(edges, vertexes, z)
	remainingEdgeTableKeys = remainingEdgeTable.keys()
	for remainingEdgeIndexKey in remainingEdgeTable:
		edge = remainingEdgeTable[remainingEdgeIndexKey]
		carveIntersection = getCarveIntersectionFromEdge(edge, vertexes, z)
		corners.append(carveIntersection)
		for edgeFaceIndex in edge.faceIndexes:
			face = faces[edgeFaceIndex]
			for edgeIndex in face.edgeIndexes:
				addEdgePair(edgePairTable, edges, edgeIndex, remainingEdgeIndexKey, remainingEdgeTable)
	allPoints = corners[:]
	for edgePairValue in edgePairTable.values():
		addPointsAtZ(edgePairValue, allPoints, importRadius, vertexes, z)
	pointTable = {}
	return getDescendingAreaLoops(allPoints, corners, importRadius)

def getLoopsWithCorners(corners, importRadius, loops, pointTable):
	'Add corners to the loops.'
	for corner in corners:
		if corner not in pointTable:
			addWithLeastLength(importRadius, loops, corner)
			pointTable[corner] = None
	return euclidean.getSimplifiedLoops(loops, importRadius)

def getNextEdgeIndexAroundZ( edge, faces, remainingEdgeTable ):
	'Get the next edge index in the mesh carve.'
	for faceIndex in edge.faceIndexes:
		face = faces[ faceIndex ]
		for edgeIndex in face.edgeIndexes:
			if edgeIndex in remainingEdgeTable:
				return edgeIndex
	return - 1

def getOrientedLoops(loops):
	'Orient the loops which must be in descending order.'
	for loopIndex, loop in enumerate(loops):
		leftPoint = euclidean.getLeftPoint(loop)
		isInFilledRegion = euclidean.getIsInFilledRegion(loops[: loopIndex] + loops[loopIndex + 1 :], leftPoint)
		if isInFilledRegion == euclidean.isWiddershins(loop):
			loop.reverse()
	return loops

def getOverhangDirection( belowOutsetLoops, segmentBegin, segmentEnd ):
	'Add to span direction from the endpoint segments which overhang the layer below.'
	segment = segmentEnd - segmentBegin
	normalizedSegment = euclidean.getNormalized( complex( segment.real, segment.imag ) )
	segmentYMirror = complex(normalizedSegment.real, -normalizedSegment.imag)
	segmentBegin = segmentYMirror * segmentBegin
	segmentEnd = segmentYMirror * segmentEnd
	solidXIntersectionList = []
	y = segmentBegin.imag
	solidXIntersectionList.append( euclidean.XIntersectionIndex( - 1.0, segmentBegin.real ) )
	solidXIntersectionList.append( euclidean.XIntersectionIndex( - 1.0, segmentEnd.real ) )
	for belowLoopIndex in xrange( len( belowOutsetLoops ) ):
		belowLoop = belowOutsetLoops[ belowLoopIndex ]
		rotatedOutset = euclidean.getPointsRoundZAxis( segmentYMirror, belowLoop )
		euclidean.addXIntersectionIndexesFromLoopY( rotatedOutset, belowLoopIndex, solidXIntersectionList, y )
	overhangingSegments = euclidean.getSegmentsFromXIntersectionIndexes( solidXIntersectionList, y )
	overhangDirection = complex()
	for overhangingSegment in overhangingSegments:
		overhangDirection += getDoubledRoundZ( overhangingSegment, normalizedSegment )
	return overhangDirection

def getOverlapRatio( loop, pointTable ):
	'Get the overlap ratio between the loop and the point table.'
	numberOfOverlaps = 0
	for point in loop:
		if point in pointTable:
			numberOfOverlaps += 1
	return float( numberOfOverlaps ) / float(len(loop))

def getPath( edges, pathIndexes, loop, z ):
	'Get the path from the edge intersections.'
	path = []
	for pathIndexIndex in xrange( len( pathIndexes ) ):
		pathIndex = pathIndexes[ pathIndexIndex ]
		edge = edges[ pathIndex ]
		carveIntersection = getCarveIntersectionFromEdge( edge, loop, z )
		path.append( carveIntersection )
	return path

def getPillarOutput(loops):
	'Get pillar output.'
	faces = []
	vertexes = getUniqueVertexes(loops)
	addPillarByLoops(faces, loops)
	return getGeometryOutputByFacesVertexes(faces, vertexes)

def getPillarsOutput(loopLists):
	'Get pillars output.'
	pillarsOutput = []
	for loopList in loopLists:
		pillarsOutput.append(getPillarOutput(loopList))
	return getUnifiedOutput(pillarsOutput)

def getRemainingEdgeTable(edges, vertexes, z):
	'Get the remaining edge hashtable.'
	remainingEdgeTable = {}
	if len(edges) > 0:
		if edges[0].zMinimum == None:
			for edge in edges:
				setEdgeMaximumMinimum(edge, vertexes)
	for edgeIndex in xrange(len(edges)):
		edge = edges[edgeIndex]
		if (edge.zMinimum < z) and (edge.zMaximum > z):
			remainingEdgeTable[edgeIndex] = edge
	return remainingEdgeTable

def getRemainingLoopAddFace(faces, remainingLoop):
	'Get the remaining loop and add face.'
	for indexedVertexIndex, indexedVertex in enumerate(remainingLoop):
		nextIndex = (indexedVertexIndex + 1) % len(remainingLoop)
		previousIndex = (indexedVertexIndex + len(remainingLoop) - 1) % len(remainingLoop)
		nextVertex = remainingLoop[nextIndex]
		previousVertex = remainingLoop[previousIndex]
		remainingPath = euclidean.getAroundLoop((indexedVertexIndex + 2) % len(remainingLoop), previousIndex, remainingLoop)
		if len(remainingLoop) < 4 or getIsPathEntirelyOutsideTriangle(previousVertex, indexedVertex, nextVertex, remainingPath):
			faceConvex = face.Face()
			faceConvex.index = len(faces)
			faceConvex.vertexIndexes.append(indexedVertex.index)
			faceConvex.vertexIndexes.append(nextVertex.index)
			faceConvex.vertexIndexes.append(previousVertex.index)
			faces.append(faceConvex)
			return euclidean.getAroundLoop(nextIndex, indexedVertexIndex, remainingLoop)
	print('Warning, could not decompose polygon in getRemainingLoopAddFace in trianglemesh for:')
	print(remainingLoop)
	return []

def getSharedFace( firstEdge, faces, secondEdge ):
	'Get the face which is shared by two edges.'
	for firstEdgeFaceIndex in firstEdge.faceIndexes:
		for secondEdgeFaceIndex in secondEdge.faceIndexes:
			if firstEdgeFaceIndex == secondEdgeFaceIndex:
				return faces[ firstEdgeFaceIndex ]
	return None

def getSymmetricXLoop(path, vertexes, x):
	'Get symmetrix x loop.'
	loop = []
	for point in path:
		vector3Index = Vector3Index(len(vertexes), x, point.real, point.imag)
		loop.append(vector3Index)
		vertexes.append(vector3Index)
	return loop

def getSymmetricYLoop(path, vertexes, y):
	'Get symmetrix y loop.'
	loop = []
	for point in path:
		vector3Index = Vector3Index(len(vertexes), point.real, y, point.imag)
		loop.append(vector3Index)
		vertexes.append(vector3Index)
	return loop

def getUnifiedOutput(outputs):
	'Get unified output.'
	if len(outputs) < 1:
		return {}
	if len(outputs) == 1:
		return outputs[0]
	return {'union' : {'shapes' : outputs}}

def getUniqueVertexes(loops):
	'Get unique vertexes.'
	vertexDictionary = {}
	uniqueVertexes = []
	for loop in loops:
		for vertexIndex, vertex in enumerate(loop):
			vertexTuple = (vertex.x, vertex.y, vertex.z)
			if vertexTuple in vertexDictionary:
				loop[vertexIndex] = vertexDictionary[vertexTuple]
			else:
				if vertex.__class__ == Vector3Index:
					loop[vertexIndex].index = len(vertexDictionary)
				else:
					loop[vertexIndex] = Vector3Index(len(vertexDictionary), vertex.x, vertex.y, vertex.z)
				vertexDictionary[vertexTuple] = loop[vertexIndex]
				uniqueVertexes.append(loop[vertexIndex])
	return uniqueVertexes

def getWideAnglePointIndex(loop):
	'Get a point index which has a wide enough angle, most point indexes have a wide enough angle, this is just to make sure.'
	dotProductMinimum = 9999999.9
	widestPointIndex = 0
	for pointIndex in xrange(len(loop)):
		point = loop[ pointIndex % len(loop) ]
		afterPoint = loop[(pointIndex + 1) % len(loop)]
		beforePoint = loop[ ( pointIndex - 1 ) % len(loop) ]
		afterSegmentNormalized = euclidean.getNormalized( afterPoint - point )
		beforeSegmentNormalized = euclidean.getNormalized( beforePoint - point )
		dotProduct = euclidean.getDotProduct( afterSegmentNormalized, beforeSegmentNormalized )
		if dotProduct < .99:
			return pointIndex
		if dotProduct < dotProductMinimum:
			dotProductMinimum = dotProduct
			widestPointIndex = pointIndex
	return widestPointIndex

def getZAddExtruderPathsBySolidCarving(rotatedLoopLayer, solidCarving, z):
	'Get next z and add extruder loops by solid carving.'
	solidCarving.rotatedLoopLayers.append(rotatedLoopLayer)
	nextZ = z + solidCarving.layerThickness
	if not solidCarving.infillInDirectionOfBridge:
		return nextZ
	allExtrudateLoops = []
	for loop in rotatedLoopLayer.loops:
		allExtrudateLoops += getBridgeLoops(solidCarving.layerThickness, loop)
	rotatedLoopLayer.rotation = getBridgeDirection(solidCarving.belowLoops, allExtrudateLoops, solidCarving.layerThickness)
	solidCarving.belowLoops = allExtrudateLoops
	return nextZ

def isInline( beginComplex, centerComplex, endComplex ):
	'Determine if the three complex points form a line.'
	centerBeginComplex = beginComplex - centerComplex
	centerEndComplex = endComplex - centerComplex
	centerBeginLength = abs( centerBeginComplex )
	centerEndLength = abs( centerEndComplex )
	if centerBeginLength <= 0.0 or centerEndLength <= 0.0:
		return False
	centerBeginComplex /= centerBeginLength
	centerEndComplex /= centerEndLength
	return euclidean.getDotProduct( centerBeginComplex, centerEndComplex ) < -0.999

def isPathAdded( edges, faces, loops, remainingEdgeTable, vertexes, z ):
	'Get the path indexes around a triangle mesh carve and add the path to the flat loops.'
	if len( remainingEdgeTable ) < 1:
		return False
	pathIndexes = []
	remainingEdgeIndexKey = remainingEdgeTable.keys()[0]
	pathIndexes.append( remainingEdgeIndexKey )
	del remainingEdgeTable[remainingEdgeIndexKey]
	nextEdgeIndexAroundZ = getNextEdgeIndexAroundZ( edges[remainingEdgeIndexKey], faces, remainingEdgeTable )
	while nextEdgeIndexAroundZ != - 1:
		pathIndexes.append( nextEdgeIndexAroundZ )
		del remainingEdgeTable[ nextEdgeIndexAroundZ ]
		nextEdgeIndexAroundZ = getNextEdgeIndexAroundZ( edges[ nextEdgeIndexAroundZ ], faces, remainingEdgeTable )
	if len( pathIndexes ) < 3:
		print('Dangling edges, will use intersecting circles to get import layer at height %s' % z)
		del loops[:]
		return False
	loops.append( getPath( edges, pathIndexes, vertexes, z ) )
	return True

def processXMLElement(xmlElement):
	'Process the xml element.'
	evaluate.processArchivable(TriangleMesh, xmlElement)

def setEdgeMaximumMinimum(edge, vertexes):
	'Set the edge maximum and minimum.'
	beginIndex = edge.vertexIndexes[0]
	endIndex = edge.vertexIndexes[1]
	if beginIndex >= len(vertexes) or endIndex >= len(vertexes):
		print('Warning, there are duplicate vertexes in setEdgeMaximumMinimum in triangle_mesh.')
		print('Something might still be printed, but there is no guarantee that it will be the correct shape.' )
		edge.zMaximum = -987654321.0
		edge.zMinimum = -987654321.0
		return
	beginZ = vertexes[beginIndex].z
	endZ = vertexes[endIndex].z
	edge.zMinimum = min(beginZ, endZ)
	edge.zMaximum = max(beginZ, endZ)

def sortLoopsInOrderOfArea(isDescending, loops):
	'Sort the loops in the order of area according isDescending.'
	loops.sort(key=euclidean.getAreaLoopAbsolute, reverse=isDescending)


class EdgePair:
	def __init__(self):
		'Pair of edges on a face.'
		self.edgeIndexes = []
		self.edges = []

	def __repr__(self):
		'Get the string representation of this EdgePair.'
		return str( self.edgeIndexes )

	def getFromIndexesEdges( self, edgeIndexes, edges ):
		'Initialize from edge indices.'
		self.edgeIndexes = edgeIndexes[:]
		self.edgeIndexes.sort()
		for edgeIndex in self.edgeIndexes:
			self.edges.append( edges[ edgeIndex ] )
		return self


class TriangleMesh( group.Group ):
	'A triangle mesh.'
	def __init__(self):
		'Add empty lists.'
		group.Group.__init__(self)
		self.belowLoops = []
		self.infillInDirectionOfBridge = False
		self.edges = []
		self.faces = []
		self.importCoarseness = 1.0
		self.isCorrectMesh = True
		self.oldChainTetragrid = None
		self.rotatedLoopLayers = []
		self.transformedVertexes = None
		self.vertexes = []

	def addXMLSection(self, depth, output):
		'Add the xml section for this object.'
		xml_simple_writer.addXMLFromVertexes( depth, output, self.vertexes )
		xml_simple_writer.addXMLFromObjects( depth, self.faces, output )

	def getCarveCornerMaximum(self):
		'Get the corner maximum of the vertexes.'
		return self.cornerMaximum

	def getCarveCornerMinimum(self):
		'Get the corner minimum of the vertexes.'
		return self.cornerMinimum

	def getCarveLayerThickness(self):
		'Get the layer thickness.'
		return self.layerThickness

	def getCarveRotatedBoundaryLayers(self):
		'Get the rotated boundary layers.'
		if self.getMinimumZ() == None:
			return []
		halfHeight = 0.5 * self.layerThickness
		self.zoneArrangement = ZoneArrangement(self.layerThickness, self.getTransformedVertexes())
		layerTop = self.cornerMaximum.z - halfHeight * 0.5
		z = self.cornerMinimum.z + halfHeight
		while z < layerTop:
			z = self.getZAddExtruderPaths(z)
		return self.rotatedLoopLayers

	def getFabmetheusXML(self):
		'Return the fabmetheus XML.'
		return None

	def getGeometryOutput(self):
		'Get geometry output dictionary.'
		return getGeometryOutputByFacesVertexes(self.faces, self.vertexes)

	def getInterpretationSuffix(self):
		'Return the suffix for a triangle mesh.'
		return 'xml'

	def getLoops(self, importRadius, z):
		'Get loops sliced through shape.'
		self.importRadius = importRadius
		return self.getLoopsFromMesh(z)

	def getLoopsFromMesh( self, z ):
		'Get loops from a carve of a mesh.'
		originalLoops = []
		self.setEdgesForAllFaces()
		if self.isCorrectMesh:
			originalLoops = getLoopsFromCorrectMesh( self.edges, self.faces, self.getTransformedVertexes(), z )
		if len( originalLoops ) < 1:
			originalLoops = getLoopsFromUnprovenMesh( self.edges, self.faces, self.importRadius, self.getTransformedVertexes(), z )
		loops = euclidean.getSimplifiedLoops(originalLoops, self.importRadius)
		sortLoopsInOrderOfArea(True, loops)
		return getOrientedLoops(loops)

	def getMinimumZ(self):
		'Get the minimum z.'
		self.cornerMaximum = Vector3(-987654321.0, -987654321.0, -987654321.0)
		self.cornerMinimum = Vector3(987654321.0, 987654321.0, 987654321.0)
		transformedVertexes = self.getTransformedVertexes()
		if len(transformedVertexes) < 1:
			return None
		for point in transformedVertexes:
			self.cornerMaximum.maximize(point)
			self.cornerMinimum.minimize(point)
		return self.cornerMinimum.z

	def getTransformedVertexes(self):
		'Get all transformed vertexes.'
		if self.xmlElement == None:
			return self.vertexes
		chainTetragrid = self.getMatrixChainTetragrid()
		if self.oldChainTetragrid != chainTetragrid:
			self.oldChainTetragrid = chainTetragrid
			self.transformedVertexes = None
		if self.transformedVertexes == None:
			if len(self.edges) > 0:
				self.edges[0].zMinimum = None
			self.transformedVertexes = matrix.getTransformedVector3s(chainTetragrid, self.vertexes)
		return self.transformedVertexes

	def getTriangleMeshes(self):
		'Get all triangleMeshes.'
		return [self]

	def getVertexes(self):
		'Get all vertexes.'
		self.transformedVertexes = None
		return self.vertexes

	def getZAddExtruderPaths(self, z):
		'Get next z and add extruder loops.'
		#settings.printProgress(len(self.rotatedLoopLayers), 'slice')
		
		rotatedLoopLayer = euclidean.RotatedLoopLayer(z)
		rotatedLoopLayer.loops = self.getLoopsFromMesh(self.zoneArrangement.getEmptyZ(z))
		return getZAddExtruderPathsBySolidCarving(rotatedLoopLayer, self, z)

	def liftByMinimumZ(self, minimumZ):
		'Lift the triangle mesh to the altitude.'
		altitude = evaluate.getEvaluatedFloat(None, 'altitude', self.xmlElement)
		if altitude == None:
			return
		lift = altitude - minimumZ
		for vertex in self.vertexes:
			vertex.z += lift

	def setCarveInfillInDirectionOfBridge( self, infillInDirectionOfBridge ):
		'Set the infill in direction of bridge.'
		self.infillInDirectionOfBridge = infillInDirectionOfBridge

	def setCarveLayerThickness( self, layerThickness ):
		'Set the layer thickness.'
		self.layerThickness = layerThickness

	def setCarveImportRadius( self, importRadius ):
		'Set the import radius.'
		self.importRadius = importRadius

	def setCarveIsCorrectMesh( self, isCorrectMesh ):
		'Set the is correct mesh flag.'
		self.isCorrectMesh = isCorrectMesh

	def setEdgesForAllFaces(self):
		'Set the face edges of all the faces.'
		edgeTable = {}
		for face in self.faces:
			face.setEdgeIndexesToVertexIndexes( self.edges, edgeTable )


class ZoneArrangement:
	'A zone arrangement.'
	def __init__(self, layerThickness, vertexes):
		'Initialize the zone interval and the zZone table.'
		self.zoneInterval = layerThickness / math.sqrt(len(vertexes)) / 1000.0
		self.zZoneSet = set()
		for point in vertexes:
			zoneIndexFloat = point.z / self.zoneInterval
			self.zZoneSet.add(math.floor(zoneIndexFloat))
			self.zZoneSet.add(math.ceil(zoneIndexFloat ))

	def getEmptyZ(self, z):
		'Get the first z which is not in the zone table.'
		zoneIndex = round(z / self.zoneInterval)
		if zoneIndex not in self.zZoneSet:
			return z
		zoneAround = 1
		while 1:
			zoneDown = zoneIndex - zoneAround
			if zoneDown not in self.zZoneSet:
				return zoneDown * self.zoneInterval
			zoneUp = zoneIndex + zoneAround
			if zoneUp not in self.zZoneSet:
				return zoneUp * self.zoneInterval
			zoneAround += 1
