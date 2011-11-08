from collections import OrderedDict
from config import config
from fabmetheus_utilities import archive, svg_writer, euclidean
from fabmetheus_utilities.vector3 import Vector3
from math import log10, floor, pi
from utilities import memory_tracker
import StringIO
import gcodes
import math
import sys
import time
from plugins.comb import CombSkein

# globals used as an easy way to maintain state between layer changes
_totalExtrusionDistance = 0.0
_previousPoint = None

class Gcode:
    '''Runtime data for conversion of 3D model to gcode.'''
    
    def __init__(self):
        self.svgText = None
        self.runtimeParameters = RuntimeParameters()
        
        # Can we remove this after reading the carving once the layers have been generated??
        self.rotatedLoopLayers = []
        
        self.carvingCornerMaximum = None
        self.carvingCornerMinimum = None
        
        self.layers = OrderedDict()
        
        self.startGcodeCommands = []
        self.endGcodeCommands = []
        self.elementOffsets = None
        self.verbose = self.runtimeParameters.verboseGcode
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        
        output.write("\nRuntimeParameters:\n%s\n" % vars(self.runtimeParameters))
        
        output.write("\nelementOffsets: %s\n" % self.elementOffsets)
        
        output.write("\nrotatedLoopLayers:\n")
        for x in self.rotatedLoopLayers:
            output.write('%s\n' % vars(x))
            
        output.write("\nstartGcodeCommands:\n")
        for x in self.startGcodeCommands:
            output.write(printCommand(x, self.verbose))
        
        output.write("\nlayers:\n")
        for key in sorted(self.layers.iterkeys()):
            output.write('%s\n' % self.layers[key])
       
        output.write("\nendGcodeCommands:\n")
        for x in self.endGcodeCommands:
            output.write(printCommand(x, self.verbose))
             
        return output.getvalue()
    
    def getSVGText(self):
        svgWriter = svg_writer.SVGWriter(
                                True,
                                self.carvingCornerMaximum,
                                self.carvingCornerMinimum,
                                self.runtimeParameters.decimalPlaces,
                                self.runtimeParameters.layerHeight,
                                self.runtimeParameters.layerThickness)
        return svgWriter.getReplacedSVGTemplate(self.runtimeParameters.inputFilename, '', self.rotatedLoopLayers)
        
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
                    
        for startCommand in self.startGcodeCommands:
            output.write(printCommand(startCommand, self.verbose))
            
        lookaheadStartVector = None
        lookaheadKeyIndex = 0
        layerCount = len(self.layers)
        for key in sorted(self.layers.iterkeys()):
            lookaheadStartPoint = None
            lookaheadKeyIndex = lookaheadKeyIndex + 1
            if lookaheadKeyIndex < layerCount:
                lookaheadKey = self.layers.keys()[lookaheadKeyIndex]
                lookaheadLayer = self.layers[lookaheadKey]
                lookaheadStartPoint = lookaheadLayer.getStartPoint()
                lookaheadStartVector = Vector3(lookaheadStartPoint.real, lookaheadStartPoint.imag, lookaheadLayer.z)

            output.write(self.layers[key].getGcodeText(output, lookaheadStartVector))
            
        for endCommand in self.endGcodeCommands:
            output.write(printCommand(endCommand, self.verbose))
                        
        return output.getvalue()
    
