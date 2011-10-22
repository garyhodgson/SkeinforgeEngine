"""
Bottom sets the bottom of the carving to the defined altitude.
Adjusts the Z heights of each layer.
"""

from fabmetheus_utilities.svg_reader import SVGReader
from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities import archive
from fabmetheus_utilities import gcodec
from fabmetheus_utilities import svg_writer
import os
import sys
import time
import math
from config import config
import logging

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, svgText=''):
	"Bottom and convert an svg file or svgText."
	svgText = archive.getTextIfEmpty(fileName, svgText)
	if gcodec.isProcedureDoneOrFileIsEmpty(svgText, name):
		return svgText
	if not config.getboolean(name,'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return svgText
	return BottomSkein().getCraftedGcode(fileName, svgText)

class BottomSkein:
	"A class to bottom a skein of extrusions."
	def __init__(self):
		self.additionalHeightOverLayerThickness = config.getfloat(name,'additional.height.ratio')
		self.altitude = config.getfloat(name,'altitude')

	def getCraftedGcode(self, fileName, svgText):
		"Parse svgText and store the bottom svgText."
		svgReader = SVGReader()
		svgReader.parseSVG('', svgText)
		if svgReader.sliceDictionary == None:
			logger.warning('Nothing will be done because the sliceDictionary could not be found getCraftedGcode in preface.')
			return ''
		layerThickness = config.getfloat('carve', 'layer.height')
		perimeterWidth = config.getfloat('carve', 'extrusion.width')
		extraDecimalPlaces = config.getfloat('carve', 'extra.decimal.places')
		decimalPlacesCarried = max(0, 1 + int(math.ceil(extraDecimalPlaces - math.log10(layerThickness))))
		
		rotatedLoopLayers = svgReader.rotatedLoopLayers
		zMinimum = 987654321.0
		for rotatedLoopLayer in rotatedLoopLayers:
			zMinimum = min(rotatedLoopLayer.z, zMinimum)
		deltaZ = self.altitude + self.additionalHeightOverLayerThickness * layerThickness - zMinimum
		for rotatedLoopLayer in rotatedLoopLayers:
			rotatedLoopLayer.z += deltaZ
		cornerMaximum = Vector3(-912345678.0, -912345678.0, -912345678.0)
		cornerMinimum = Vector3(912345678.0, 912345678.0, 912345678.0)
		svg_writer.setSVGCarvingCorners(cornerMaximum, cornerMinimum, layerThickness, rotatedLoopLayers)
		svgWriter = svg_writer.SVGWriter(
			True,
			cornerMaximum,
			cornerMinimum,
			decimalPlacesCarried,
			layerThickness,
			perimeterWidth)
		commentElement = svg_writer.getCommentElement(svgReader.root)
		procedureNameString = svgReader.sliceDictionary['procedureName'] + ',bottom'
		return svgWriter.getReplacedSVGTemplate(fileName, procedureNameString, rotatedLoopLayers, commentElement)
