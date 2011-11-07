"""
Cool is a script to cool the shape.

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from fabmetheus_utilities import archive, euclidean, intercircle
from gcode import GcodeCommand
import gcodes
import logging
from importlib import import_module
import os, sys

name = __name__
logger = logging.getLogger(name)

def performAction(gcode):
	'Cool a gcode linear move text.'
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return
	CoolSkein(gcode).cool()

class CoolSkein:
	'A class to cool a skein of extrusions.'
	def __init__(self, gcode):
		self.gcode = gcode
		
		self.turnFanOnAtBeginning = config.getboolean(name, 'turn.on.fan.at.beginning')
		self.turnFanOffAtEnding = config.getboolean(name, 'turn.off.fan.at.end')
		self.nameOfCoolStartFile = config.get(name, 'cool.start.file')
		self.nameOfCoolEndFile = config.get(name, 'cool.end.file')
		self.coolStrategyName = config.get(name, 'cool.strategy')
		self.coolStrategyPath = config.get(name, 'cool.strategy.path')
		self.absoluteCoolStartFilePath = os.path.join(archive.getSkeinforgePath('alterations'), self.nameOfCoolStartFile)
		self.absoluteCoolEndFilePath = os.path.join(archive.getSkeinforgePath('alterations'), self.nameOfCoolEndFile)
		self.coolStartLines = archive.getFileText(self.absoluteCoolEndFilePath, printWarning=False)
		self.coolEndLines = archive.getFileText(self.absoluteCoolEndFilePath, printWarning=False)
		
	def cool(self):
		'Parse gcode text and store the cool gcode.'
		
		if self.turnFanOnAtBeginning:
			self.gcode.startGcodeCommands.append(GcodeCommand(gcodes.TURN_FAN_ON))
		
		coolStrategy = None
		try:
			sys.path.insert(0, self.coolStrategyPath)
			coolStrategy = import_module(self.coolStrategyName)
		except:
			logger.warning("Could not find module for cooling strategy called: %s", self.coolStrategyName)
		
		for layer in self.gcode.layers.values():
			for line in self.coolStartLines:
				layer.preLayerGcodeCommands.append(line)
	            
			if coolStrategy != None:
				coolStrategy.cool(layer, self.gcode.runtimeParameters, dict(config.items(name)))
				
			for line in self.coolEndLines:
				layer.postLayerGcodeCommands.append(line)

		if self.turnFanOffAtEnding:
			self.gcode.endGcodeCommands.append(GcodeCommand(gcodes.TURN_FAN_OFF))
