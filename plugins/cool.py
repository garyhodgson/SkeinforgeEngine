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
from entities import GcodeCommand
import gcodes
import logging
from importlib import import_module
import os, sys

name = __name__
logger = logging.getLogger(name)

def performAction(slicedModel):
	'Give the extrusion time to cool down.'
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return
	CoolSkein(slicedModel).cool()

class CoolSkein:
	'A class to cool a skein of extrusions.'
	def __init__(self, slicedModel):
		self.slicedModel = slicedModel
		
		self.turnFanOnAtBeginning = config.getboolean(name, 'turn.on.fan.at.beginning')
		self.turnFanOffAtEnding = config.getboolean(name, 'turn.off.fan.at.end')
		self.nameOfCoolStartFile = config.get(name, 'cool.start.file')
		self.nameOfCoolEndFile = config.get(name, 'cool.end.file')
		self.coolStrategyName = config.get(name, 'strategy')
		self.coolStrategyPath = config.get(name, 'strategy.path')
		self.absoluteCoolStartFilePath = os.path.join('alterations', self.nameOfCoolStartFile)
		self.absoluteCoolEndFilePath = os.path.join('alterations', self.nameOfCoolEndFile)
		self.coolStartLines = archive.getTextLines(archive.getFileText(self.absoluteCoolEndFilePath, printWarning=False))
		self.coolEndLines = archive.getTextLines(archive.getFileText(self.absoluteCoolEndFilePath, printWarning=False))
		
	def cool(self):
		'Apply the cool strategy.'
		
		if self.turnFanOnAtBeginning:
			self.slicedModel.startGcodeCommands.append(GcodeCommand(gcodes.TURN_FAN_ON))
		
		coolStrategy = None
		try:
			if self.coolStrategyPath not in sys.path:
				sys.path.insert(0, self.coolStrategyPath)
			coolStrategy = import_module(self.coolStrategyName).getStrategy(self.slicedModel.runtimeParameters)
			logger.info("Using cool strategy: %s", self.coolStrategyName)
		except ImportError as inst:
			logger.warning("Could not find module for cooling strategy called: %s. %s", self.coolStrategyName, inst)	
		except Exception as inst:
			logger.warning("Exception reading strategy %s: %s", self.coolStrategyName, inst)
		
		for layer in self.slicedModel.layers.values():
			for line in self.coolStartLines:
				layer.preLayerGcodeCommands.append(line)
	            
			if coolStrategy != None:
				coolStrategy.cool(layer)
				
			for line in self.coolEndLines:
				layer.postLayerGcodeCommands.append(line)

		if self.turnFanOffAtEnding:
			self.slicedModel.endGcodeCommands.append(GcodeCommand(gcodes.TURN_FAN_OFF))
