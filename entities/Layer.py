from StringIO import StringIO
from config import config
from entities import NestedRing, GcodeCommand
from utilities import memory_tracker
import gcodes
import sys
import time

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
        
        if self.runtimeParameters.dimensionActive:
            if self.runtimeParameters.extrusionUnitsRelative:
                self.preLayerGcodeCommands.append(GcodeCommand(gcodes.RELATIVE_EXTRUSION_DISTANCE))
            else:
                self.preLayerGcodeCommands.append(GcodeCommand(gcodes.ABSOLUTE_EXTRUSION_DISTANCE))
        
        self.combSkein = None
            
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO()
        
        output.write('%2slayer (%s) z:%s\n' % ('', self.index, self.z))
        
        output.write('%2slayer feedAndFlowRateMultiplier:%s\n' % ('', self.feedAndFlowRateMultiplier))
        
        if self.bridgeRotation != None:
            output.write('bridgeRotation %s, ' % self.bridgeRotation)
            
        output.write('%4spreLayerGcodeCommand:' % (''))
        for preLayerGcodeCommand in self.preLayerGcodeCommands:
            output.write(GcodeCommand.printCommand(preLayerGcodeCommand, self.runtimeParameters.verboseGcode))
            
        output.write('%4snestedRings:' % (''))
        for nestedRing in self.nestedRings:
            output.write(nestedRing)
            
        output.write('%4spostLayerGcodeCommand:' % (''))
        for postLayerGcodeCommand in self.postLayerGcodeCommands:
            output.write(GcodeCommand.printCommand(postLayerGcodeCommand, self.runtimeParameters.verboseGcode))
           
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