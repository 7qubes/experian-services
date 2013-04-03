import logging
import json
from google.appengine.api import urlfetch
from google.appengine.api import memcache
import urllib
import base64
import hashlib
import hmac
import webapp2
import datetime

# Import local modules
from controllers import utils
from controllers import datastore

class DSStub(utils.BaseHandler):
	def get(self):

		# Save a vehicle
		datastore.set_vehicle(**dict(
			make='Volkswagen',
			model='Golf',
			door_plan='13',
			year_of_manufacture='2013'			
		))

		# Then query results
		response = datastore.get_vehicle(**dict(
			make='Volkswagen',
			model='Golf'
		))

		# And log it
		logging.info(response)