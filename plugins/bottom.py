"""
Bottom sets the bottom of the carving to the defined altitude.
Adjusts the Z heights of each layer.
"""

from fabmetheus_utilities.svg_reader import SVGReader
from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities import archive
from fabmetheus_utilities import gcodec
from fabmetheus_utilities import svg_writer
import os, sys, time, math, logging
from config import config

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, text, gcode):
	"Bottom and convert an svg file or text."
	if not config.getboolean(name,'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return text
	if config.getboolean(name, 'debug'):
		archive.writeFileText( fileName[: fileName.rfind('.')]+'.pre.bottom', text )
	gcodeText = BottomSkein(gcode).getCraftedGcode(fileName, text)
	if config.getboolean(name, 'debug'):
		archive.writeFileText( fileName[: fileName.rfind('.')]+'.post.bottom', gcodeText )
	return gcodeText

class BottomSkein:
	"A class to bottom a skein of extrusions."
	def __init__(self, gcode):
		self.gcode = gcode
		self.additionalHeightRatio = config.getfloat(name,'additional.height.ratio')
		self.altitude = config.getfloat(name,'altitude')
		
		self.layerThickness = config.getfloat('carve', 'layer.height')
		self.perimeterWidth = config.getfloat('carve', 'extrusion.width')
		self.decimalPlaces =  config.getint('general', 'decimal.places')

	def getCraftedGcode(self, fileName, svgText):
		"Parse svgText and store the bottom svgText."
		svgReader = SVGReader()
		svgReader.parseSVG('', svgText)
		if svgReader.sliceDictionary == None:
			logger.warning('Nothing will be done because the sliceDictionary could not be found getCraftedGcode in preface.')
			return ''
		
		# Original
		rotatedLoopLayers = svgReader.rotatedLoopLayers
		zMinimum = 987654321.0
		for rotatedLoopLayer in rotatedLoopLayers:
			zMinimum = min(rotatedLoopLayer.z, zMinimum)
		deltaZ = self.altitude + self.additionalHeightRatio * self.layerThickness - zMinimum
		for rotatedLoopLayer in rotatedLoopLayers:
			rotatedLoopLayer.z += deltaZ
		cornerMaximum = Vector3(-912345678.0, -912345678.0, -912345678.0)
		cornerMinimum = Vector3(912345678.0, 912345678.0, 912345678.0)
		svg_writer.setSVGCarvingCorners(cornerMaximum, cornerMinimum, self.layerThickness, rotatedLoopLayers)
		svgWriter = svg_writer.SVGWriter(
			True,
			cornerMaximum,
			cornerMinimum,
			self.decimalPlaces,
			self.layerThickness,
			self.perimeterWidth)
		commentElement = svg_writer.getCommentElement(svgReader.root)
		procedureNameString = svgReader.sliceDictionary['procedureName'] + ',bottom'
		
		# New
		rotatedLoopLayers = self.gcode.rotatedLoopLayers
		zMinimum = 987654321.0
		for rotatedLoopLayer in rotatedLoopLayers:
			zMinimum = min(rotatedLoopLayer.z, zMinimum)
		deltaZ = self.altitude + self.additionalHeightRatio * self.layerThickness - zMinimum
		for rotatedLoopLayer in rotatedLoopLayers:
			rotatedLoopLayer.z += deltaZ
		
		return svgWriter.getReplacedSVGTemplate(fileName, procedureNameString, rotatedLoopLayers, commentElement)
