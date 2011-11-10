from fabmetheus_utilities import intercircle, euclidean
from data_structures import GcodeCommand
import gcodes, math

def cool(layer, runtimeParameters, coolOptions=None):
    '''Apply the cooling by moving the nozzle around the print.'''
    
    if layer.index == 0:
        # We don't have to slow down on the first layer
        return
    
    (layerDistance, layerDuration) = layer.getDistanceAndDuration()
    minimumLayerTime = float(coolOptions['minimum.layer.time'])
    remainingOrbitTime = max(minimumLayerTime - layerDuration, 0.0)
    oribitalMarginDistance = float(coolOptions['orbital.margin'])
    oribitalMargin = complex(oribitalMarginDistance, oribitalMarginDistance)
        
    boundaryLayerLoops = []
    for nestedRing in layer.nestedRings:
        boundaryLayerLoops.append(nestedRing.getXYBoundaries())
    
    if remainingOrbitTime > 0.0 and boundaryLayerLoops != None:          
        if len(boundaryLayerLoops) < 1:
            return
        
        largestLoop = euclidean.getLargestLoop(boundaryLayerLoops)
        cornerMinimum = euclidean.getMinimumByComplexPath(largestLoop) - oribitalMargin
        cornerMaximum = euclidean.getMaximumByComplexPath(largestLoop) + oribitalMargin

        largestLoop = euclidean.getSquareLoopWiddershins(cornerMaximum, cornerMinimum)
        
        if len(largestLoop) > 1 and remainingOrbitTime > 1.5 :
            timeInOrbit = 0.0
            
            while timeInOrbit < remainingOrbitTime:
                for point in largestLoop:
                    gcodeArgs = [('X', round(point.real, runtimeParameters.decimalPlaces)),
                                 ('Y', round(point.imag, runtimeParameters.decimalPlaces)),
                                 ('Z', round(layer.z, runtimeParameters.decimalPlaces)),
                                 ('F', round(runtimeParameters.orbitalFeedRateMinute, runtimeParameters.decimalPlaces))]
                    layer.preLayerGcodeCommands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
                timeInOrbit += euclidean.getLoopLength(largestLoop) / runtimeParameters.orbitalFeedRatePerSecond
