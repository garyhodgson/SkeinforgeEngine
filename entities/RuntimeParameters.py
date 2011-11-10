from config import config
import time
from math import pi

class RuntimeParameters:
    def __init__(self):
        self.startTime = time.time()
        self.endTime = None
        self.inputFilename = None
        self.outputFilename = None
        
        self.profileMemory = config.getboolean('general', 'profile.memory')
        
        self.decimalPlaces = config.getint('general', 'decimal.places')
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
        
        self.speedActive = config.getboolean('speed', 'active')
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
        
        self.dimensionActive = config.getboolean('dimension', 'active')
        self.filamentDiameter = config.getfloat('dimension', 'filament.diameter')
        self.filamentPackingDensity = config.getfloat('dimension', 'filament.packing.density')
        self.oozeRate = config.getfloat('dimension', 'oozerate')
        self.extruderRetractionSpeed = config.getfloat('dimension', 'extruder.retraction.speed')
        self.extrusionUnitsRelative = config.getboolean('dimension', 'extrusion.units.relative')
        self.dimensionDecimalPlaces = config.getint('dimension', 'decimal.places')
        
        self.extrusionPrintOrder = config.get('fill', 'extrusion.sequence.print.order').split(',')
        
        self.bridgeFeedRateMinute = self.bridgeFeedRateRatio * self.perimeterFeedRate * 60 # todo former reference to main feed now perimeter feed
        self.perimeterFeedRateMinute = self.perimeterFeedRate * 60
        self.extrusionFeedRateMinute = self.feedRate * 60.0
        self.travelFeedRateMinute = self.travelFeedRate * 60
        
        self.minimumLayerFeedRate = config.getfloat('cool', 'minimum.layer.feed.rate')
        self.minimumLayerFeedRateMinute = self.minimumLayerFeedRate * 60
        
        self.minimumBridgeFeedRateMultiplier = self.minimumLayerFeedRateMinute / self.bridgeFeedRateMinute
        self.minimumPerimeterFeedRateMultiplier = self.minimumLayerFeedRateMinute / self.perimeterFeedRateMinute        
        self.minimumExtrusionFeedRateMultiplier = self.minimumLayerFeedRateMinute / self.extrusionFeedRateMinute
        self.minimumTravelFeedRateMultiplier = self.minimumLayerFeedRateMinute / self.travelFeedRateMinute
        
        nozzleXsection = (self.nozzleDiameter / 2) ** 2 * pi
        extrusionXsection = ((abs(self.perimeterWidth) + self.layerThickness) / 4) ** 2 * pi
        
        self.flowRate = self.flowRateRatio * self.feedRate
        self.bridgeFlowRate = (self.bridgeFlowRateRatio * self.bridgeFeedRateRatio) * (self.perimeterFlowRateRatio * self.perimeterFeedRate) * (nozzleXsection / extrusionXsection)
        self.perimeterFlowRate = self.perimeterFlowRateRatio * self.perimeterFeedRate
        
        self.orbitalFeedRateSecond = (self.feedRate * self.orbitalFeedRateRatio)
        self.orbitalFeedRateMinute = self.orbitalFeedRateSecond * 60
        
        self.combActive = config.getboolean('comb', 'active')
