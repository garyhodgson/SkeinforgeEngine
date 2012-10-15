from StringIO import StringIO
from collections import OrderedDict
from config import config
from fabmetheus_utilities import euclidean
from fabmetheus_utilities.vector3 import Vector3
from math import pi
from paths import BoundaryPerimeter, Loop, InfillPath
from utilities import memory_tracker
import math
import sys
import time


class NestedRing:
    def __init__(self, z, runtimeParameters):
       
        if runtimeParameters.profileMemory:
            memory_tracker.track_object(self)
        
        self.runtimeParameters = runtimeParameters
        self.decimalPlaces = self.runtimeParameters.decimalPlaces
        self.z = z
        
        self.perimeter = None
        self.loops = []
        self.infillPaths = []

        self.innerNestedRings = []
        
        # can the following be removed? only used whilst generating the infill?
        self.infillPathsHolder = []
        self.extraLoops = []
        self.penultimateFillLoops = []
        self.lastFillLoops = None        
        ###
                
        self.bridgeFeedRateMinute = self.runtimeParameters.bridgeFeedRateMinute
        self.perimeterFeedRateMinute = self.runtimeParameters.perimeterFeedRateMinute
        self.extrusionFeedRateMinute = self.runtimeParameters.extrusionFeedRateMinute
        self.travelFeedRateMinute = self.runtimeParameters.travelFeedRateMinute
        self.extrusionUnitsRelative = self.runtimeParameters.extrusionUnitsRelative
        
        self.oozeRate = self.runtimeParameters.oozeRate
        self.zDistanceRatio = 5.0
        self.extruderRetractionSpeedMinute = round(60.0 * self.runtimeParameters.extruderRetractionSpeed, self.decimalPlaces)

        self.layerThickness = self.runtimeParameters.layerThickness
        self.perimeterWidth = self.runtimeParameters.perimeterWidth
        self.filamentDiameter = self.runtimeParameters.filamentDiameter
        self.filamentPackingDensity = self.runtimeParameters.filamentPackingDensity
        self.absolutePositioning = config.getboolean('preface', 'positioning.absolute')
        self.flowRate = self.runtimeParameters.flowRate
        self.perimeterFlowRate = self.runtimeParameters.perimeterFlowRate
        self.bridgeFlowRate = self.runtimeParameters.bridgeFlowRate
        self.previousPoint = None
        filamentRadius = 0.5 * self.filamentDiameter
        filamentPackingArea = pi * filamentRadius * filamentRadius * self.filamentPackingDensity
        extrusionArea = pi * self.layerThickness ** 2 / 4 + self.layerThickness * (self.perimeterWidth - self.layerThickness)
            #http://hydraraptor.blogspot.sk/2011/03/spot-on-flow-rate.html
        self.flowScaleSixty = 60.0 * extrusionArea / filamentPackingArea
        
    def __str__(self):
        output = StringIO()
        output.write('\n%4s#########################################' % '')
        output.write('\n%8snestedRing:' % '')
        
        output.write('\n%10sboundaryPerimeter:\n' % '')
        output.write(self.perimeter)

        output.write('\n%10sinnerNestedRings:\n' % '')
        for innerNestedRing in self.innerNestedRings:
            output.write('%12s%s\n' % ('', innerNestedRing))
                    
        output.write('\n%10sloops:\n' % '')
        for loop in self.loops:
            output.write(loop)
        
        output.write('\n%10sextraLoops:\n' % '')
        for extraLoop in self.extraLoops:
            output.write('%12s%s\n' % ('', extraLoop))
            
        output.write('\n%10spenultimateFillLoops:\n' % '')
        for penultimateFillLoop in self.penultimateFillLoops:
            output.write('%12s%s\n' % ('', penultimateFillLoop))
        
        output.write('\n%10slastFillLoops:\n' % '')
        if self.lastFillLoops != None:
            for lastFillLoop in self.lastFillLoops:
                output.write('%12s%s\n' % ('', lastFillLoop))
            
        output.write('\n%10sinfillPaths:\n' % '')
        for infillPath in self.infillPaths:
            output.write(infillPath)
            
        output.write('\n%4s###### end nestedRing ########################' % '')
                    
        return output.getvalue()
    
    
    def getDistanceAndDuration(self):
        '''Returns the amount of time needed to print the ring, and the distance travelled.'''
        duration = 0.0
        distance = 0.0
        
        (perimeterDistance, perimeterDuration) = self.perimeter.getDistanceAndDuration()
        duration += perimeterDuration
        distance += perimeterDistance
            
        for loop in self.loops:
            (loopDistance, loopDuration) = loop.getDistanceAndDuration()
            duration += loopDuration
            distance += loopDistance
            
        for infillPath in self.infillPaths:
            (infillPathDistance, infillPathDuration) = infillPath.getDistanceAndDuration()
            duration += infillPathDuration
            distance += infillPathDistance
        
        for nestedRing in self.innerNestedRings:
            (nestedRingPathDistance, nestedRingPathDuration) = nestedRing.getDistanceAndDuration()
            duration += nestedRingPathDuration
            distance += nestedRingPathDistance
            
        return (distance, duration)
    
    
    def getPerimeterPaths(self, pathList):        
        pathList.append(self.perimeter)
        
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.getPerimeterPaths(pathList)
            
    def getLoopPaths(self, pathList):        
        for loop in self.loops:
            pathList.append(loop)
        
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.getLoopPaths(pathList)
            
        
    def getInfillPaths(self, pathList):        
        for infillPath in self.infillPaths:
            pathList.append(infillPath)
        
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.getInfillPaths(pathList)
            
            
    def getStartPoint(self):
        if self.perimeter != None:
            return self.perimeter.getStartPoint()
        

    def offset(self, offset):
        'Moves the nested ring by the offset amount'
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.offset(offset)
            
        self.perimeter.offset(offset)
                        
        for loop in self.loops:
            loop.offset(offset)
            
        for infillPath in self.infillPaths:
            infillPath.offset(offset)
            
                        
    def setBoundaryPerimeter(self, boundaryPointsLoop, perimeterLoop=None):        
        self.perimeter = BoundaryPerimeter(self.z, self.runtimeParameters)
        
        for point in boundaryPointsLoop:
            self.perimeter.boundaryPoints.append(Vector3(point.real, point.imag, self.z))
            
        if len(boundaryPointsLoop) < 2:
            return
        
        if perimeterLoop == None:
            perimeterLoop = boundaryPointsLoop
            
        if euclidean.isWiddershins(perimeterLoop):
            self.perimeter.type = 'outer'
        else:
            self.perimeter.type = 'inner'
        path = perimeterLoop + [perimeterLoop[0]]
        self.perimeter.addPath(path)
        
    
    def addInfillGcodeFromThread(self, thread):
        'Add a thread to the output.'
        
        infillPath = InfillPath(self.z, self.runtimeParameters)
        decimalPlaces = self.decimalPlaces
        if len(thread) > 0:
            infillPath.startPoint = thread[0]
            infillPath.points = thread[1 :]
        else:
            logger.warning('Zero length vertex positions array which was skipped over, this should never happen.')
        if len(thread) < 2:
            logger.warning('Thread of only one point: %s, this should never happen.', thread)
            return
        
        self.infillPaths.append(infillPath)    


    def getLoopsToBeFilled(self):
        'Get last fill loops from the outside loop and the loops inside the inside loops.'
        if self.lastFillLoops == None:
            return self.getSurroundingBoundaries()
        return self.lastFillLoops


    def getXYBoundaries(self):
        '''Converts XYZ boundary points to XY'''
        xyBoundaries = []
        for boundaryPoint in self.perimeter.boundaryPoints:
            xyBoundaries.append(boundaryPoint.dropAxis())
        return xyBoundaries
    
            
    def getSurroundingBoundaries(self):
        'Get the boundary of the surronding loop plus any boundaries of the innerNestedRings.'
        surroundingBoundaries = [self.getXYBoundaries()]
        
        for nestedRing in self.innerNestedRings:
            surroundingBoundaries.append(nestedRing.getXYBoundaries())
        
        return surroundingBoundaries
    
    
    def getFillLoops(self, penultimateFillLoops):
        'Get last fill loops from the outside loop and the loops inside the inside loops.'
        fillLoops = self.getLoopsToBeFilled()[:]
        surroundingBoundaries = self.getSurroundingBoundaries()
        withinLoops = []
        if penultimateFillLoops == None:
            penultimateFillLoops = self.penultimateFillLoops
        
        if penultimateFillLoops != None:
            for penultimateFillLoop in penultimateFillLoops:
                if len(penultimateFillLoop) > 2:
                    if euclidean.getIsInFilledRegion(surroundingBoundaries, penultimateFillLoop[0]):
                        withinLoops.append(penultimateFillLoop)
                        
        if not euclidean.getIsInFilledRegionByPaths(self.penultimateFillLoops, fillLoops):
            fillLoops += self.penultimateFillLoops
            
        for nestedRing in self.innerNestedRings:
            fillLoops += euclidean.getFillOfSurroundings(nestedRing.innerNestedRings, penultimateFillLoops)
        return fillLoops
    
    def transferPaths(self, paths):
        'Transfer paths.'
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.transferPaths(paths)
        loop = self.getXYBoundaries()
        for insideIndex in xrange(len(paths) - 1, -1, -1):
            inside = paths[ insideIndex ]
            if euclidean.isPathInsideLoop(loop, inside):
                self.infillPathsHolder.append(inside)
                del paths[ insideIndex ]

    def addToThreads(self, extrusionHalfWidth, oldOrderedLocation, threadSequence):
        'Add to paths from the last location. perimeter>inner >fill>paths or fill> perimeter>inner >paths'
        self.addPerimeterInner(extrusionHalfWidth, oldOrderedLocation, threadSequence)
        self.transferInfillPaths(extrusionHalfWidth, oldOrderedLocation, threadSequence)
        
    def transferInfillPaths(self, extrusionHalfWidth, oldOrderedLocation, threadSequence):
        'Transfer the infill paths.'
        euclidean.transferClosestPaths(oldOrderedLocation, self.infillPathsHolder[:], self)
    
    def addPerimeterInner(self, extrusionHalfWidth, oldOrderedLocation, threadSequence):
        'Add to the perimeter and the inner island.'
        for loop in self.extraLoops:
            innerPerimeterLoop = Loop(self.z, self.runtimeParameters)
            if euclidean.isWiddershins(loop + [loop[0]]):
                innerPerimeterLoop.type = 'outer'
            else:
                innerPerimeterLoop.type = 'inner'
            innerPerimeterLoop.addPath(loop + [loop[0]])
            self.loops.append(innerPerimeterLoop)
        
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.addToThreads(extrusionHalfWidth, oldOrderedLocation, threadSequence)
