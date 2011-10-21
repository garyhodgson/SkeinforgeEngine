"""
Carve is a script to carve a shape into svg slice layers.
It creates the perimeter contours
"""

from fabmetheus_utilities import svg_writer
import math
import logging
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
	return CarveSkein().getCarvedSVG(carving, fileName)

class CarveSkein:
	"A class to carve a carving."
	def getCarvedSVG(self, carving, fileName):
		"Parse gnu triangulated surface text and store the carved gcode."
		layerThickness = config.getfloat(name, 'layer.height')
		perimeterWidth = config.getfloat(name, 'extrusion.width')
		carving.setCarveInfillInDirectionOfBridge(config.getboolean('carve', 'infill.bridge.direction'))
		carving.setCarveLayerThickness(layerThickness)
		importRadius = 0.5 * config.getfloat(name, 'import.coarseness.ratio') * abs(perimeterWidth)
		carving.setCarveImportRadius(max(importRadius, 0.001 * layerThickness))
		carving.setCarveIsCorrectMesh(config.getboolean(name, 'mesh.correct'))
		rotatedLoopLayers = carving.getCarveRotatedBoundaryLayers()
		if len(rotatedLoopLayers) < 1:
			logger.warning('There are no slices for the model, this could be because the model is too small for the Layer Thickness.')
			return ''
		layerThickness = carving.getCarveLayerThickness()
		extraDecimalPlaces = config.getfloat(name, 'extra.decimal.places')
		decimalPlacesCarried = max(0, 1 + int(math.ceil(extraDecimalPlaces - math.log10(layerThickness))))
	
		svgWriter = svg_writer.SVGWriter(
			True,
			carving.getCarveCornerMaximum(),
			carving.getCarveCornerMinimum(),
			decimalPlacesCarried,
			carving.getCarveLayerThickness(),
			perimeterWidth)
		
		truncatedRotatedBoundaryLayers = svg_writer.getTruncatedRotatedBoundaryLayers(rotatedLoopLayers,
																					config.getint(name, 'layer.print.from'),
																					config.getint(name, 'layer.print.to'))
		
		return svgWriter.getReplacedSVGTemplate(
			fileName, name, truncatedRotatedBoundaryLayers, carving.getFabmetheusXML())
