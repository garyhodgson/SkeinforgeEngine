from config import config
from fabmetheus_utilities.vector3 import Vector3
from entities import GcodeCommand, TravelPath
from plugins.comb import CombSkein
import StringIO
import gcodes
import sys
import time

class GcodeWriter:
    '''Writes the gcode for a sliced model.'''
    
    def __init__(self, gcode):
        self.gcode = gcode
        
        
    def getSlicedModelAsGcode(self, verbose=False):
        '''Final gcode representation.'''
        output = StringIO.StringIO()
                    
        for startCommand in self.gcode.startGcodeCommands:
            output.write(printCommand(startCommand, verbose))
            
        lookaheadStartVector = None
        lookaheadKeyIndex = 0
        layerCount = len(self.gcode.layers)
        for key in sorted(self.gcode.layers.iterkeys()):
            lookaheadStartPoint = None
            lookaheadKeyIndex = lookaheadKeyIndex + 1
            if lookaheadKeyIndex < layerCount:
                lookaheadKey = self.gcode.layers.keys()[lookaheadKeyIndex]
                lookaheadLayer = self.gcode.layers[lookaheadKey]
                lookaheadStartPoint = lookaheadLayer.getStartPoint()
                lookaheadStartVector = Vector3(lookaheadStartPoint.real, lookaheadStartPoint.imag, lookaheadLayer.z)

            self.getLayerAsGcode(self.gcode.layers[key], output, lookaheadStartVector, verbose)
            
        for endCommand in self.gcode.endGcodeCommands:
            output.write(printCommand(endCommand, verbose))
                        
        return output.getvalue()
    
    
    def getLayerAsGcode(self, layer, output, parentLookaheadStartVector=None, verbose=False):
        '''Final Gcode representation.'''
        
        for preLayerGcodeCommand in layer.preLayerGcodeCommands:
            output.write(printCommand(preLayerGcodeCommand, verbose))
            
        if layer.runtimeParameters.combActive: 
            combSkein = CombSkein(layer)            
        
        pathList = layer.getOrderedPathList()        
        
        pathListCount = len(pathList)
        for (index, path) in enumerate(pathList):
            if index + 1 < pathListCount:
                lookaheadStartPoint = pathList[index + 1].getStartPoint()
                lookaheadVector = Vector3(lookaheadStartPoint.real, lookaheadStartPoint.imag, layer.z)
            else:
                lookaheadVector = parentLookaheadStartVector
                
            previousVector = None
            if index > 0:
                previousPoint = pathList[index - 1].getEndPoint()
                previousVector = Vector3(previousPoint.real, previousPoint.imag, layer.z)
                
            nextPoint = path.getStartPoint()
            nextVector = Vector3(nextPoint.real, nextPoint.imag, layer.z)
            
            travelPath = TravelPath(layer.z, layer.runtimeParameters, previousVector, nextVector, combSkein)
            self.getPathAsGcode(travelPath, output, lookaheadVector, layer.feedAndFlowRateMultiplier, verbose)
            
            self.getPathAsGcode(path, output, lookaheadVector, layer.feedAndFlowRateMultiplier, verbose)
        
        for postLayerGcodeCommand in layer.postLayerGcodeCommands:
            output.write(printCommand(postLayerGcodeCommand, verbose))
            
    def getPathAsGcode(self, path, output, lookaheadStartVector=None, feedAndFlowRateMultiplier=1.0, verbose=False):
        '''Final Gcode representation.'''
        path.generateGcode(lookaheadStartVector, feedAndFlowRateMultiplier)
            
        for command in path.gcodeCommands:
            output.write('%s' % printCommand(command, verbose))

def printCommand(command, verbose=False):
    if command == None:
        return 
    if isinstance(command, GcodeCommand):
        return'%s\n' % command.str(verbose)
    else:
        return '%s\n' % command
