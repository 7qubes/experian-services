from google.appengine.ext import db
from google.appengine.api.datastore import Key
from google.appengine.api import memcache
import logging
import os
import time
import cgi
import datetime
import random
import re

# Import local scripts
from models import models
from controllers import utils

"""
	@name: get_vehicle
	@description:
		Gets an individual vehicle based on kwargs.

		The make and model arguments are 'hard' filters; if either of these do not return at least one Vehicle model instance,
		we throw an Exception

		The door_plan_literal and year_of_manufacture arguments are 'soft' filters; if either of these do not match additional
		db.Query filters, we revert to a previous db.Query where we had a make and model match. We then update a 'matches' dictionary 
		object with a flag to show what arguments have been matched, and therefore credibility of the Vehicle query results

	@kwargs:
		make
		model
		year_of_manufacture
		door_plan
		door_plan_literal
"""
def get_vehicle(**kwargs):
	response = None
	try:
		logging.info(kwargs)
		memcache_key = utils.create_memcache_key('vehicle', **kwargs)
		memcache_result = memcache.get(memcache_key)

		# [ST]TODO: Remove after debugging
		memcache_result = None

		if memcache_result is not None:
			response = memcache_result
		else:
			make = kwargs.get('make')
			model = kwargs.get('model')
			door_plan_literal = kwargs.get('door_plan_literal')

			# Check for essential arguments
			if make is None:
				raise Exception('No make provided')
			if model is None:
				raise Exception('No model provided')
			if door_plan_literal is None:
				raise Exception('No door_plan_literal provided')

			# Create an empty doctionary for successful Query matches
			matches = dict()

			# Query all Vehicles by Make and check for at least one match
			query = models.Vehicle.all().filter('make = ', kwargs.get('make'))
			if query.get() is not None:
				matches['make'] = True

				# Using the same Query, filter all Vehicles additionally by Model and check for at least one match
				query = query.filter('model = ', kwargs.get('model'))
				if query.get() is not None:
					matches['model'] = True

					# Create a new Query for all Vehicles by Make, Model and Door Plan Literal
					query_door_plan = models.Vehicle.all().filter('make = ', kwargs.get('make')).filter('model = ', kwargs.get('model')).filter('door_plan_literal = ', kwargs.get('door_plan_literal'))
					if query_door_plan.get() is not None:
						query = query_door_plan
						matches['door_plan_literal'] = True

						# Create a new Query for all Vehicles by Make, Model, Door Plan Literal and Year Of Manufacture
						query_yom = models.Vehicle.all().filter('make = ', kwargs.get('make')).filter('model = ', kwargs.get('model')).filter('door_plan_literal = ', kwargs.get('door_plan_literal')).filter('year_of_manufacture = ', kwargs.get('year_of_manufacture'))
						if query_yom.get() is not None:
							query = query_yom
							matches['year_of_manufacture'] = True
						else:
							query = query
							matches['year_of_manufacture'] = False	
					else:
						query = query
						matches['door_plan_literal'] = False
				else:
					logging.exception('No model found in datastore with name '+model)
					raise Exception('No model found in datastore with name '+model)
			else:
				logging.exception('No make found in datastore with name '+make)
				raise Exception('No make found in datastore with name '+make)

			# Order the Query by Year Of Manufacture by default, in descending order
			query.order('-year_of_manufacture')
			
			# Get the first query item
			vehicle = query.get()

			# If we have a Vehicle
			if vehicle is not None:
				# Convert the Model instance to a dictionary
				response = db.to_dict(vehicle, dict(key_name=vehicle.key().name() or vehicle.key().id()))

				# Get image URl for Vehicle views on Ricability
				ricability_model_name = vehicle.ricability_model_name
				if ricability_model_name is not None and ricability_model_name != '':
					image_filename = ricability_model_name.split(' ')
					image_filename = '-'.join(image_filename)
					# Add images object with Front View image
					response['images'] = {
						'front_view':'http://www.ricability.org.uk/consumer_reports/mobility_reports/car_measurement_guide/i/cars/1_Front View/'+image_filename+'.jpg',
						'rear_view':'http://www.ricability.org.uk/consumer_reports/mobility_reports/car_measurement_guide/i/cars/2_Rear View/'+image_filename+'.jpg',
						'boot':'http://www.ricability.org.uk/consumer_reports/mobility_reports/car_measurement_guide/i/cars/Boot/'+image_filename+'.jpg'
					}
				response['matches'] = matches
				# Set this in Memcache
				memcache.set(memcache_key, response)

			return response
	except Exception, e:
		logging.exception(e)
		raise e	
	

"""
	@name: set_vehicle
	@description:
		Sets an individual vehicle in the datastore
"""
def set_vehicle(**kwargs):
	try:
		yom = None
		key_name = kwargs.get('make')+':'+kwargs.get('model')
		if kwargs.get('year_of_manufacture') is not None:
			yom = int(kwargs.get('year_of_manufacture'))
			key_name = key_name+':'+kwargs.get('year_of_manufacture')
		if kwargs.get('door_plan') is not None:
			key_name = key_name+':'+kwargs.get('door_plan')

		vehicle = models.Vehicle.get_or_insert(
			key_name=key_name,
			make=kwargs.get('make'),
			model=kwargs.get('model'),
			ricability_model_name=kwargs.get('ricability_model_name'),
			year_of_manufacture=yom,
			door_plan=kwargs.get('door_plan'),
			door_plan_literal=kwargs.get('door_plan_literal'),
			boot_aperture_width_bottom=kwargs.get('boot_aperture_width_bottom'),
			boot_aperture_width_middle=kwargs.get('boot_aperture_width_middle'),
			boot_aperture_width_top=kwargs.get('boot_aperture_width_top'),
			boot_aperture_height=kwargs.get('boot_aperture_height'),
			boot_aperture_verticalheight=kwargs.get('boot_aperture_verticalheight'),
			boot_length=kwargs.get('boot_length')
		)

		return vehicle.key()
	except Exception, e:
		logging.exception(e)
		raise e
	