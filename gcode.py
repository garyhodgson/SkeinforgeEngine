from collections import OrderedDict
from config import config
from decimal import Decimal, ROUND_HALF_UP
from fabmetheus_utilities import euclidean
from fabmetheus_utilities.vector3 import Vector3
from math import log10, floor, pi
from plugins.speed import SpeedSkein
import StringIO
import decimal
import gcodes
import time
import weakref

def sa_round(f, digits=0):
    """
    Symmetric Arithmetic Rounding for decimal numbers
    f       - float to round
    digits  - number of digits after the point to leave
    """
    decimal.getcontext().prec = 12
    return str(Decimal(str(f)).quantize(Decimal("1") / (Decimal('10') ** digits), ROUND_HALF_UP))

def printCommand(x, verbose=False):
    if isinstance(x, GcodeCommand):
        return'%s\n' % x.str(verbose)
    else:
        return '%s\n' % x
            
class Gcode:
    '''Runtime data for conversion of 3D model to gcode.'''
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.runtimeParameters = RuntimeParameters()
        self.rotatedLoopLayers = []
        self.layers = OrderedDict()
        
        self.startGcodeCommands = []
        self.endGcodeCommands = []
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        
        output.write("\n\nRuntimeParameters:\n%s\n\n" % vars(self.runtimeParameters))
        
        output.write("rotatedLoopLayers:\n")
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
    
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
        
        for x in self.startGcodeCommands:
            output.write(printCommand(x, self.verbose))

        for key in sorted(self.layers.iterkeys()):
            output.write('%s' % self.layers[key].getGcodeText())

        for x in self.endGcodeCommands:
            output.write(printCommand(x, self.verbose))
                        
        return output.getvalue()

class Layer:
    def __init__(self, z, gcode):
        self.z = z
        self.gcode = weakref.proxy(gcode)
        self.bridgeRotation = None
        self.nestedRings = []
        
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        
        
        
        output.write('\n\tlayer %s' % self.z)
        if self.bridgeRotation != None:
            output.write('bridgeRotation %s, ' % self.bridgeRotation)
            
        output.write('\n\t\tnestedRings:\n')
        for x in self.nestedRings:
            output.write('%s\n' % x)
            
        return output.getvalue()
    
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
        for x in self.nestedRings:
            output.write(x.getGcodeText())
        return output.getvalue()
    
    def addNestedRing(self, nestedRing):
        self.nestedRings.append(nestedRing)
   

