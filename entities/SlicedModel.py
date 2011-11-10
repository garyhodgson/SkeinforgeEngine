from collections import OrderedDict
from config import config
from StringIO import StringIO
import gcodes
import math
import sys
import time
from RuntimeParameters import RuntimeParameters
from GcodeCommand import GcodeCommand 

class SlicedModel:
    '''Runtime data for conversion of 3D model to gcode.'''
    
    def __init__(self):

        self.runtimeParameters = RuntimeParameters()
        self.layers = OrderedDict()
        
        self.startGcodeCommands = []
        self.endGcodeCommands = []
        self.elementOffsets = None

        self.svgText = None
        self.carvingCornerMaximum = None
        self.carvingCornerMinimum = None
        
        # Can we remove this after reading the carving once the layers have been generated??
        self.rotatedLoopLayers = []
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO()
        
        output.write("\nRuntimeParameters:\n%s\n" % vars(self.runtimeParameters))
        
        output.write("\nelementOffsets: %s\n" % self.elementOffsets)
        
        output.write("\nrotatedLoopLayers:\n")
        for rotatedLoopLayer in self.rotatedLoopLayers:
            output.write('%s\n' % vars(rotatedLoopLayer))
            
        output.write("\nstartGcodeCommands:\n")
        for startGcodeCommand in self.startGcodeCommands:
            output.write(GcodeCommand.printCommand(startGcodeCommand, self.runtimeParameters.verboseGcode))
        
        output.write("\nlayers:\n")
        for key in sorted(self.layers.iterkeys()):
            output.write('%s\n' % self.layers[key])
       
        output.write("\nendGcodeCommands:\n")
        for endGcodeCommand in self.endGcodeCommands:
            output.write(GcodeCommand.printCommand(endGcodeCommand, self.runtimeParameters.verboseGcode))
             
        return output.getvalue()