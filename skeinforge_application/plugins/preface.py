"""
Preface converts the svg slices into gcode extrusion layers, optionally prefaced with some gcode commands.
"""

from fabmetheus_utilities.svg_reader import SVGReader
from fabmetheus_utilities import archive
from fabmetheus_utilities import gcodec
from time import strftime
import os
import sys
from config import config
import logging

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, text=''):
	"Preface and convert an svg file or text."
	text = archive.getTextIfEmpty(fileName, text)
	if gcodec.isProcedureDoneOrFileIsEmpty(text, 'preface'):
		return text
	return PrefaceSkein().getCraftedGcode(text)

class PrefaceSkein:
	"A class to preface a skein of extrusions."
	def __init__(self):
		self.gcode = gcodec.Gcode()
		self.extruderActive = False
		self.lineIndex = 0
		self.oldLocation = None
		self.svgReader = SVGReader()
		self.setPositioningToAbsolute = config.getboolean('preface','positioning.absolute')
		self.setUnitsToMillimeters = config.getboolean('preface','units.millimeters')
		self.startAtHome = config.getboolean('preface','startup.at.home')
		self.resetExtruder = config.getboolean('preface','startup.extruder.reset')
		self.setPositioningToAbsolute = config.getboolean('preface','positioning.absolute')

	def addFromUpperLowerFile(self, fileName):
		"Add lines of text from the fileName or the lowercase fileName, if there is no file by the original fileName in the directory."
		absoluteFilePath = os.path.join('alterations',  fileName)
		fileText = archive.getFileText(absoluteFilePath)
		self.gcode.addLinesSetAbsoluteDistanceMode(archive.getTextLines(fileText))

	def addInitializationToOutput(self):
		"Add initialization gcode to the output."
		self.addFromUpperLowerFile(config.get('preface','start.file')) # Add a start file if it exists.
		self.gcode.addTagBracketedLine('creation', 'skeinforge') # GCode formatted comment

		self.gcode.addLine('(<extruderInitialization>)') # GCode formatted comment
		if self.setPositioningToAbsolute:
			self.gcode.addLine('G90 ;set positioning to absolute') # Set positioning to absolute.
		if self.setUnitsToMillimeters:
			self.gcode.addLine('G21 ;set units to millimeters') # Set units to millimeters.
		if self.startAtHome:
			self.gcode.addLine('G28 ;start at home') # Start at home.
		if self.resetExtruder:
			self.gcode.addLine('G92 E0 ;reset extruder distance') # Start at home.

		
		self.gcode.addTagBracketedLine('craftTypeName', 'extrusion')
		self.gcode.addTagBracketedLine('decimalPlacesCarried', self.gcode.decimalPlacesCarried)
		layerThickness = float(self.svgReader.sliceDictionary['layerThickness'])
		self.gcode.addTagRoundedLine('layerThickness', layerThickness)
		perimeterWidth = float(self.svgReader.sliceDictionary['perimeterWidth'])
		self.gcode.addTagRoundedLine('perimeterWidth', perimeterWidth)
		self.gcode.addTagBracketedLine('profileName', 'Default')
		self.gcode.addLine('(<settings>)')
		self.gcode.addLine('(</settings>)')
		self.gcode.addTagBracketedLine('timeStampPreface', strftime('%Y%m%d_%H%M%S'))
		procedureNames = self.svgReader.sliceDictionary['procedureName'].replace(',', ' ').split()
		for procedureName in procedureNames:
			self.gcode.addTagBracketedLine('procedureName', procedureName)
		self.gcode.addTagBracketedLine('procedureName', 'preface')
		self.gcode.addLine('(</extruderInitialization>)') # Initialization is finished, extrusion is starting.
		self.gcode.addLine('(<crafting>)') # Initialization is finished, crafting is starting.

	def addPreface(self, rotatedLoopLayer):
		"Add preface to the carve layer."
		self.gcode.addLine('(<layer> %s )' % rotatedLoopLayer.z) # Indicate that a new layer is starting.
		if rotatedLoopLayer.rotation != None:
			self.gcode.addTagBracketedLine('bridgeRotation', str(rotatedLoopLayer.rotation)) # Indicate the bridge rotation.
		for loop in rotatedLoopLayer.loops:
			self.gcode.addGcodeFromLoop(loop, rotatedLoopLayer.z)
		self.gcode.addLine('(</layer>)')

	def addShutdownToOutput(self):
		"Add shutdown gcode to the output."
		self.gcode.addLine('(</crafting>)') # GCode formatted comment
		self.addFromUpperLowerFile(config.get('preface','end.file')) # Add an end file if it exists.

	def getCraftedGcode(self, gcodeText):
		"Parse gcode text and store the bevel gcode."
		
		self.svgReader.parseSVG('', gcodeText)
		if self.svgReader.sliceDictionary == None:
			logger.warning('Nothing will be done because the sliceDictionary could not be found getCraftedGcode in preface.')
			return ''
		self.gcode.decimalPlacesCarried = int(self.svgReader.sliceDictionary['decimalPlacesCarried'])
		self.addInitializationToOutput()
		for rotatedLoopLayerIndex, rotatedLoopLayer in enumerate(self.svgReader.rotatedLoopLayers):
			logger.info('layer: %s/%s', rotatedLoopLayerIndex+1, len(self.svgReader.rotatedLoopLayers))
			self.addPreface(rotatedLoopLayer)
		self.addShutdownToOutput()
		return self.gcode.output.getvalue()
