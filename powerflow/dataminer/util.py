"""
@author: timon
"""
from pyproj import Geod

import math
import collections.abc

class Geo():

	def compute_length(geometry):

		if not geometry:
			return 0

		lons, lats = zip(*geometry)

		geod = Geod(ellps='WGS84')

		return geod.line_length(lons, lats)


"""
@author: oskar
"""

class Coords:

	def __init__(self, fst, snd=None):

		if snd == None:
			if isinstance(fst, Coords):
				lat = fst.lat
				lon = fst.lon
			elif isinstance(fst, (tuple,list,collections.abc.Iterable)):
				lat, lon = fst
			elif isinstance(fst, complex):
				lat = fst.real
				lon = fst.imag
			else:
				raise ValueError("No longitude passed")
		else:
			lat = fst
			lon = snd

		if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
			raise TypeError("Invalid coordinate types")

		self.lat = lat
		self.lon = lon


	def __repr__(self):
		return f"<{self.lat},{self.lon}>"

	def __iter__(self):
		for i in [self.lat, self.lon]:
			yield i

	def __eq__(self, another):
		if isinstance(another, tuple):
			return (self.lat == another[0]) and (self.lon == another[1])
		else:
			return (self.lat == another.lat) and (self.lon == another.lon)

	def __hash__(self):
		return hash((self.lat, self.lon))

	def __reversed__(self):
		return (self.lon, self.lat)

	def tuple(self):
		return (self.lat, self.lon)

	def radians(self):
		return (math.radians(self.lat),math.radians(self.lon))

	def distance_to(self, another):
		return math.hypot(self.lat - another.lat, self.lon - another.lon)

	def round(self, ndigits=6):
		self.lat = round(self.lat, ndigits)
		self.lon = round(self.lon, ndigits)


import random, string
def generate_id(prefix=''):
	id_length = 20
	alphabet = string.ascii_letters + string.digits
	return prefix + '_' + ''.join(random.choices(alphabet, k=id_length))

class CSV:

	@classmethod
	def escape(cls, text):
		return text.replace(';', '_&_')

	def print_row(self, row):
		print(self.delim.join(row), file=self.f)

	def print_rows(self, rows):
		for row in rows:
			self.print_row(row)

	def __init__(self, filename, header_row=None, delim=';'):

		self.f = open(filename, 'w+')
		self.delim = delim

		if header_row != None:
			self.print_row(header_row)

	def __enter__(self):
		return self

	def __exit__(self, type, value, traceback):
		self.f.close()