class Layer:
    def __init__(self, z, index, runtimeParameters):
        self.z = z
        self.index = index
        self.runtimeParameters = runtimeParameters
        self.bridgeRotation = None
        self.nestedRings = []
        self.preLayerGcodeCommands = []
        self.postLayerGcodeCommands = []
        self.feedAndFlowRateMultiplier = 1.0  
        
        if runtimeParameters.profileMemory:
            memory_tracker.track_object(self)
        self.verbose = self.runtimeParameters.verboseGcode
        
        if self.runtimeParameters.dimensionActive:
            if self.runtimeParameters.extrusionUnitsRelative:
                self.preLayerGcodeCommands.append(GcodeCommand(gcodes.RELATIVE_EXTRUSION_DISTANCE))
            else:
                self.preLayerGcodeCommands.append(GcodeCommand(gcodes.ABSOLUTE_EXTRUSION_DISTANCE))
        
        self.combSkein = None
            
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        
        output.write('%2slayer (%s) z:%s\n' % ('', self.index, self.z))
        
        output.write('%2slayer feedAndFlowRateMultiplier:%s\n' % ('', self.feedAndFlowRateMultiplier))
        
        if self.bridgeRotation != None:
            output.write('bridgeRotation %s, ' % self.bridgeRotation)
            
        output.write('%4spreLayerGcodeCommand:' % (''))
        for preLayerGcodeCommand in self.preLayerGcodeCommands:
            output.write(printCommand(preLayerGcodeCommand, self.verbose))
            
        output.write('%4snestedRings:' % (''))
        for nestedRing in self.nestedRings:
            output.write(nestedRing)
            
        output.write('%4spostLayerGcodeCommand:' % (''))
        for postLayerGcodeCommand in self.postLayerGcodeCommands:
            output.write(printCommand(postLayerGcodeCommand, self.verbose))
           
        return output.getvalue()
    
    def getDistanceAndDuration(self):
        '''Returns the amount of time needed to print the layer, and the distance to travel. Note, this currently ignores commands in the pre and post layer list.'''
        duration = 0.0
        distance = 0.0
        for nestedRing in self.nestedRings:
            (nestedRingDistance, nestedRingDuration) = nestedRing.getDistanceAndDuration()
            distance += nestedRingDistance
            duration += nestedRingDuration
        return (distance, duration)
    

    def getOrderedPathList(self):
        pathList = []
        threadFunctionDictionary = {
            'infill':self.getInfillPaths, 'loops':self.getLoopPaths, 'perimeter':self.getPerimeterPaths}
        for threadType in self.runtimeParameters.extrusionPrintOrder:
            threadFunctionDictionary[threadType](pathList)
        
        return pathList

    def getGcodeText(self, output, parentLookaheadStartVector=None):
        '''Final Gcode representation.'''
        
        for preLayerGcodeCommand in self.preLayerGcodeCommands:
            output.write(printCommand(preLayerGcodeCommand, self.verbose))
        
        
        if self.runtimeParameters.combActive: 
            self.combSkein = CombSkein(self)
        
        pathList = self.getOrderedPathList()        
        
        pathListCount = len(pathList)
        for (index, path) in enumerate(pathList):
            if index + 1 < pathListCount:
                lookaheadStartPoint = pathList[index + 1].getStartPoint()
                lookaheadVector = Vector3(lookaheadStartPoint.real, lookaheadStartPoint.imag, self.z)
            else:
                lookaheadVector = parentLookaheadStartVector
                
            previousVector = None
            if index > 0:
                previousPoint = pathList[index - 1].getEndPoint()
                previousVector = Vector3(previousPoint.real, previousPoint.imag, self.z)
                
            nextPoint = path.getStartPoint()
            nextVector = Vector3(nextPoint.real, nextPoint.imag, self.z)
            
            travelPath = TravelPath(self.z, self.runtimeParameters, previousVector, nextVector, self.combSkein)
            travelPath.getGcodeText(output, lookaheadVector, self.feedAndFlowRateMultiplier)
            
            path.getGcodeText(output, lookaheadVector, self.feedAndFlowRateMultiplier)
        
        for postLayerGcodeCommand in self.postLayerGcodeCommands:
            output.write(printCommand(postLayerGcodeCommand, self.verbose))
    
    def getPerimeterPaths(self, pathList):

        for nestedRing in self.nestedRings:
            nestedRing.getPerimeterPaths(pathList)
    
    def getLoopPaths(self, pathList):

        for nestedRing in self.nestedRings:
            nestedRing.getLoopPaths(pathList)
    
    def getInfillPaths(self, pathList):

        for nestedRing in self.nestedRings:
            nestedRing.getInfillPaths(pathList)
    
    def getStartPoint(self):
        if len(self.nestedRings) > 0:
            return self.nestedRings[0].getStartPoint()
        
    def addNestedRing(self, nestedRing):
        self.nestedRings.append(nestedRing)
        
    def isBridgeLayer(self):
        return self.bridgeRotation != None
   

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
        self.flowScaleSixty = 60.0 * ((((self.layerThickness + self.perimeterWidth) / 4) ** 2 * pi) / filamentPackingArea)
        
    def __str__(self):
        output = StringIO.StringIO()
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
            (nestedRingPathDistance, nestedRingDuration) = nestedRing.getDistanceAndDuration()
            duration += nestedRingDuration
            distance += nestedRingDistance
            
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
        thread = perimeterLoop + [perimeterLoop[0]]
        self.perimeter.addPathFromThread(thread)
    
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
        for nestedRing in self.innerNestedRings:
            euclidean.transferPathsToSurroundingLoops(nestedRing.innerNestedRings, paths)
        self.infillPathsHolder = euclidean.getTransferredPaths(paths, self.getXYBoundaries())
        
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
            innerPerimeterLoop.addPathFromThread(loop + [loop[0]])
            self.loops.append(innerPerimeterLoop)
        
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.addToThreads(extrusionHalfWidth, oldOrderedLocation, threadSequence)

