import logging
import json
from google.appengine.api import urlfetch
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import users
import urllib
import base64
import hashlib
import hmac
import webapp2
import datetime

# Import local modules
from controllers import utils
from models import models

class RicabilityVehicleCollection(utils.BaseHandler):
	def process(self):
		try:
			# Check for App Engine CRON Header or System Admin access
			if not self.request.headers.has_key('X-Appengine-Cron'):
				
				# Else check for System Admin access
				is_system_admin = users.is_current_user_admin()
				
				if not is_system_admin:
					logging.warning('WARNING: Illegal access to CRON job by user')
					user = users.get_current_user()
					if user is not None:
						logging.warning('User nickname : '+str(user.nickname()))
						logging.warning('User email : '+str(user.email()))
						logging.warning('User ID : '+str(user.user_id()))
					# Return immediately and do not run the tasks
					return False
			
			# Kick off the tasks for collecting vehicles
			for make, model_obj in models.ricability_vehicles.items():
				for vehicle_id, vehicle_description in model_obj.items():
					taskqueue.add(
						queue_name='vehiclecollection',
						url='/tasks/ricability-vehicle-collection',
						params={
							'vehicle_id':vehicle_id,
							'vehicle_description':vehicle_description
						}
					)
			
			return True

		except Exception, e:
			raise e		

	def get(self):
		self.process()
	def post(self):
		self.process()