"""
Preface creates the nested ring structure from the rotated layers, and adds optional start and end gcodes.

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from fabmetheus_utilities import euclidean, archive
from gcode import GcodeCommand, Layer, BoundaryPerimeter, NestedRing
from time import strftime
import gcodes
import logging
import os


logger = logging.getLogger(__name__)
name = __name__

def performAction(gcode):
	"Preface and converts the layers."
	PrefaceSkein(gcode).preface()

class PrefaceSkein:
	"A class to preface a skein of extrusions."
	def __init__(self, gcode):
		self.gcode = gcode
		self.setPositioningToAbsolute = config.getboolean(name, 'positioning.absolute')
		self.setUnitsToMillimeters = config.getboolean(name, 'units.millimeters')
		self.startAtHome = config.getboolean(name, 'startup.at.home')
		self.resetExtruder = config.getboolean(name, 'startup.extruder.reset')
		self.endFile = config.get(name, 'end.file')
		self.startFile = config.get(name, 'start.file')
		
	def preface(self):
		"Prefaces and converts the svg text to Gcode."
		
		self.addStartCommandsToGcode()
		
		for (index, rotatedLoopLayer) in enumerate(self.gcode.rotatedLoopLayers):
			self.addPrefaceToGcode(index, rotatedLoopLayer)
		
		self.addEndCommandsToGcode()		
	
	
	def addPrefaceToGcode(self, index, rotatedLoopLayer):
		decimalPlaces = self.gcode.runtimeParameters.decimalPlaces
		z = round(rotatedLoopLayer.z, 3)
		layer = Layer(z, index, self.gcode.runtimeParameters)		
		

		if rotatedLoopLayer.rotation != None:
			layer.bridgeRotation = complex(rotatedLoopLayer.rotation)
		
		loops = rotatedLoopLayer.loops
		internalLoops = self.createLoopHierarchy(loops)
		
		nestRingPlaceholder = {}
		for loop in loops:
			nestedRing = NestedRing(z, self.gcode.runtimeParameters)
			nestedRing.setBoundaryPerimeter(loop)
			nestRingPlaceholder[str(loop)] = nestedRing 
		
		for internalLoop in internalLoops:
			parent = internalLoops[internalLoop]
			child = loops[internalLoop]
			childNestedRing = nestRingPlaceholder[str(loops[internalLoop])]
			
			if parent == None:
				layer.addNestedRing(childNestedRing)
			else:
				parentNestedRing = nestRingPlaceholder[str(internalLoops[internalLoop])]
				parentNestedRing.innerNestedRings.append(childNestedRing)
				 
		self.gcode.layers[z] = layer

	def createLoopHierarchy(self, loops):
		internalLoops = {}
		
		for (loopIndex, loop) in enumerate(loops):
			internalLoops[loopIndex] = []
			otherLoops = []
			for beforeIndex in xrange(loopIndex):
				otherLoops.append(loops[beforeIndex])
			for afterIndex in xrange(loopIndex + 1, len(loops)):
				otherLoops.append(loops[afterIndex])
			internalLoops[loopIndex] = euclidean.getClosestEnclosingLoop(otherLoops, loop)
		return internalLoops
	
	def addStartCommandsToGcode(self):		
		if config.get(name, 'start.file') != None:
			for line in archive.getLinesFromAlterationsFile(self.startFile):
				self.gcode.startGcodeCommands.append(line)
		
		if self.setPositioningToAbsolute:
			self.gcode.startGcodeCommands.append(GcodeCommand(gcodes.ABSOLUTE_POSITIONING))
		if self.setUnitsToMillimeters:
			self.gcode.startGcodeCommands.append(GcodeCommand(gcodes.UNITS_IN_MILLIMETERS))
		if self.startAtHome:
			self.gcode.startGcodeCommands.append(GcodeCommand(gcodes.START_AT_HOME))
		if self.resetExtruder:
			self.gcode.startGcodeCommands.append(GcodeCommand(gcodes.RESET_EXTRUDER_DISTANCE, [('E', '0')]))
		
	def addEndCommandsToGcode(self):
		if config.get(name, 'end.file') != None:
			for line in archive.getLinesFromAlterationsFile(self.endFile):
				self.gcode.endGcodeCommands.append(line)

