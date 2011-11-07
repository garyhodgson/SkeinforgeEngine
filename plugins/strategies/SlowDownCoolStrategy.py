
def cool(layer, runtimeParameters, coolOptions=None):
    '''Apply the cooling by slowing down the print rate.
        Note: This strategy only sets the feed/flow multiplier for the layer. The gcode 
        engine determines whether this or the minimum layer feed rate is actually used.
        This allows the speed of the gcode to be modified without having to recalculate
        the slowdown ratio.  
    '''
    
    (layerDistance, layerDuration) = layer.getDistanceAndDuration()
    minimumLayerTime = float(coolOptions['minimum.layer.time'])
    layer.feedAndFlowRateMultiplier = min(1.0, layerDuration / minimumLayerTime)
    