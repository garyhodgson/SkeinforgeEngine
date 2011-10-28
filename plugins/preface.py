"""
Preface converts the svg slices into gcodecGcode extrusion layers, optionally prefaced with some gcodecGcode commands.
"""

from config import config
from decimal import *
from fabmetheus_utilities import archive, euclidean, gcodec
from fabmetheus_utilities.svg_reader import SVGReader
from fabmetheus_utilities.vector3 import Vector3
from gcode import GcodeCommand, Layer, BoundaryPerimeter, NestedRing
from time import strftime
import gcodes
import logging
import os
import sys

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, text, gcode):
	"Preface and convert an svg file or text."
	if config.getboolean(name, 'debug'):
		archive.writeFileText(fileName[: fileName.rfind('.')] + '.pre.preface', text)
	craftedGcodeText = PrefaceSkein(gcode).getCraftedGcode(text)
	if config.getboolean(name, 'debug'):
		archive.writeFileText(fileName[: fileName.rfind('.')] + '.post.preface', craftedGcodeText)
	return craftedGcodeText

class PrefaceSkein:
	"A class to preface a skein of extrusions."
	def __init__(self, gcode):
		self.gcodecGcode = gcodec.Gcode()
		self.gcode = gcode
		self.extruderActive = False
		self.lineIndex = 0
		self.oldLocation = None
		self.svgReader = SVGReader()
		self.setPositioningToAbsolute = config.getboolean('preface', 'positioning.absolute')
		self.setUnitsToMillimeters = config.getboolean('preface', 'units.millimeters')
		self.startAtHome = config.getboolean('preface', 'startup.at.home')
		self.resetExtruder = config.getboolean('preface', 'startup.extruder.reset')
		self.setPositioningToAbsolute = config.getboolean('preface', 'positioning.absolute')

	def addFromUpperLowerFile(self, fileName):
		"Add lines of text from the fileName or the lowercase fileName, if there is no file by the original fileName in the directory."
		absoluteFilePath = os.path.join('alterations', fileName)
		fileText = archive.getFileText(absoluteFilePath)
		self.gcodecGcode.addLinesSetAbsoluteDistanceMode(archive.getTextLines(fileText))

	def getLinesFromFile(self, fileName):
		lines = []
		absPath = os.path.join('alterations', fileName)
		try:			
			f = open(absPath, 'r')
			lines = f.read().replace('\r', '\n').replace('\n\n', '\n').split('\n')
			f.close()
		except IOError as e:
			logger.warning("Unable to open file: %s", absPath)
		return lines
	
	def addInitializationToOutput(self):
		"Add initialization gcodecGcode to the output."
		self.addFromUpperLowerFile(config.get('preface', 'start.file')) # Add a start file if it exists.
		self.gcodecGcode.addTagBracketedLine('creation', 'skeinforge') # GCode formatted comment

		self.gcodecGcode.addLine('(<extruderInitialization>)') # GCode formatted comment
		if self.setPositioningToAbsolute:
			self.gcodecGcode.addLine('G90 ;set positioning to absolute') # Set positioning to absolute.
		if self.setUnitsToMillimeters:
			self.gcodecGcode.addLine('G21 ;set units to millimeters') # Set units to millimeters.
		if self.startAtHome:
			self.gcodecGcode.addLine('G28 ;start at home') # Start at home.
		if self.resetExtruder:
			self.gcodecGcode.addLine('G92 E0 ;reset extruder distance') # Start at home.

		
		self.gcodecGcode.addTagBracketedLine('craftTypeName', 'extrusion')
		self.gcodecGcode.addTagBracketedLine('decimalPlacesCarried', self.gcodecGcode.decimalPlacesCarried)
		layerThickness = float(self.svgReader.sliceDictionary['layerThickness'])
		self.gcodecGcode.addTagRoundedLine('layerThickness', layerThickness)
		perimeterWidth = float(self.svgReader.sliceDictionary['perimeterWidth'])
		self.gcodecGcode.addTagRoundedLine('perimeterWidth', perimeterWidth)
		self.gcodecGcode.addTagBracketedLine('profileName', 'Default')
		self.gcodecGcode.addLine('(<settings>)')
		self.gcodecGcode.addLine('(</settings>)')
		self.gcodecGcode.addTagBracketedLine('timeStampPreface', strftime('%Y%m%d_%H%M%S'))
		procedureNames = self.svgReader.sliceDictionary['procedureName'].replace(',', ' ').split()
		for procedureName in procedureNames:
			self.gcodecGcode.addTagBracketedLine('procedureName', procedureName)
		self.gcodecGcode.addTagBracketedLine('procedureName', 'preface')
		self.gcodecGcode.addLine('(</extruderInitialization>)') # Initialization is finished, extrusion is starting.
		self.gcodecGcode.addLine('(<crafting>)') # Initialization is finished, crafting is starting.

	def addPreface(self, rotatedLoopLayer):
		"Add preface to the carve layer."
		self.gcodecGcode.addLine('(<layer> %s )' % rotatedLoopLayer.z) # Indicate that a new layer is starting.
		if rotatedLoopLayer.rotation != None:
			self.gcodecGcode.addTagBracketedLine('bridgeRotation', str(rotatedLoopLayer.rotation)) # Indicate the bridge rotation.
		for loop in rotatedLoopLayer.loops:
			self.gcodecGcode.addGcodeFromLoop(loop, rotatedLoopLayer.z)
		self.gcodecGcode.addLine('(</layer>)')
	
	def addPrefaceToGcode(self, rotatedLoopLayer):
		z = rotatedLoopLayer.z
		layer = Layer(z, self.gcode)
		
		decimalPlaces = self.gcode.runtimeParameters.decimalPlaces

		if rotatedLoopLayer.rotation != None:
			layer.bridgeRotation = complex(rotatedLoopLayer.rotation)
			
		for loop in rotatedLoopLayer.loops:
			nestedRing = NestedRing(layer)
			nestedRing.addBoundaryPerimeter(loop)
			layer.addNestedRing(nestedRing)
		
		self.gcode.layers[z] = layer

	def addShutdownToOutput(self):
		"Add shutdown gcodecGcode to the output."
		self.gcodecGcode.addLine('(</crafting>)') # GCode formatted comment
		self.addFromUpperLowerFile(config.get('preface', 'end.file')) # Add an end file if it exists.
		
	def addStartCommandsToGcode(self):
		
		if config.get(name, 'start.file') != None:
			for line in self.getLinesFromFile(config.get(name, 'start.file')):
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
			for line in self.getLinesFromFile(config.get(name, 'end.file')):
				self.gcode.endGcodeCommands.append(line)
				
	def getCraftedGcode(self, gcodeText):
		"Parse gcodecGcode text and store the bevel gcodecGcode."
		
		self.svgReader.parseSVG('', gcodeText)
		if self.svgReader.sliceDictionary == None:
			logger.warning('Nothing will be done because the sliceDictionary could not be found getCraftedGcode in preface.')
			return ''
		
		self.gcodecGcode.decimalPlacesCarried = self.gcode.runtimeParameters.decimalPlaces
		self.addInitializationToOutput()
		
		self.addStartCommandsToGcode()
		
		for rotatedLoopLayerIndex, rotatedLoopLayer in enumerate(self.svgReader.rotatedLoopLayers):
			self.addPreface(rotatedLoopLayer)
		
		for rotatedLoopLayer in self.gcode.rotatedLoopLayers:
			self.addPrefaceToGcode(rotatedLoopLayer)
		
		self.addShutdownToOutput()
		self.addEndCommandsToGcode()
		
		return self.gcodecGcode.output.getvalue()
