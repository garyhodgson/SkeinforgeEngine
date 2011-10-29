"""
Carve is a script to carve a shape into svg slice layers. It creates the perimeter contours

Original author 
	'Enrique Perez (perez_enrique@yahoo.com) 
	modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
	
license 
	'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

"""

from config import config
from fabmetheus_utilities import archive, svg_writer
import logging
import math

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, gcodeText, gcode):
	"Get carved text."
	carving = svg_writer.getCarving(fileName)
	if carving == None:
		return ''
	if config.getboolean(name, 'debug'):
		carvingFilename = fileName[: fileName.rfind('.')]+'.carving.xml'
		archive.writeFileText( carvingFilename , str(carving) )
		logger.info("Carving XML written to %s", carvingFilename)
	return CarveSkein(gcode).getCarvedSVG(carving, fileName)

class CarveSkein:
	"A class to carve a carving."
	
	def __init__(self, gcode):
		'Initialize'
		self.gcode = gcode
		self.layerHeight = config.getfloat(name, 'layer.height')
		self.extrusionWidth = config.getfloat(name, 'extrusion.width')
		self.infillBridgeDirection = config.getboolean(name, 'infill.bridge.direction')
		self.importCoarsenessRatio = config.getfloat(name, 'import.coarseness.ratio')
		self.correctMesh = config.getboolean(name, 'mesh.correct')
		self.decimalPlaces = config.getint('general', 'decimal.places')
		self.layerPrintFrom = config.getint(name, 'layer.print.from')
		self.layerPrintTo = config.getint(name, 'layer.print.to')
				
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
		
		self.gcode.runtimeParameters.decimalPlaces = self.decimalPlaces
		self.gcode.runtimeParameters.layerThickness = self.layerHeight
		self.gcode.runtimeParameters.perimeterWidth = self.extrusionWidth
	
		svgWriter = svg_writer.SVGWriter(
			True,
			carving.getCarveCornerMaximum(),
			carving.getCarveCornerMinimum(),
			self.decimalPlaces,
			carving.getCarveLayerThickness(),
			self.extrusionWidth)
		
		truncatedLayers = rotatedLoopLayers[self.layerPrintFrom : self.layerPrintTo]
		
		self.gcode.rotatedLoopLayers = truncatedLayers
		
		svgText = svgWriter.getReplacedSVGTemplate(fileName, name, truncatedLayers, carving.getFabmetheusXML())
		
		if config.getboolean(name, 'debug'):
			svgFilename = fileName[: fileName.rfind('.')]+'.svg'
			archive.writeFileText( svgFilename , svgText )
			logger.info("Carving SVG written to %s", svgFilename)
		
		return svgText
