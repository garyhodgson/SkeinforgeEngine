from collections import OrderedDict
from config import config
from fabmetheus_utilities import euclidean
from fabmetheus_utilities.vector3 import Vector3
import StringIO
import gcodes
import time
import weakref
from math import log10, floor

def round_sig(x, s=2):
    f = '%%.%gg' % s
    return '%s' % float(f % x)

class Gcode:
    '''Runtime data for conversion of 3D model to gcode.'''
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.runtimeParameters = RuntimeParameters()
        self.rotatedLoopLayers = []
        self.layers = {}
        
        self.startGcodeCommands = []
        self.endGcodeCommands = []
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        
        output.write("\n\nRuntimeParameters:\n%s\n\n" % vars(self.runtimeParameters))
        
        output.write("rotatedLoopLayers:\n")
        for x in self.rotatedLoopLayers:
            output.write('%s\n' % vars(x))
            
        output.write("\nstartGcodeCommands:\n")
        for x in self.startGcodeCommands:
            if isinstance(x, GcodeCommand):
                output.write('%s\n' % x.str(self.verbose))
            else:
                output.write('%s\n' % x)
        
        output.write("\nendGcodeCommands:\n")
        for x in self.endGcodeCommands:
            if isinstance(x, GcodeCommand):
                output.write('%s\n' % x.str(self.verbose))
            else:
                output.write('%s\n' % x)
        
        output.write("\nlayers:\n")
        for key in sorted(self.layers.iterkeys()):
            output.write('%s\n' % self.layers[key])
        
        return output.getvalue()
    
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
        
        for x in self.startGcodeCommands:
            if isinstance(x, GcodeCommand):
                output.write('%s\n' % x.str(self.verbose))
            else:
                output.write('%s\n' % x)

        for key in sorted(self.layers.iterkeys()):
            output.write('%s' % self.layers[key].getGcodeText())

        for x in self.endGcodeCommands:
            if isinstance(x, GcodeCommand):
                output.write('%s\n' % x.str(self.verbose))
            else:
                output.write('%s\n' % x)
                        
        return output.getvalue()

class RuntimeParameters:
    def __init__(self):
        self.startTime = time.time()
        self.endTime = None
        self.decimalPlaces = None
        self.layerThickness = None
        self.perimeterWidth = None
        self.profileName = None
        self.bridgeWidthMultiplier = None
        self.nozzleDiameter = None

class GcodeCommand:
    def __init__(self, commandLetter, parameters=None):
        self.commandLetter = commandLetter
        if parameters == None:
            parameters = {}
        self.parameters = OrderedDict(parameters)
    
    def __str__(self):
        return str(False) 
    
    def str(self, verbose=False):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        output.write('%s ' % (self.commandLetter[0]))
        if (verbose):
            output.write('\t\t\t; %s ' % (self.commandLetter[1]))
        for name, value in self.parameters.items():
            output.write('%s%s ' % (name, value))
        return output.getvalue().strip()

class Layer:
    def __init__(self, z, gcode):
        self.z = z
        self.gcode = weakref.proxy(gcode)
        self.bridgeRotation = None
        self.boundaryPerimeters = []
        self.loops = []
        self.gcodeCommands = []
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        
        output.write('\nlayer %s' % self.z)
        if self.bridgeRotation != None:
            output.write('bridgeRotation %s, ' % self.bridgeRotation)
            
        output.write('\nboundaryPerimeters:\n')
        for x in self.boundaryPerimeters:
            output.write('%s\n' % x)
            
        output.write('loops: %s\n, ' % self.loops)
        output.write('gcodeCommands: %s' % self.gcodeCommands)
        return output.getvalue()
    
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
        for x in self.boundaryPerimeters:
            output.write('%s' % x.getGcodeText())
        return output.getvalue()
    
    def addBoundaryPerimeter(self, loop):
        boundaryPerimeter = BoundaryPerimeter()
        for point in loop:
            boundaryPerimeter.boundaryPoints.append(Vector3(point.real, point.imag, self.z))
        if len(loop) < 2:
            return
        
        if euclidean.isWiddershins(loop):
            boundaryPerimeter.perimeterType = 'outer'
        else:
            boundaryPerimeter.perimeterType = 'inner'
        thread = loop + [loop[0]]
        self.addGcodeFromThread(thread, boundaryPerimeter)
                
    def addGcodeFromThread(self, thread, boundaryPerimeter=None):
        'Add a thread to the output.'
        if boundaryPerimeter == None:
            boundaryPerimeter = BoundaryPerimeter()
        decimalPlaces = self.gcode.runtimeParameters.decimalPlaces
        if len(thread) > 0:
            point = thread[0]
            boundaryPerimeter.perimeterGcodeCommands.append(
                GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT,
                            [('X', round_sig(point.real, decimalPlaces)),
                            ('Y', round_sig(point.imag, decimalPlaces)),
                            ('Z', round_sig(self.z, decimalPlaces))]))
        else:
            logger.warning('Zero length vertex positions array which was skipped over, this should never happen.')
        if len(thread) < 2:
            logger.warning('Thread of only one point: %s, this should never happen.', thread)
            return
        for point in thread[1 :]:
            boundaryPerimeter.perimeterGcodeCommands.append(
                GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT,
                            [('X', round_sig(point.real, decimalPlaces)),
                            ('Y', round_sig(point.imag, decimalPlaces)),
                            ('Z', round_sig(self.z, decimalPlaces))]))
            
        self.boundaryPerimeters.append(boundaryPerimeter)

class BoundaryPerimeter:
    def __init__(self):
        self.boundaryPoints = [] 
        self.perimeterType = None
        self.perimeterGcodeCommands = []

    def __str__(self):
        '''Get the string representation.'''
        output = StringIO.StringIO()
        output.write('\tboundaryPoints: %s\n' % self.boundaryPoints)
        output.write('\tperimeterType: %s\n' % self.perimeterType)
        output.write('\tperimeterGcodeCommands:\n')
        for x in self.perimeterGcodeCommands:
            output.write('\t\t%s\n' % x.str())
        return output.getvalue()
    
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
        
        for x in self.perimeterGcodeCommands:
            if isinstance(x, GcodeCommand):
                output.write('%s\n' % x.str())
            else:
                output.write('%s\n' % x)
        
        return output.getvalue()
