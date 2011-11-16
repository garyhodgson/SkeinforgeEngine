"""
Apply the cooling by moving the nozzle around the print.
"""
from config import config
from data_structures import GcodeCommand
from fabmetheus_utilities import euclidean
import gcodes

def getStrategy(runtimeParameters):
    '''Returns an instance of the strategy'''
    return OrbitCoolStrategy(runtimeParameters)

class OrbitCoolStrategy:
    '''Allows a layer to cool by orbiting around the model for a set time.'''
    def __init__(self, runtimeParameters):
        
        self.minimumLayerTime = config.getfloat('cool','minimum.layer.time')
        self.orbitalFeedRateSecond = runtimeParameters.orbitalFeedRateSecond
        self.orbitalFeedRateMinute = runtimeParameters.orbitalFeedRateMinute
        self.oribitalMarginDistance = config.getfloat('cool','orbital.margin')
        self.oribitalMargin = complex(self.oribitalMarginDistance, self.oribitalMarginDistance)
        self.decimalPlaces = runtimeParameters.decimalPlaces
        
        
    def cool(self, layer):
        '''Apply the cooling by moving the nozzle around the print.'''
        
        if layer.index == 0:
            # We don't have to slow down on the first layer
            return
        
        (layerDistance, layerDuration) = layer.getDistanceAndDuration()
        remainingOrbitTime = max(self.minimumLayerTime - layerDuration, 0.0)

        boundaryLayerLoops = []
        for nestedRing in layer.nestedRings:
            boundaryLayerLoops.append(nestedRing.getXYBoundaries())
        
        if remainingOrbitTime > 0.0 and boundaryLayerLoops != None:          
            if len(boundaryLayerLoops) < 1:
                return
            
            largestLoop = euclidean.getLargestLoop(boundaryLayerLoops)
            cornerMinimum = euclidean.getMinimumByComplexPath(largestLoop) - self.oribitalMargin
            cornerMaximum = euclidean.getMaximumByComplexPath(largestLoop) + self.oribitalMargin
    
            largestLoop = euclidean.getSquareLoopWiddershins(cornerMaximum, cornerMinimum)
            
            if len(largestLoop) > 1 and remainingOrbitTime > 1.5 :
                timeInOrbit = 0.0
                
                while timeInOrbit < remainingOrbitTime:
                    for point in largestLoop:
                        gcodeArgs = [('X', round(point.real, self.decimalPlaces)),
                                     ('Y', round(point.imag, self.decimalPlaces)),
                                     ('Z', round(layer.z, self.decimalPlaces)),
                                     ('F', round(self.orbitalFeedRateMinute, self.decimalPlaces))]
                        layer.preLayerGcodeCommands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
                    timeInOrbit += euclidean.getLoopLength(largestLoop) / self.orbitalFeedRateSecond