class NestedRing:
    def __init__(self, layer):
        self.layer = weakref.proxy(layer)
        self.runtimeParameters = self.layer.gcode.runtimeParameters
        self.decimalPlaces = self.layer.gcode.runtimeParameters.decimalPlaces
        self.z = self.layer.z
        self.verbose = layer.gcode.verbose
        self.boundaryPerimeters = []
        self.innerNestedRings = []
        self.extraLoops = []
        self.penultimateFillLoops = []
        self.lastFillLoops = None
        self.infillPaths = []
        self.infillGcodeCommands = []
        self.activateSpeed = self.runtimeParameters.activateSpeed
        self.bridgeFeedRateMinute = self.runtimeParameters.bridgeFeedRateRatio * self.layer.gcode.runtimeParameters.perimeterFeedRate * 60 # todo former reference to main feed now perimeter feed
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
        self.previousPoint = None
        
    def __str__(self):
        output = StringIO.StringIO()
        
        output.write('\n\t\t\tboundaryPerimeters:\n')
        for x in self.boundaryPerimeters:
            output.write('%s\n' % x)
                    
        output.write('\n\t\t\tinnerNestedRings:\n')
        for x in self.innerNestedRings:
            output.write('\t\t\t\t%s\n' % x)
            
        output.write('\n\t\t\textraLoops:\n')
        for x in self.extraLoops:
            output.write('\t\t\t\t%s\n' % x)
            
        output.write('\n\t\t\tpenultimateFillLoops:\n')
        for x in self.penultimateFillLoops:
            output.write('\t\t\t\t%s\n' % x)
        
        output.write('\n\t\t\tlastFillLoops:\n')
        if self.lastFillLoops != None:
            for x in self.lastFillLoops:
                output.write('\t\t\t\t%s\n' % x)
            
        output.write('\n\t\t\tinfillPaths:\n')
        for x in self.infillPaths:
            output.write('\t\t\t\t%s\n' % x)
        
        output.write('\t\t\t\tinfillGcodeCommands:\n')
        for x in self.infillGcodeCommands:
            output.write(printCommand(x, self.verbose))
            
        return output.getvalue()
    
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
        
        for x in self.boundaryPerimeters:
            output.write(x.getGcodeText())
        
        for x in self.infillGcodeCommands:
            output.write(printCommand(x, self.verbose))
        return output.getvalue()
 
    def addBoundaryPerimeter(self, boundaryPointsLoop, perimeterLoop=None):
        boundaryPerimeter = BoundaryPerimeter(self)
        
        for point in boundaryPointsLoop:
            boundaryPerimeter.boundaryPoints.append(Vector3(point.real, point.imag, self.z))
            
        if len(boundaryPointsLoop) < 2:
            return
        
        if perimeterLoop == None:
            perimeterLoop = boundaryPointsLoop
            
        if euclidean.isWiddershins(perimeterLoop):
            boundaryPerimeter.perimeterType = 'outer'
        else:
            boundaryPerimeter.perimeterType = 'inner'
        thread = perimeterLoop + [perimeterLoop[0]]
        self.addPerimeterGcodeFromThread(thread, boundaryPerimeter)
                
    def addPerimeterGcodeFromThread(self, thread, boundaryPerimeter=None):
        'Add a thread to the output.'
        if boundaryPerimeter == None:
            boundaryPerimeter = BoundaryPerimeter(self)
        decimalPlaces = self.decimalPlaces

        if len(thread) > 0:
            
            # Move to start position - no extrusion
            point = thread[0]
            gcodeArgs = [('X', round(point.real, decimalPlaces)),
                ('Y', round(point.imag, decimalPlaces)),
                ('Z', round(self.layer.z, decimalPlaces))]
            if self.activateSpeed:
                gcodeArgs.append(('F', self.travelFeedRateMinute))
            boundaryPerimeter.perimeterGcodeCommands.append(
                GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
            
        else:
            logger.warning('Zero length vertex positions array which was skipped over, this should never happen.')
        if len(thread) < 2:
            logger.warning('Thread of only one point: %s, this should never happen.', thread)
            return

        if self.activateDimension:
            # note hardcoded because of retraction calculation
            if self.previousPoint == None:
                extrusionDistance = 0.0
            else:
                extrusionDistance = 0.7
                
            self.previousPoint = point
            boundaryPerimeter.perimeterGcodeCommands.extend(self.getRetractReverseCommands(extrusionDistance))
            
        boundaryPerimeter.perimeterGcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_ON))        
        
        for point in thread[1 :]:
            gcodeArgs = [('X', round(point.real, decimalPlaces)),
                         ('Y', round(point.imag, decimalPlaces)),
                         ('Z', round(self.layer.z, decimalPlaces))]
            
            if self.activateSpeed:
                gcodeArgs.append(('F', self.perimeterFeedRateMinute))
                
            if self.activateDimension:
                extrusionDistance = self.getExtrusionDistance(self.previousPoint, point)
                gcodeArgs.append(('E', '%s' % extrusionDistance))
                
            boundaryPerimeter.perimeterGcodeCommands.append(
                GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
            
        if self.activateDimension:
            # IMPORTANT - TODO - calcuating the distance between the end of the perimeter 
            # and the next starting point (either next layer perimeter or infill) is quite 
            # tricky unless the gcode is generated after all plugins are finished.
            # for the time being i'm hardcoding the retraction to 0.7mm
            extrusionDistance = -0.7
            boundaryPerimeter.perimeterGcodeCommands.extend(self.getRetractCommands(extrusionDistance))
            
        boundaryPerimeter.perimeterGcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_OFF))    
        self.boundaryPerimeters.append(boundaryPerimeter)
    
    def getResetExtruderDistance(self):
        self.totalExtrusionDistance = 0.0
        return GcodeCommand(gcodes.RESET_EXTRUDER_DISTANCE, [('E', '0')])
        

    def getExtrusionDistance(self, previousPoint, point):
        distance = 0.0
        if self.absolutePositioning:
            if previousPoint != None:
                distance = abs(point - previousPoint)
            previousPoint = point
        else:
            if previousPoint == None:
                logger.warning('There was no absolute location when the G91 command was parsed, so the absolute location will be set to the origin.')
                previousPoint = Vector3()
            distance = abs(point)
            previousPoint += point
        filamentRadius = 0.5 * self.filamentDiameter
        filamentPackingArea = pi * filamentRadius * filamentRadius * self.filamentPackingDensity
        flowScaleSixty = 60.0 * ((((self.layerThickness + self.perimeterWidth) / 4) ** 2 * pi) / filamentPackingArea)
        scaledFlowRate = self.flowRate * flowScaleSixty
        extrusionDistance = scaledFlowRate / self.extrusionFeedRateMinute * distance
        if self.extrusionUnitsRelative:
            extrusionDistance = round(extrusionDistance, self.decimalPlaces)
        else:
            self.totalExtrusionDistance += extrusionDistance
            extrusionDistance = round(self.totalExtrusionDistance, self.decimalPlaces)
        return extrusionDistance

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

    def addInfillGcodeFromThread(self, thread):
        'Add a thread to the output.'
        decimalPlaces = self.decimalPlaces
        if len(thread) > 0:
            point = thread[0]
            gcodeArgs = [('X', round(point.real, decimalPlaces)),
                            ('Y', round(point.imag, decimalPlaces)),
                            ('Z', round(self.layer.z, decimalPlaces))]
            if self.activateSpeed:
                gcodeArgs.append(('F', self.travelFeedRateMinute))
            self.infillGcodeCommands.append(
                GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
        else:
            logger.warning('Zero length vertex positions array which was skipped over, this should never happen.')
        if len(thread) < 2:
            logger.warning('Thread of only one point: %s, this should never happen.', thread)
            return
        
        if self.activateDimension:
            # note hardcoded because of retraction calculation
            if self.previousPoint == None:
                extrusionDistance = 0.0
            else:
                extrusionDistance = 0.7
                
            self.previousPoint = point
            self.infillGcodeCommands.extend(self.getRetractReverseCommands(extrusionDistance))
            
        self.infillGcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_ON))
        for point in thread[1 :]:
            gcodeArgs = [('X', round(point.real, decimalPlaces)),('Y', round(point.imag, decimalPlaces)),('Z', round(self.layer.z, decimalPlaces))]
            if self.activateSpeed:
                feedRate = self.extrusionFeedRateMinute if self.layer.bridgeRotation == None else self.bridgeFeedRateMinute
                gcodeArgs.append(('F', feedRate))
            
            if self.activateDimension:
                extrusionDistance = self.getExtrusionDistance(self.previousPoint, point)
                gcodeArgs.append(('E', '%s' % extrusionDistance))
                
            self.infillGcodeCommands.append(
                GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
            
        if self.activateDimension:
            
            # IMPORTANT - TODO - calcuating the distance between the end of the perimeter 
            # and the next starting point (either next layer perimeter or infill) is quite 
            # tricky unless the gcode is generated after all plugins are finished.
            # for the time being i'm hardcoding the retraction to 0.7mm
            extrusionDistance = -0.7
            self.infillGcodeCommands.extend(self.getRetractCommands(extrusionDistance))
            
        self.infillGcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_OFF))    

    def getLoopsToBeFilled(self):
        'Get last fill loops from the outside loop and the loops inside the inside loops.'
        if self.lastFillLoops == None:
            return self.getSurroundingBoundaries()
        return self.lastFillLoops
    
    def getXYBoundaries(self):
        '''Converts XYZ boundary points to XY'''
        xyBoundaries = []
        for boundaryPerimeter in self.boundaryPerimeters:
            xy_boundary = []
            for boundaryPoint in boundaryPerimeter.boundaryPoints:
                xy_boundary.append(boundaryPoint.dropAxis())
            xyBoundaries.extend(xy_boundary)
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
        self.infillPaths = euclidean.getTransferredPaths(paths, self.getXYBoundaries())
        
    def addToThreads(self, extrusionHalfWidth, oldOrderedLocation, threadSequence):
        'Add to paths from the last location. perimeter>inner >fill>paths or fill> perimeter>inner >paths'
        # not necessary as already there??????????????
        #addSurroundingLoopBeginning(skein.gcodeCodec, self.boundary, self.z)
        
        # Necessary? already there? needed for ordering?
        #threadFunctionDictionary = {
        #    'infill' : self.transferInfillPaths, 'loops' : self.transferClosestFillLoops, 'perimeter' : self.addPerimeterInner}
        #for threadType in threadSequence:
        #    threadFunctionDictionary[threadType](extrusionHalfWidth, oldOrderedLocation, threadSequence)
        
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
        euclidean.transferClosestPaths(oldOrderedLocation, self.infillPaths[:], self)
    
    def addPerimeterInner(self, extrusionHalfWidth, oldOrderedLocation, threadSequence):
        'Add to the perimeter and the inner island.'
        #if self.loop == None:
        #    euclidean.transferClosestPaths(oldOrderedLocation, self.perimeterPaths[:], self)
        #else:
        #    euclidean.addToThreadsFromLoop(extrusionHalfWidth, 'perimeter', self.loop[:], oldOrderedLocation, self)
        
        
        ##!!!!!!!!!!!!!!!!!!!
        for loop in self.extraLoops:
           # print "loop",loop
           # print "loop + [loop[0]]",loop + [loop[0]]
           #loop + [loop[0]] means go back to start, i.e. form complete loop
           self.addPerimeterGcodeFromThread(loop + [loop[0]], None)
        
        
        #self.addToThreads(extrusionHalfWidth, self.innerNestedRings[:], oldOrderedLocation, skein, threadSequence)
        for innerNestedRing in self.innerNestedRings:
            innerNestedRing.addToThreads(extrusionHalfWidth, oldOrderedLocation, threadSequence)
        
        
class BoundaryPerimeter:
    def __init__(self, nestedRing):
        self.nestedRing = weakref.proxy(nestedRing)
        self.verbose = nestedRing.layer.gcode.verbose
        self.boundaryPoints = [] 
        self.perimeterType = None
        self.perimeterGcodeCommands = []

    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        output.write('\tboundaryPoints: %s\n' % self.boundaryPoints)
        output.write('\tperimeterType: %s\n' % self.perimeterType)
        output.write('\tperimeterGcodeCommands:\n')
        for x in self.perimeterGcodeCommands:
            output.write(printCommand(x))
        return output.getvalue()
    
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
        
        for x in self.perimeterGcodeCommands:
            output.write(printCommand(x, self.verbose))
        
        return output.getvalue()


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
