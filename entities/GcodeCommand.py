from collections import OrderedDict
from config import config
from fabmetheus_utilities import archive, svg_writer, euclidean
from fabmetheus_utilities.vector3 import Vector3
from math import log10, floor, pi
from utilities import memory_tracker
from StringIO import StringIO
import gcodes
import math
import sys
import time

class GcodeCommand:
    def __init__(self, commandLetter, parameters=None):
        self.commandLetter = commandLetter
        if parameters == None:
            parameters = {}
        self.parameters = OrderedDict(parameters)
    
    def __str__(self):
        return self.str(False) 
    
    def str(self, verbose=False):
        '''Get the string representation.'''
        output = StringIO()
        output.write('%s ' % (self.commandLetter[0]))
        for name, value in self.parameters.items():
            output.write('%s%s ' % (name, value))
        if (verbose):
            output.write(';%20s ' % (self.commandLetter[1]))
        return output.getvalue().strip()


    @staticmethod
    def printCommand(command, verbose=False):
        if command == None:
            return 
        if isinstance(command, GcodeCommand):
            return'%s\n' % command.str(verbose)
        else:
            return '%s\n' % command