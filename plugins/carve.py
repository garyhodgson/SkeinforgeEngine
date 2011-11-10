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


def performAction(slicedModel):
	"Get carved text."
	filename = slicedModel.runtimeParameters.inputFilename
	carving = svg_writer.getCarving(filename)
	if carving == None:
		return
	if config.getboolean(name, 'debug'):
		carvingFilename = filename[: filename.rfind('.')] + '.carving.xml'
		archive.writeFileText(carvingFilename , str(carving))
		logger.info("Carving XML written to %s", carvingFilename)
	CarveSkein(slicedModel).carve(carving)

class CarveSkein:
	"A class to carve a 3D model."
	
	def __init__(self, slicedModel):
		'Initialize'
		self.slicedModel = slicedModel
		self.layerHeight = config.getfloat(name, 'layer.height')
		self.extrusionWidth = config.getfloat(name, 'extrusion.width')
		self.infillBridgeDirection = config.getboolean(name, 'infill.bridge.direction')
		self.importCoarsenessRatio = config.getfloat(name, 'import.coarseness.ratio')
		self.correctMesh = config.getboolean(name, 'mesh.correct')
		self.decimalPlaces = config.getint('general', 'decimal.places')
		self.layerPrintFrom = config.getint(name, 'layer.print.from')
		self.layerPrintTo = config.getint(name, 'layer.print.to')
				
	def carve(self, carving):
		"Parse 3D model file and store the carved slicedModel."
		
		carving.setCarveInfillInDirectionOfBridge(self.infillBridgeDirection)
		carving.setCarveLayerThickness(self.layerHeight)
		importRadius = 0.5 * self.importCoarsenessRatio * abs(self.extrusionWidth)
		carving.setCarveImportRadius(max(importRadius, 0.001 * self.layerHeight))
		carving.setCarveIsCorrectMesh(self.correctMesh)
		
		rotatedLoopLayers = carving.getCarveRotatedBoundaryLayers()

		if len(rotatedLoopLayers) < 1:
			logger.warning('There are no slices for the model, this could be because the model is too small for the Layer Thickness.')
			return
		
		self.slicedModel.carvingCornerMaximum = carving.getCarveCornerMaximum()
		self.slicedModel.carvingCornerMinimum = carving.getCarveCornerMinimum()

		toBePrintedLayers = rotatedLoopLayers[self.layerPrintFrom : self.layerPrintTo]
		for toBePrintedLayer in toBePrintedLayers:
			sortedLoops = []
			for toBePrintedLayerLoop in toBePrintedLayer.loops:
				lowerLeftPoint = self.getLowerLeftCorner(toBePrintedLayerLoop)
				lowerLeftIndex = toBePrintedLayerLoop.index(lowerLeftPoint)
				sortedLoops.append(toBePrintedLayerLoop[lowerLeftIndex:] + toBePrintedLayerLoop[:lowerLeftIndex])
			toBePrintedLayer.loops = sortedLoops

		self.slicedModel.rotatedLoopLayers = toBePrintedLayers
				
		if config.getboolean(name, 'debug'):
			filename = self.slicedModel.runtimeParameters.inputFilename
			svgFilename = filename[: filename.rfind('.')] + '.svg'
			svgWriter = svg_writer.SVGWriter(
                                True,
                                self.slicedModel.carvingCornerMaximum,
                                self.slicedModel.carvingCornerMinimum,
                                self.slicedModel.runtimeParameters.decimalPlaces,
                                self.slicedModel.runtimeParameters.layerHeight,
                                self.slicedModel.runtimeParameters.layerThickness)
			archive.writeFileText(svgFilename , svgWriter.getReplacedSVGTemplate(self.slicedModel.runtimeParameters.inputFilename, '', self.slicedModel.rotatedLoopLayers))
			logger.info("Carving SVG written to %s", svgFilename)
			
	def getLowerLeftCorner(self, points):
		'Get the lower left corner point from a set of points.'
		lowerLeftCorner = None
		lowestRealPlusImaginary = 987654321.0
		for point in points:
			realPlusImaginary = point.real + point.imag
			if realPlusImaginary < lowestRealPlusImaginary:
				lowestRealPlusImaginary = realPlusImaginary
				lowerLeftCorner = point
		return lowerLeftCorner
			