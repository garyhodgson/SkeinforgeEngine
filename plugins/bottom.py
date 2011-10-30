"""
Bottom sets the bottom of the carving to the defined altitude. Adjusts the Z heights of each layer.

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from fabmetheus_utilities import archive
import os, sys, time, math, logging
from config import config

logger = logging.getLogger(__name__)
name = __name__

def performAction(gcode):
	"Align the model to the bottom of the printing plane"
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return
	BottomSkein(gcode).bottom()
	
class BottomSkein:
	"A class to bottom a skein of extrusions."
	def __init__(self, gcode):
		self.gcode = gcode
		self.additionalHeightRatio = config.getfloat(name, 'additional.height.ratio')
		self.altitude = config.getfloat(name, 'altitude')
		self.layerThickness = config.getfloat('carve', 'layer.height')
		self.perimeterWidth = config.getfloat('carve', 'extrusion.width')
		self.decimalPlaces = config.getint('general', 'decimal.places')

	def bottom(self):
		"Parse svgText and store the bottom svgText."
		
		fileName = self.gcode.runtimeParameters.inputFilename
		svgText = self.gcode.svgText
				
		rotatedLoopLayers = self.gcode.rotatedLoopLayers
		
		zMinimum = 987654321.0
		for rotatedLoopLayer in rotatedLoopLayers:
			zMinimum = min(rotatedLoopLayer.z, zMinimum)
		deltaZ = self.altitude + self.additionalHeightRatio * self.layerThickness - zMinimum
		
		for rotatedLoopLayer in rotatedLoopLayers:
			rotatedLoopLayer.z += deltaZ
		
		if config.getboolean(name, 'debug'):
			filename = self.gcode.runtimeParameters.inputFilename
			svgFilename = filename[: filename.rfind('.')] + '.bottom.svg'
			archive.writeFileText(svgFilename , self.gcode.getSVGText())
			logger.info("Bottom SVG written to %s", svgFilename)

