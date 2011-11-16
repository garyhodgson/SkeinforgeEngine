"""
Allows a layer to cool slowing down the nozzle movement.
"""
from config import config
from fabmetheus_utilities import euclidean
import gcodes


def getStrategy(runtimeParameters):
    '''Returns an instance of the strategy'''
    return SlowDownCoolStrategy(runtimeParameters)

class SlowDownCoolStrategy:
    '''Allows a layer to cool slowing down the nozzle movement.'''
    def __init__(self, runtimeParameters):
        
        self.minimumLayerTime = config.getfloat('cool','minimum.layer.time')
                
        
    def cool(self, layer):
        '''Apply the cooling by slowing down the print rate.
            Note: This strategy only sets the feed/flow multiplier for the layer. The gcode 
            engine determines whether this or the minimum layer feed rate is actually used.
            This allows the speed of the gcode to be modified without having to recalculate
            the slowdown ratio.  
        '''
        
        (layerDistance, layerDuration) = layer.getDistanceAndDuration()
        layer.feedAndFlowRateMultiplier = min(1.0, layerDuration / self.minimumLayerTime)
        