class Path:
    ''' A Path the tool will follow within a nested ring.'''
    def __init__(self, z, runtimeParameters):
        
        self.z = z
        self.runtimeParameters = runtimeParameters
        self.verbose = self.runtimeParameters.verboseGcode
        
        self.type = None
        self.startPoint = None
        self.points = []
        self.gcodeCommands = []
        
        self.decimalPlaces = self.runtimeParameters.decimalPlaces
        self.dimensionDecimalPlaces = self.runtimeParameters.dimensionDecimalPlaces
        self.speedActive = self.runtimeParameters.speedActive
        self.bridgeFeedRateMinute = self.runtimeParameters.bridgeFeedRateMinute
        self.perimeterFeedRateMinute = self.runtimeParameters.perimeterFeedRateMinute
        self.extrusionFeedRateMinute = self.runtimeParameters.extrusionFeedRateMinute
        self.travelFeedRateMinute = self.runtimeParameters.travelFeedRateMinute
        self.extrusionUnitsRelative = self.runtimeParameters.extrusionUnitsRelative
        
        self.dimensionActive = self.runtimeParameters.dimensionActive
        
        self.oozeRate = self.runtimeParameters.oozeRate
        self.zDistanceRatio = 5.0
        self.extruderRetractionSpeedMinute = round(60.0 * self.runtimeParameters.extruderRetractionSpeed, self.dimensionDecimalPlaces)

        self.layerThickness = self.runtimeParameters.layerThickness
        self.perimeterWidth = self.runtimeParameters.perimeterWidth
        self.filamentDiameter = self.runtimeParameters.filamentDiameter
        self.filamentPackingDensity = self.runtimeParameters.filamentPackingDensity
        self.absolutePositioning = config.getboolean('preface', 'positioning.absolute')
        self.flowRate = self.runtimeParameters.flowRate
        self.perimeterFlowRate = self.runtimeParameters.perimeterFlowRate
        self.bridgeFlowRate = self.runtimeParameters.bridgeFlowRate
        
        filamentRadius = 0.5 * self.filamentDiameter
        filamentPackingArea = pi * filamentRadius * filamentRadius * self.filamentPackingDensity
        self.flowScaleSixty = 60.0 * ((((self.layerThickness + self.perimeterWidth) / 4) ** 2 * pi) / filamentPackingArea)
        
        self.minimumBridgeFeedRateMultiplier = self.runtimeParameters.minimumBridgeFeedRateMultiplier
        self.minimumPerimeterFeedRateMultiplier = self.runtimeParameters.minimumPerimeterFeedRateMultiplier
        self.minimumExtrusionFeedRateMultiplier = self.runtimeParameters.minimumExtrusionFeedRateMultiplier
        self.minimumTravelFeedRateMultiplier = self.runtimeParameters.minimumTravelFeedRateMultiplier
        self.minimumLayerFeedRateMinute = self.runtimeParameters.minimumLayerFeedRateMinute
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        output.write('%14stype: %s\n' % ('', self.type))
        output.write('%14sstartPoint: %s\n' % ('', self.startPoint))
        output.write('%14spoints: %s\n' % ('', self.points))
        output.write('%14sgcodeCommands:\n' % '')
        for command in self.gcodeCommands:
            output.write('%16s%s' % ('', printCommand(command)))
        return output.getvalue()    
    
    def getDistanceAndDuration(self):
        '''Returns the time taken to follow the path and the distance'''
        oldLocation = self.startPoint
        feedRate = self.travelFeedRateMinute
        duration = 0.0
        distance = 0.0
        for point in self.points:
            feedRateSecond = feedRate / 60.0
            
            separationX = point.real - oldLocation.real
            separationY = point.imag - oldLocation.imag
            segmentDistance = math.sqrt(separationX ** 2 + separationY ** 2)
            
            duration += segmentDistance / feedRateSecond
            distance += segmentDistance
            oldLocation = point
            if isinstance(self, BoundaryPerimeter):
                feedRate = self.perimeterFeedRateMinute
            else:
                feedRate = self.extrusionFeedRateMinute
                
        return (distance, duration)
        
    def getStartPoint(self):
        return self.startPoint
    
    def getEndPoint(self):
        if len(self.points) > 0:
            return self.points[len(self.points) - 1]
        else:
            return None
        
    def getGcodeText(self, output, lookaheadStartVector=None, feedAndFlowRateMultiplier=1.0):
        '''Final Gcode representation.'''
        self.generateGcode(lookaheadStartVector, feedAndFlowRateMultiplier)
            
        for command in self.gcodeCommands:
            output.write('%s' % printCommand(command, self.verbose))

    def generateGcode(self, lookaheadStartVector=None, feedAndFlowRateMultiplier=1.0):
        'Transforms paths and points to gcode'
        global _previousPoint
        
        if _previousPoint == None:
            _previousPoint = self.startPoint
            
        for point in self.points:
            
            gcodeArgs = [('X', round(point.real, self.decimalPlaces)),
                         ('Y', round(point.imag, self.decimalPlaces)),
                         ('Z', round(self.z, self.decimalPlaces))]
            
            if isinstance(self, BoundaryPerimeter):
                pathFeedRateMinute = self.perimeterFeedRateMinute
            else:
                pathFeedRateMinute = self.extrusionFeedRateMinute

            (pathFeedRateMinute, pathFeedRateMultiplier) = self.getFeedRateAndMultiplier(pathFeedRateMinute, feedAndFlowRateMultiplier)
            
            if self.speedActive:
                gcodeArgs.append(('F', pathFeedRateMinute))
                
            if self.dimensionActive:
                extrusionDistance = self.getExtrusionDistance(point, self.flowRate * pathFeedRateMultiplier, pathFeedRateMinute)
                gcodeArgs.append(('E', '%s' % extrusionDistance))
                
            self.gcodeCommands.append(
                GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
        
    def getFeedRateAndMultiplier(self, feedRateMinute, feedRateMultiplier):
        'Returns the multiplier that results in either the minimum feed rate or the slowed down feed rate'
        if (feedRateMultiplier * feedRateMinute) < self.minimumLayerFeedRateMinute:
            return (self.minimumLayerFeedRateMinute, self.minimumLayerFeedRateMinute / feedRateMinute)
        else:
            return (feedRateMinute, feedRateMultiplier)
    
    def getResetExtruderDistanceCommand(self):
        global _totalExtrusionDistance
        _totalExtrusionDistance = 0.0
        return GcodeCommand(gcodes.RESET_EXTRUDER_DISTANCE, [('E', '0')])
        

    def getExtrusionDistance(self, point, flowRate, feedRateMinute):
        global _totalExtrusionDistance
        global _previousPoint
        distance = 0.0
        
        if self.absolutePositioning:
            if _previousPoint != None:
                distance = abs(point - _previousPoint)
            _previousPoint = point
        else:
            if _previousPoint == None:
                logger.warning('There was no absolute location when the G91 command was parsed, so the absolute location will be set to the origin.')
                _previousPoint = Vector3()
            distance = abs(point)
            _previousPoint += point
            
        
        scaledFlowRate = flowRate * self.flowScaleSixty
        extrusionDistance = scaledFlowRate / feedRateMinute * distance
        
        if self.extrusionUnitsRelative:
            extrusionDistance = round(extrusionDistance, self.dimensionDecimalPlaces)
        else:
            _totalExtrusionDistance += extrusionDistance
            extrusionDistance = round(_totalExtrusionDistance, self.dimensionDecimalPlaces)
            
        return extrusionDistance

    def offset(self, offset):
        if self.startPoint != None:
            self.startPoint = complex(self.startPoint.real + offset.real, self.startPoint.imag + offset.imag)
        for (index, point) in enumerate(self.points):
            self.points[index] = complex(point.real + offset.real, point.imag + offset.imag)
            
class InfillPath(Path):
    
    def __init__(self, z, runtimeParameters):        
        Path.__init__(self, z, runtimeParameters)
            
class Loop(Path):
    
    def __init__(self, z, runtimeParameters):
        Path.__init__(self, z, runtimeParameters)
        
    def addPathFromThread(self, thread):
        'Add a thread to the output.'
        if len(thread) > 0:        
            self.startPoint = thread[0]
            self.points = thread[1 :]
        else:
            logger.warning('Zero length vertex positions array which was skipped over, this should never happen.')
        if len(thread) < 2:
            logger.warning('Thread of only one point: %s, this should never happen.', thread)
            
class TravelPath(Path):
    '''Moves from one path to another withou extruding. Optionally dodges gaps (comb) and retracts (dimension)'''
    
    def __init__(self, z, runtimeParameters, fromLocation, toLocation, combSkein):
        Path.__init__(self, z, runtimeParameters)
        self.fromLocation = fromLocation
        self.toLocation = toLocation
        self.combSkein = combSkein
        
        if fromLocation != None:
            self.startPoint = fromLocation.dropAxis()
        else:  
            self.startPoint = toLocation.dropAxis()
            
        self.points.append(toLocation.dropAxis())
        
    def offset(self, offset):
        self.fromLocation.x += offset.real
        self.fromLocation.y += offset.imag            
        self.toLocation.x += offset.real
        self.toLocation.y += offset.imag            
        Path.offset(self, offset)
        
    def __str__(self):
        output = StringIO.StringIO()
        output.write('\n%12sfromLocation: %s\n' % ('', self.fromLocation))
        output.write('%12stoLocation: %s\n' % ('', self.toLocation))
        output.write(Path.__str__(self))
        return output.getvalue()

    def moveToStartPoint(self, feedAndFlowRateMultiplier):
        '''Adds gcode to move the nozzle to the startpoint of the path. 
            If comb is active the path will dodge all open spaces.
        '''
        startPointPath = []
        
        if self.runtimeParameters.combActive and self.fromLocation != None and self.combSkein != None: 
            
            additionalCommands = self.combSkein.getPathsBetween(self.z, self.fromLocation.dropAxis(), self.toLocation.dropAxis())
            startPointPath.extend(additionalCommands)
        
        startPointPath.append(self.toLocation.dropAxis())
        
        for point in startPointPath:
            gcodeArgs = [('X', round(point.real, self.decimalPlaces)),
                ('Y', round(point.imag, self.decimalPlaces)),
                ('Z', round(self.z, self.decimalPlaces))]
            
            if self.speedActive:
                travelFeedRateMinute, travelFeedRateMultiplier = self.getFeedRateAndMultiplier(self.travelFeedRateMinute, feedAndFlowRateMultiplier)
                gcodeArgs.append(('F', self.travelFeedRateMinute * travelFeedRateMultiplier))
                
            self.gcodeCommands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
                        
    def generateGcode(self, lookaheadStartVector=None, feedAndFlowRateMultiplier=1.0):
        'Transforms paths and points to gcode'
        lastRetractionExtrusionDistance = 0.0
        
        if self.dimensionActive:
            
            if lookaheadStartVector != None and self.fromLocation != None:
                
                toLocation = lookaheadStartVector
                locationMinusOld = toLocation - self.fromLocation
                xyTravel = abs(locationMinusOld.dropAxis())
                zTravelMultiplied = locationMinusOld.z * self.zDistanceRatio
                timeToNextThread = math.sqrt(xyTravel * xyTravel + zTravelMultiplied * zTravelMultiplied) / self.extrusionFeedRateMinute * 60
                retractionExtrusionDistance = timeToNextThread * abs(self.oozeRate) / 60
            else:
                retractionExtrusionDistance = 0.0
            
            if isinstance(self, BoundaryPerimeter):
                postRetractFeedRateMinute = self.perimeterFeedRateMinute
            else:
                postRetractFeedRateMinute = self.extrusionFeedRateMinute
            self.gcodeCommands.extend(self.getRetractCommands(retractionExtrusionDistance, postRetractFeedRateMinute))
            
            #Store for reverse retraction
            lastRetractionExtrusionDistance = retractionExtrusionDistance
            
        self.gcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_OFF))
        
        self.moveToStartPoint(feedAndFlowRateMultiplier)
    
        if self.dimensionActive:
            self.previousPoint = self.startPoint
            self.gcodeCommands.extend(self.getRetractReverseCommands(lastRetractionExtrusionDistance))
            
        self.gcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_ON))        
        
    def getRetractCommands(self, extrusionDistance, resumingSpeed):
        global _totalExtrusionDistance
        commands = []
        if self.extrusionUnitsRelative:
            retractDistance = round(extrusionDistance, self.dimensionDecimalPlaces)
        else:
            _totalExtrusionDistance -= extrusionDistance
            retractDistance = round(_totalExtrusionDistance, self.dimensionDecimalPlaces)
    
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.extruderRetractionSpeedMinute)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('E', '%s' % retractDistance)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % resumingSpeed)]))
        return commands
    
    def getRetractReverseCommands(self, extrusionDistance):
        global _totalExtrusionDistance
        commands = []
        if self.extrusionUnitsRelative:
            retractDistance = round(extrusionDistance, self.dimensionDecimalPlaces)
        else:
            _totalExtrusionDistance += extrusionDistance
            retractDistance = round(_totalExtrusionDistance, self.dimensionDecimalPlaces)
    
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.extruderRetractionSpeedMinute)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('E', '%s' % retractDistance)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.travelFeedRateMinute)]))
                        
        if not self.extrusionUnitsRelative:
            commands.append(self.getResetExtruderDistanceCommand())
        return commands        
    
