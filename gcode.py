from collections import OrderedDict
from config import config
from decimal import Decimal, ROUND_HALF_UP
from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities import archive, svg_writer, euclidean
from math import log10, floor, pi
from plugins.speed import SpeedSkein
import StringIO
import decimal
import gcodes
import time
import weakref
import sys
from utilities import memory_tracker

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

        for key in sorted(self.layers.iterkeys()):
            output.write(self.layers[key].getGcodeText(output))

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
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        
        output.write('%2slayer (%s) z:%s\n' % ('', self.index,self.z))
        if self.bridgeRotation != None:
            output.write('bridgeRotation %s, ' % self.bridgeRotation)
            
        output.write('%4snestedRings:' % (''))
        for nestedRing in self.nestedRings:
            output.write(nestedRing)
           
        return output.getvalue()
    
    def getGcodeText(self, output):
        '''Final Gcode representation.'''
        for nestedRing in self.nestedRings:
            output.write(nestedRing.getGcodeText(output))
    
    def addNestedRing(self, nestedRing):
        self.nestedRings.append(nestedRing)
   

class NestedRing:
    def __init__(self, z, runtimeParameters):
        self.runtimeParameters = runtimeParameters
        self.decimalPlaces = self.runtimeParameters.decimalPlaces
        self.z = z
        
        self.boundaryPerimeters = None
        
        self.loops = []
        
        self.infillPaths = []
        self.infillPathsHolder = []
        
        self.innerNestedRings = []
        
        # can the following be removed? only used whilst generating the infill?
        self.extraLoops = []
        self.penultimateFillLoops = []
        self.lastFillLoops = None        
                
        self.activateSpeed = self.runtimeParameters.activateSpeed
        self.bridgeFeedRateMinute = self.runtimeParameters.bridgeFeedRateRatio * self.runtimeParameters.perimeterFeedRate * 60 # todo former reference to main feed now perimeter feed
        self.perimeterFeedRateMinute = self.runtimeParameters.perimeterFeedRate * 60
        self.extrusionFeedRateMinute = 60.0 * self.runtimeParameters.feedRate
        self.travelFeedRateMinute = self.runtimeParameters.travelFeedRate * 60
        self.extrusionUnitsRelative = self.runtimeParameters.extrusionUnitsRelative
        self.totalExtrusionDistance = 0.0
        
        self.activateDimension = self.runtimeParameters.activateDimension
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
        output.write('\n%4s#########################################'%'')
        output.write('\n%8snestedRing:' % '')
        
        output.write('\n%10sboundaryPerimeter:\n' % '')
        output.write(self.boundaryPerimeter)

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
            
        output.write('\n%4s###### end nestedRing ########################'%'')
                    
        return output.getvalue()
    
    def getGcodeText(self, output):
        '''Final Gcode representation.'''        
        
        output.write(self.boundaryPerimeter.getGcodeText(output))
        
        for loop in self.loops:
            output.write(loop.getGcodeText(output))
            
        for infillPath in self.infillPaths:
            output.write(infillPath.getGcodeText(output))
            
        for innerNestedRing in self.innerNestedRings:
            output.write(innerNestedRing.getGcodeText(output))
    
    def offset(self, offset):
        'Moves the nested ring by the offset amount'
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.offset(offset)
            
        self.boundaryPerimeter.offset(offset)
                        
        for loop in self.loops:
            loop.offset(offset)
            
        for infillPath in self.infillPaths:
            infillPath.offset(offset)
                        
    def setBoundaryPerimeter(self, boundaryPointsLoop, perimeterLoop=None):
        
        self.boundaryPerimeter = BoundaryPerimeter(self.z, self.runtimeParameters)
        
        for point in boundaryPointsLoop:
            self.boundaryPerimeter.boundaryPoints.append(Vector3(point.real, point.imag, self.z))
            
        if len(boundaryPointsLoop) < 2:
            return
        
        if perimeterLoop == None:
            perimeterLoop = boundaryPointsLoop
            
        if euclidean.isWiddershins(perimeterLoop):
            self.boundaryPerimeter.type  = 'outer'
        else:
            self.boundaryPerimeter.type = 'inner'
        thread = perimeterLoop + [perimeterLoop[0]]
        self.boundaryPerimeter.addPathFromThread(thread)
    
    def addInfillGcodeFromThread(self, thread):
        'Add a thread to the output.'
        
        infillPath = InfillPath(self.z, self.runtimeParameters)
        decimalPlaces = self.decimalPlaces
        if len(thread) > 0:
            infillPath.startPoint = thread[0]
            infillPath.extrusionThread = thread[1 :]
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
        for boundaryPoint in self.boundaryPerimeter.boundaryPoints:
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
        
        # Necessary? already there? needed for ordering?
        #threadFunctionDictionary = {
        #    'infill' : self.transferInfillPaths, 'loops' : self.transferClosestFillLoops, 'perimeter' : self.addPerimeterInner}
        #for threadType in threadSequence:
        #    threadFunctionDictionary[threadType](extrusionHalfWidth, oldOrderedLocation, threadSequence)
        
        #self.transferClosestFillLoops(extrusionHalfWidth, oldOrderedLocation, threadSequence)
        self.addPerimeterInner(extrusionHalfWidth, oldOrderedLocation, threadSequence)
        self.transferInfillPaths(extrusionHalfWidth, oldOrderedLocation, threadSequence)
        
    def transferClosestFillLoops(self, extrusionHalfWidth, oldOrderedLocation, threadSequence):
        'Transfer closest fill loops.'
        if len(self.extraLoops) < 1:
            return
        remainingFillLoops = self.extraLoops[:]
        while len(remainingFillLoops) > 0:
            euclidean.transferClosestFillLoop(extrusionHalfWidth, oldOrderedLocation, remainingFillLoops, self)

    def transferInfillPaths(self, extrusionHalfWidth, oldOrderedLocation, threadSequence):
        'Transfer the infill paths.'
        euclidean.transferClosestPaths(oldOrderedLocation, self.infillPathsHolder[:], self)
    
    def addPerimeterInner(self, extrusionHalfWidth, oldOrderedLocation, threadSequence):
        'Add to the perimeter and the inner island.'
        for loop in self.extraLoops:
            innerPerimeterLoop = Loop(self.z, self.runtimeParameters)
            if euclidean.isWiddershins(loop + [loop[0]]):
                innerPerimeterLoop.type  = 'outer'
            else:
                innerPerimeterLoop.type = 'inner'
            innerPerimeterLoop.addPathFromThread(loop + [loop[0]])
            self.loops.append(innerPerimeterLoop)
        
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.addToThreads(extrusionHalfWidth, oldOrderedLocation, threadSequence)

