from config import config
from fabmetheus_utilities.vector3 import Vector3
from entities import GcodeCommand, TravelPath
from plugins.comb import CombSkein
import StringIO
import gcodes
import sys
import time
import entities.paths as paths

class GcodeWriter:
    '''Writes the slicedModel for a sliced model.'''
    
    def __init__(self, slicedModel):
        self.slicedModel = slicedModel
        
        
    def getSlicedModel(self, verbose=False):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
                    
        for startCommand in self.slicedModel.startGcodeCommands:
            output.write(printCommand(startCommand, verbose))
            
        lookaheadStartVector = None
        lookaheadKeyIndex = 0
        layerCount = len(self.slicedModel.layers)
        for key in sorted(self.slicedModel.layers.iterkeys()):
            lookaheadStartPoint = None
            lookaheadKeyIndex = lookaheadKeyIndex + 1
            if lookaheadKeyIndex < layerCount:
                lookaheadKey = self.slicedModel.layers.keys()[lookaheadKeyIndex]
                lookaheadLayer = self.slicedModel.layers[lookaheadKey]
                lookaheadStartPoint = lookaheadLayer.getStartPoint()
                lookaheadStartVector = Vector3(lookaheadStartPoint.real, lookaheadStartPoint.imag, lookaheadLayer.z)

            self.getLayer(self.slicedModel.layers[key], output, lookaheadStartVector, verbose)
            
        for endCommand in self.slicedModel.endGcodeCommands:
            output.write(printCommand(endCommand, verbose))
                        
        return output.getvalue()
    
    
    def getLayer(self, layer, output, parentLookaheadStartVector=None, verbose=False):
        '''Final Gcode representation.'''
        for preLayerGcodeCommand in layer.preLayerGcodeCommands:
            output.write(printCommand(preLayerGcodeCommand, verbose))
        
        if layer.runtimeParameters.combActive: 
            combSkein = CombSkein(layer)
        else:
            combSkein = None                        
        
        pathList = layer.getOrderedPathList()
        paths.resetExtrusionStats()
        
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
            
            self.getPath(travelPath, output, lookaheadVector, layer.feedAndFlowRateMultiplier, verbose)
            
            self.getPath(path, output, lookaheadVector, layer.feedAndFlowRateMultiplier, verbose)
        
        for postLayerGcodeCommand in layer.postLayerGcodeCommands:
            output.write(printCommand(postLayerGcodeCommand, verbose))
            
    def getPath(self, path, output, lookaheadStartVector=None, feedAndFlowRateMultiplier=1.0, verbose=False):
        '''Final Gcode representation.'''
        path.generateGcode(lookaheadStartVector, feedAndFlowRateMultiplier, self.slicedModel.runtimeParameters)
            
        for command in path.gcodeCommands:
            output.write('%s' % printCommand(command, verbose))

def printCommand(command, verbose=False):
    if command == None:
        return 
    if isinstance(command, GcodeCommand):
        return'%s\n' % command.str(verbose)
    else:
        return '%s\n' % command
