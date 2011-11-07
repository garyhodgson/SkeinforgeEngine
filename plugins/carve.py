"""
Carve is a script to carve a shape into svg slice layers. It creates the perimeter contours

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from fabmetheus_utilities import archive, svg_writer, vector3
import logging
import math

name = 'carve'
logger = logging.getLogger(name)


def performAction(gcode):
	"Get carved text."
	filename = gcode.runtimeParameters.inputFilename
	carving = svg_writer.getCarving(filename)
	if carving == None:
		return
	if config.getboolean(name, 'debug'):
		carvingFilename = filename[: filename.rfind('.')] + '.carving.xml'
		archive.writeFileText(carvingFilename , str(carving))
		logger.info("Carving XML written to %s", carvingFilename)
	CarveSkein(gcode).carve(carving)

class CarveSkein:
	"A class to carve a 3D model."
	
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
				
	def carve(self, carving):
		"Parse 3D model file and store the carved gcode."
		
		carving.setCarveInfillInDirectionOfBridge(self.infillBridgeDirection)
		carving.setCarveLayerThickness(self.layerHeight)
		importRadius = 0.5 * self.importCoarsenessRatio * abs(self.extrusionWidth)
		carving.setCarveImportRadius(max(importRadius, 0.001 * self.layerHeight))
		carving.setCarveIsCorrectMesh(self.correctMesh)
		
		rotatedLoopLayers = carving.getCarveRotatedBoundaryLayers()

		if len(rotatedLoopLayers) < 1:
			logger.warning('There are no slices for the model, this could be because the model is too small for the Layer Thickness.')
			return
		
		self.gcode.carvingCornerMaximum = carving.getCarveCornerMaximum()
		self.gcode.carvingCornerMinimum = carving.getCarveCornerMinimum()
		
		self.gcode.rotatedLoopLayers = rotatedLoopLayers[self.layerPrintFrom : self.layerPrintTo]
				
		if config.getboolean(name, 'debug'):
			filename = self.gcode.runtimeParameters.inputFilename
			svgFilename = filename[: filename.rfind('.')] + '.svg'
			archive.writeFileText(svgFilename , self.gcode.getSVGText())
			logger.info("Carving SVG written to %s", svgFilename)
