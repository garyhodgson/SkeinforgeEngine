from GcodeCommand import GcodeCommand
from StringIO import StringIO
from collections import OrderedDict
from config import config
from fabmetheus_utilities.vector3 import Vector3
from math import pi
from utilities import memory_tracker
import gcodes
import math
import sys
import time

# globals used as an easy way to maintain state between layer changes
_totalExtrusionDistance = 0.0
_previousPoint = None

class Path:
    ''' A Path the tool will follow within a nested ring.'''
    def __init__(self, z, runtimeParameters):
        
        self.z = z
        self.runtimeParameters = runtimeParameters
        
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
        output = StringIO()
        output.write('%14stype: %s\n' % ('', self.type))
        output.write('%14sstartPoint: %s\n' % ('', self.startPoint))
        output.write('%14spoints: %s\n' % ('', self.points))
        output.write('%14sgcodeCommands:\n' % '')
        for command in self.gcodeCommands:
            output.write('%16s%s' % ('', GcodeCommand.printCommand(command)))
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

    def generateGcode(self, lookaheadStartVector=None, feedAndFlowRateMultiplier=1.0):
        'Transforms paths and points to gcode'
        global _previousPoint
        self.gcodeCommands = []
        
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

class InfillPath(Path):
    
    def __init__(self, z, runtimeParameters):        
        Path.__init__(self, z, runtimeParameters)
            
class TravelPath(Path):
    '''Moves from one path to another without extruding. Optionally dodges gaps (comb) and retracts (dimension)'''
    
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
        output = StringIO()
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
        output = StringIO()
        output.write('%12sboundaryPerimeter:\n' % '')
        output.write('%14sboundaryPoints: %s\n' % ('', self.boundaryPoints))
        output.write(Loop.__str__(self))
        return output.getvalue()
    
    def offset(self, offset):
        for boundaryPoint in self.boundaryPoints:
            boundaryPoint.x += offset.real
            boundaryPoint.y += offset.imag            
        Loop.offset(self, offset)       