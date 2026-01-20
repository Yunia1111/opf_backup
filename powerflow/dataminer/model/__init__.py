from enum import Enum

import numpy as np
from scipy.spatial import KDTree
EARTH_RADIUS = 6371000

from .. import util
Coords = util.Coords




class NodeType(Enum):
	UNDEF = 0
	BUS = 1
	BRANCH = 2
	SUBSTATION = 3

class ConnType(Enum):
	UNDEF = 0
	LINE = 1
	CABLE = 2
	HVDC_LINE = 3
	HVDC_CABLE = 4

class EndType(Enum):
	UNDEF = 0
	START = 1
	END = 2

	def __repr__(self):
		return str(self)




class FilteredItem(Exception):
	pass

class DoesNotExistError(Exception):
	pass

class NoVoltageError(ValueError):
	pass




from .connection import *
from .node import *

from .generator import *
from .load import *
