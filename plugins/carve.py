"""
Carve is a script to carve a shape into svg slice layers.
It creates the perimeter contours
"""

from fabmetheus_utilities import svg_writer
import math
import logging
from fabmetheus_utilities import archive
from config import config

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, gcodeText=''):
	"Get carved text."
	carving = svg_writer.getCarving(fileName)
	if carving == None:
		return ''
	if config.getboolean(name, 'export.carving'):
		carvingFilename = fileName[: fileName.rfind('.')]+'.carving.xml'
		archive.writeFileText( carvingFilename , str(carving) )
		logger.info("Carving XML written to %s", carvingFilename)
	return CarveSkein().getCarvedSVG(carving, fileName)

class CarveSkein:
	"A class to carve a carving."
	
	def __init__(self):
		'Initialize'
		self.layerHeight = config.getfloat(name, 'layer.height')
		self.extrusionWidth = config.getfloat(name, 'extrusion.width')
		self.infillBridgeDirection = config.getboolean(name, 'infill.bridge.direction')
		self.importCoarsenessRatio = config.getfloat(name, 'import.coarseness.ratio')
		self.correctMesh = config.getboolean(name, 'mesh.correct')
		self.extraDecimalPlaces = config.getfloat(name, 'extra.decimal.places')
		self.layerPrintFrom = config.getint(name, 'layer.print.from')
		self.layerPrintTo = config.getint(name, 'layer.print.to')
		self.exportSvg = config.getboolean(name, 'export.svg')
		
	def getCarvedSVG(self, carving, fileName):
		"Parse gnu triangulated surface text and store the carved gcode."
		carving.setCarveInfillInDirectionOfBridge(self.infillBridgeDirection)
		carving.setCarveLayerThickness(self.layerHeight)
		importRadius = 0.5 * self.importCoarsenessRatio * abs(self.extrusionWidth)
		carving.setCarveImportRadius(max(importRadius, 0.001 * self.layerHeight))
		carving.setCarveIsCorrectMesh(self.correctMesh)
		rotatedLoopLayers = carving.getCarveRotatedBoundaryLayers()
		if len(rotatedLoopLayers) < 1:
			logger.warning('There are no slices for the model, this could be because the model is too small for the Layer Thickness.')
			return ''
		self.layerHeight = carving.getCarveLayerThickness()
		decimalPlacesCarried = max(0, 1 + int(math.ceil(self.extraDecimalPlaces - math.log10(self.layerHeight))))
	
		svgWriter = svg_writer.SVGWriter(
			True,
			carving.getCarveCornerMaximum(),
			carving.getCarveCornerMinimum(),
			decimalPlacesCarried,
			carving.getCarveLayerThickness(),
			self.extrusionWidth)
		
		truncatedLayers = rotatedLoopLayers[self.layerPrintFrom : self.layerPrintTo]
		
		svgText = svgWriter.getReplacedSVGTemplate(fileName, name, truncatedLayers, carving.getFabmetheusXML())
		
		if self.exportSvg:
			svgFilename = fileName[: fileName.rfind('.')]+'.svg'
			archive.writeFileText( svgFilename , svgText )
			logger.info("Carving SVG written to %s", svgFilename)
		
		return svgText
