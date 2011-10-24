import StringIO, time
from collections import OrderedDict
from config import config

class Gcode:
    '''Runtime data for conversion of 3D model to gcode.'''
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.runtimeParameters = RuntimeParameters()
        self.rotatedLoopLayers = []
        self.layers = []
        
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
        for x in self.layers:
            output.write('%s\n' % x)
        
        return output.getvalue()
    
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
        
        for x in self.startGcodeCommands:
            if isinstance(x, GcodeCommand):
                output.write('%s\n' % x.str(self.verbose))
            else:
                output.write('%s\n' % x)

        for x in self.layers:
            output.write('%s' % x.getGcodeText())

        for x in self.endGcodeCommands:
            if isinstance(x, GcodeCommand):
                output.write('%s\n' % x.str(self.verbose))
            else:
                output.write('%s\n' % x)
                        
        return output.getvalue()

class RuntimeParameters:
    def __init__(self):
        self.startTime = time.time()
        self.decimalPlacesCarried = 5
        self.layerThickness = 0.4
        self.perimeterWidth = 0.6
        self.profileName = ''
        self.endTime = None

class GcodeCommand:
    def __init__(self, commandLetter, parameters={}):
        self.commandLetter = commandLetter
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
        return output.getvalue()

class Layer:
    def __init__(self, z):
        self.z = z
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
            output.write('%s' % x)
            
        output.write('loops: %s\n, ' % self.loops)
        output.write('gcodeCommands: %s' % self.gcodeCommands)
        return output.getvalue()
    
    def getGcodeText(self):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()
        
        for x in self.boundaryPerimeters:
            output.write('%s\n' % x.getGcodeText())
        
        return output.getvalue()

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