class Path:
    ''' A Path the tool will follow within a nested ring.'''
    def __init__(self, z, runtimeParameters):
        
        #self.nestedRing = weakref.proxy(nestedRing)
        #self.nestedRing = nestedRing
        self.z = z
        self.runtimeParameters = runtimeParameters
        self.verbose = self.runtimeParameters.verboseGcode
        
        self.type = None
        self.startPoint = None
        self.extrusionThread = []
        self.gcodeCommands = []
        
        self.decimalPlaces = self.runtimeParameters.decimalPlaces
        self.activateSpeed = self.runtimeParameters.activateSpeed
        self.bridgeFeedRateMinute = self.runtimeParameters.bridgeFeedRateRatio * self.runtimeParameters.perimeterFeedRate * 60 # todo former reference to main feed now perimeter feed
        self.perimeterFeedRateMinute = self.runtimeParameters.perimeterFeedRate * 60
        self.extrusionFeedRateMinute = 60.0 * self.runtimeParameters.feedRate
        self.travelFeedRateMinute = self.runtimeParameters.travelFeedRate * 60
        self.extrusionUnitsRelative = self.runtimeParameters.extrusionUnitsRelative
        self.totalExtrusionDistance = 0.0
        
        self.activateDimension = self.runtimeParameters.activateDimension
        
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
        '''Get the string representation.'''
        output = StringIO.StringIO()
        output.write('%14stype: %s\n' % ('', self.type))
        output.write('%14sstartPoint: %s\n' % ('', self.startPoint))
        output.write('%14sextrusionThread: %s\n' % ('', self.extrusionThread))
        output.write('%14sgcodeCommands:\n' % '')
        for x in self.gcodeCommands:
            output.write('%16s%s' % ('', printCommand(x)))
        return output.getvalue()    
        
    def getGcodeText(self, output, returnCached=False):
        '''Final Gcode representation.'''
        if not returnCached:
            self.generateGcode()
            
        for command in self.gcodeCommands:
            output.write('%s' % printCommand(command, self.verbose))

    def generateGcode(self):
        'Transforms paths and points to gcode'
        gcodeArgs = [('X', round(self.startPoint.real, self.decimalPlaces)),
                     ('Y', round(self.startPoint.imag, self.decimalPlaces)),
                     ('Z', round(self.z, self.decimalPlaces))]
        
        if self.activateSpeed:
            gcodeArgs.append(('F', self.travelFeedRateMinute))
        
        self.gcodeCommands.append(
            GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
    
        if self.activateDimension:
            # note hardcoded because of retraction calculation
            if self.previousPoint == None:
                extrusionDistance = 0.0
            else:
                extrusionDistance = 0.7
                
            self.previousPoint = self.startPoint
            self.gcodeCommands.extend(self.getRetractReverseCommands(extrusionDistance))
            
        self.gcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_ON))        
        
        for point in self.extrusionThread:
            gcodeArgs = [('X', round(point.real, self.decimalPlaces)),
                         ('Y', round(point.imag, self.decimalPlaces)),
                         ('Z', round(self.z, self.decimalPlaces))]
            
            if self.activateSpeed:
                gcodeArgs.append(('F', self.perimeterFeedRateMinute))
                
            if self.activateDimension:
                extrusionDistance = self.getExtrusionDistance(point, self.flowRate, self.extrusionFeedRateMinute)
                gcodeArgs.append(('E', '%s' % extrusionDistance))
                
            self.gcodeCommands.append(
                GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
            
        if self.activateDimension:
            # IMPORTANT - TODO - calcuating the distance between the end of the perimeter 
            # and the next starting point (either next layer perimeter or infill) is quite 
            # tricky unless the gcode is generated after all plugins are finished.
            # for the time being i'm hardcoding the retraction to 0.7mm
            extrusionDistance = -0.7
            self.gcodeCommands.extend(self.getRetractCommands(extrusionDistance))
            
        self.gcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_OFF))
      
    def getRetractCommands(self, extrusionDistance):
        commands = []
        if self.extrusionUnitsRelative:
            retractDistance = round(extrusionDistance, self.decimalPlaces)
        else:
            self.totalExtrusionDistance += extrusionDistance
            retractDistance = round(self.totalExtrusionDistance, self.decimalPlaces)
    
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.extruderRetractionSpeedMinute)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('E', '%s' % retractDistance)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.perimeterFeedRateMinute)]))
        return commands
    
    def getRetractReverseCommands(self, extrusionDistance):
        commands = []
        if self.extrusionUnitsRelative:
            retractDistance = round(extrusionDistance, self.decimalPlaces)
        else:
            self.totalExtrusionDistance += extrusionDistance
            retractDistance = round(self.totalExtrusionDistance, self.decimalPlaces)
    
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.extruderRetractionSpeedMinute)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('E', '%s' % retractDistance)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.travelFeedRateMinute)]))
                        
        if not self.extrusionUnitsRelative:
            commands.append(self.getResetExtruderDistance())
        return commands
    
    def getResetExtruderDistance(self):
        self.totalExtrusionDistance = 0.0
        return GcodeCommand(gcodes.RESET_EXTRUDER_DISTANCE, [('E', '0')])
        

    def getExtrusionDistance(self, point, flowRate, feedRateMinute):
        distance = 0.0
        
        if self.absolutePositioning:
            if self.previousPoint != None:
                distance = abs(point - self.previousPoint)
            self.previousPoint = point
        else:
            if previousPoint == None:
                logger.warning('There was no absolute location when the G91 command was parsed, so the absolute location will be set to the origin.')
                self.previousPoint = Vector3()
            distance = abs(point)
            self.previousPoint += point
            
        
        scaledFlowRate = flowRate * self.flowScaleSixty
        extrusionDistance = scaledFlowRate / feedRateMinute * distance
        
        if self.extrusionUnitsRelative:
            extrusionDistance = round(extrusionDistance, self.decimalPlaces)
        else:
            self.totalExtrusionDistance += extrusionDistance
            extrusionDistance = round(self.totalExtrusionDistance, self.decimalPlaces)
            
        return extrusionDistance

    def offset(self, offset):
        if self.startPoint != None:
            self.startPoint = complex(self.startPoint.real + offset.real, self.startPoint.imag + offset.imag)

        for (index,point) in enumerate(self.extrusionThread):
            self.extrusionThread[index] = complex(point.real + offset.real, point.imag + offset.imag)
            
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
            self.extrusionThread = thread[1 :]
        else:
            logger.warning('Zero length vertex positions array which was skipped over, this should never happen.')
        if len(thread) < 2:
            logger.warning('Thread of only one point: %s, this should never happen.', thread)
            
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
        
        self.decimalPlaces = config.getfloat('general', 'decimal.places')
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
        self.orbitalFeedRatePerSecond = None
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
        
        self.activateSpeed = config.getboolean('speed', 'active')
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
        
        self.activateDimension = config.getboolean('dimension', 'active')
        self.filamentDiameter = config.getfloat('dimension', 'filament.diameter')
        self.filamentPackingDensity = config.getfloat('dimension', 'filament.packing.density')
        self.oozeRate = config.getfloat('dimension', 'oozerate')
        self.extruderRetractionSpeed = config.getfloat('dimension', 'extruder.retraction.speed')
        self.extrusionUnitsRelative = config.getboolean('dimension', 'extrusion.units.relative')
        
        
        nozzleXsection = (self.nozzleDiameter / 2) ** 2 * pi
        extrusionXsection = ((abs(self.perimeterWidth) + self.layerThickness) / 4) ** 2 * pi
        
        self.flowRate = self.flowRateRatio * self.feedRate
        self.bridgeFlowRate = (self.bridgeFlowRateRatio * self.bridgeFeedRateRatio) * (self.perimeterFlowRateRatio * self.perimeterFeedRate) * (nozzleXsection / extrusionXsection)
        self.perimeterFlowRate = self.perimeterFlowRateRatio * self.perimeterFeedRate
        

class GcodeCommand:
    def __init__(self, commandLetter, parameters=None):
        self.commandLetter = commandLetter
        if parameters == None:
            parameters = {}
        self.parameters = OrderedDict(parameters)
    
    def __str__(self):
        return str(False) 
    
    def str(self, verbose=False):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        output.write('%s ' % (self.commandLetter[0]))
        if (verbose):
            output.write('\t\t\t; %s ' % (self.commandLetter[1]))
        for name, value in self.parameters.items():
            output.write('%s%s ' % (name, value))
        return output.getvalue().strip()


def printCommand(command, verbose=False):
    if command == None:
        return 
    if isinstance(command, GcodeCommand):
        return'%s\n' % command.str(verbose)
    else:
        return '%s\n' % command