class BoundaryPerimeter(Loop):
    
    def __init__(self, z, runtimeParameters):
        Loop.__init__(self, z, runtimeParameters)
        self.boundaryPoints = []

    def __str__(self):
        output = StringIO.StringIO()
        output.write('%12sboundaryPerimeter:\n' % '')
        output.write('%14sboundaryPoints: %s\n' % ('', self.boundaryPoints))
        output.write(Loop.__str__(self))
        return output.getvalue()
    
    def offset(self, offset):
        for boundaryPoint in self.boundaryPoints:
            boundaryPoint.x += offset.real
            boundaryPoint.y += offset.imag            
        Loop.offset(self, offset)    
        
class RuntimeParameters:
    def __init__(self):
        self.startTime = time.time()
        self.endTime = None
        self.inputFilename = None
        self.outputFilename = None
        
        self.profileMemory = config.getboolean('general', 'profile.memory')
        
        self.decimalPlaces = config.getint('general', 'decimal.places')
        self.layerThickness = config.getfloat('carve', 'layer.height')
        self.perimeterWidth = config.getfloat('carve', 'extrusion.width')
        self.profileName = None
        self.bridgeWidthMultiplier = None
        self.nozzleDiameter = None
        self.threadSequence = None
        self.infillWidth = None
        self.operatingFeedRatePerSecond = None
        self.perimeterFeedRatePerSecond = None
        self.operatingFlowRate = None
        self.verboseGcode = config.getboolean('general', 'verbose.gcode')
        
        self.overlapRemovalWidthOverPerimeterWidth = config.getfloat('inset', 'overlap.removal.scaler')
        self.nozzleDiameter = config.getfloat('inset', 'nozzle.diameter')
        self.bridgeWidthMultiplier = config.getfloat('inset', 'bridge.width.multiplier.ratio')
        self.loopOrderAscendingArea = config.getboolean('inset', 'loop.order.preferloops')
        
        self.layerHeight = config.getfloat('carve', 'layer.height')
        self.extrusionWidth = config.getfloat('carve', 'extrusion.width')
        self.infillBridgeDirection = config.getboolean('carve', 'infill.bridge.direction')
        self.importCoarsenessRatio = config.getfloat('carve', 'import.coarseness.ratio')
        self.correctMesh = config.getboolean('carve', 'mesh.correct')
        self.decimalPlaces = config.getint('general', 'decimal.places')
        self.layerPrintFrom = config.getint('carve', 'layer.print.from')
        self.layerPrintTo = config.getint('carve', 'layer.print.to')
        
        self.speedActive = config.getboolean('speed', 'active')
        self.addFlowRate = config.getboolean('speed', 'add.flow.rate')
        self.addAccelerationRate = config.getboolean('speed', 'add.acceleration.rate')
        self.feedRate = config.getfloat('speed', 'feed.rate')
        self.flowRateRatio = config.getfloat('speed', 'flow.rate.ratio')
        self.accelerationRate = config.getfloat('speed', 'acceleration.rate')
        self.orbitalFeedRateRatio = config.getfloat('speed', 'feed.rate.orbiting.ratio')
        self.perimeterFeedRate = config.getfloat('speed', 'feed.rate.perimeter')
        self.perimeterFlowRateRatio = config.getfloat('speed', 'flow.rate.perimeter.ratio')
        self.bridgeFeedRateRatio = config.getfloat('speed', 'feed.rate.bridge.ratio')
        self.bridgeFlowRateRatio = config.getfloat('speed', 'flow.rate.bridge.ratio')
        self.travelFeedRate = config.getfloat('speed', 'feed.rate.travel')
        
        self.dimensionActive = config.getboolean('dimension', 'active')
        self.filamentDiameter = config.getfloat('dimension', 'filament.diameter')
        self.filamentPackingDensity = config.getfloat('dimension', 'filament.packing.density')
        self.oozeRate = config.getfloat('dimension', 'oozerate')
        self.extruderRetractionSpeed = config.getfloat('dimension', 'extruder.retraction.speed')
        self.extrusionUnitsRelative = config.getboolean('dimension', 'extrusion.units.relative')
        self.dimensionDecimalPlaces = config.getint('dimension', 'decimal.places')
        
        self.extrusionPrintOrder = config.get('fill', 'extrusion.sequence.print.order').split(',')
        
        self.bridgeFeedRateMinute = self.bridgeFeedRateRatio * self.perimeterFeedRate * 60 # todo former reference to main feed now perimeter feed
        self.perimeterFeedRateMinute = self.perimeterFeedRate * 60
        self.extrusionFeedRateMinute = self.feedRate * 60.0
        self.travelFeedRateMinute = self.travelFeedRate * 60
        
        self.minimumLayerFeedRate = config.getfloat('cool', 'minimum.layer.feed.rate')
        self.minimumLayerFeedRateMinute = self.minimumLayerFeedRate * 60
        
        self.minimumBridgeFeedRateMultiplier = self.minimumLayerFeedRateMinute / self.bridgeFeedRateMinute
        self.minimumPerimeterFeedRateMultiplier = self.minimumLayerFeedRateMinute / self.perimeterFeedRateMinute        
        self.minimumExtrusionFeedRateMultiplier = self.minimumLayerFeedRateMinute / self.extrusionFeedRateMinute
        self.minimumTravelFeedRateMultiplier = self.minimumLayerFeedRateMinute / self.travelFeedRateMinute
        
        nozzleXsection = (self.nozzleDiameter / 2) ** 2 * pi
        extrusionXsection = ((abs(self.perimeterWidth) + self.layerThickness) / 4) ** 2 * pi
        
        self.flowRate = self.flowRateRatio * self.feedRate
        self.bridgeFlowRate = (self.bridgeFlowRateRatio * self.bridgeFeedRateRatio) * (self.perimeterFlowRateRatio * self.perimeterFeedRate) * (nozzleXsection / extrusionXsection)
        self.perimeterFlowRate = self.perimeterFlowRateRatio * self.perimeterFeedRate
        
        self.orbitalFeedRatePerSecond = (self.feedRate * self.orbitalFeedRateRatio)
        self.orbitalFeedRateMinute = self.orbitalFeedRatePerSecond * 60
        
        self.combActive = config.getboolean('comb', 'active')

class GcodeCommand:
    def __init__(self, commandLetter, parameters=None):
        self.commandLetter = commandLetter
        if parameters == None:
            parameters = {}
        self.parameters = OrderedDict(parameters)
    
    def __str__(self):
        return self.str(False) 
    
    def str(self, verbose=False):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        output.write('%s ' % (self.commandLetter[0]))
        for name, value in self.parameters.items():
            output.write('%s%s ' % (name, value))
        if (verbose):
            output.write(';%20s ' % (self.commandLetter[1]))
        return output.getvalue().strip()


def printCommand(command, verbose=False):
    if command == None:
        return 
    if isinstance(command, GcodeCommand):
        return'%s\n' % command.str(verbose)
    else:
        return '%s\n' % command
