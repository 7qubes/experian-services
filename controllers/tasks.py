import os
import logging
import datetime
import base64
import cgi
import time
import urllib
import urlparse
import re
from google.appengine.ext import db
from google.appengine.api.datastore import Key
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.runtime import DeadlineExceededError
import json
# Import local libraries and scripts
import html5lib
from html5lib import treebuilders, treewalkers, serializer

# Import local modules or scripts
from controllers import datastore
from models import models
from controllers import utils


class RicabilityVehicleCollection(utils.BaseHandler):
	def process(self):
		try:
			
			# Get Task params
			vehicle_id = str(self.request.get('vehicle_id'))
			make = ''
			model = ''
			yom = None
			door_plan = ''
			door_plan_literal = ''
			boot_aperture_bottom = None
			boot_aperture_middle = None
			boot_aperture_top = None
			boot_aperture_height = None
			boot_aperture_verticalheight = None

			# Set the default URL
			url = self.ricability_config.get('url')
			# Create the Request parameter arguments
			args = dict()
			args['CarID'] = vehicle_id
			args['fromPage'] = 'PickOne'
			args['measurement'] = 'cm'
			args = urllib.urlencode(args)

			url = url % args
			# Fetch the web page
			f = urlfetch.fetch(url=url, method=self.ricability_config.get('method'), deadline=self.ricability_config.get('deadline'), headers=self.ricability_config.get('headers'))
			if f.status_code == 200:
				# Create Parser
				parser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder('dom'))
				
				# Create MiniDom Document
				minidom_document = parser.parse(f.content)

				# Get all DIVs
				all_divs = minidom_document.getElementsByTagName('div')
				for div in all_divs:
					# If we find the #container-content, break
					if div.getAttribute('id') == 'container-content':
						# Now get all child DIVs to get the vehicle make, model, door plan and year of manufacture
						content_divs = div.getElementsByTagName('div')
						vehicle_details_div = content_divs[5]
						vehicle_name_strong = vehicle_details_div.getElementsByTagName('strong')[0]
						# Get the last TextNode
						vehicle_name = vehicle_name_strong.childNodes[-1].nodeValue
						logging.info(vehicle_name)

						vehicle_name_split = vehicle_name.split(' ')
						logging.info('vehicle_name_split')
						logging.info(vehicle_name_split)

						make = vehicle_name_split[0]
						logging.info(make)
						
						model = vehicle_name_split[1]
						logging.info(model)

						# Extract Door Plan
						regexp_pattern_doorplan = re.compile('(\d+[dr]{2}\s[a-zA-Z\-0-9]+)')
						regex_result_doorplan = regexp_pattern_doorplan.findall(vehicle_name)
						logging.info('regex_result_doorplan')
						logging.info(regex_result_doorplan)

						if len(regex_result_doorplan) > 0:
							door_plan_text = regex_result_doorplan[0]
							# Set the Door Plan collected from Ricability to lowercase
							# This is to avoid tyhis scenario not matching: '3dr hatch' vs '3dr Hatch' (no match)
							door_plan_text = door_plan_text.lower()
							logging.info(door_plan_text)
							# Set DVLA Door Plan Code
							if models.ricability_to_dvla_door_plan.get(door_plan_text) is not None:
								dvla_door_plan_code = models.ricability_to_dvla_door_plan.get(door_plan_text)
								if dvla_door_plan_code is not None:
									door_plan = dvla_door_plan_code
									logging.info(door_plan)
							# Set DVLA Door Plan Literal
							if models.ricability_to_dvla_door_plan_literal.get(door_plan_text) is not None:
								dvla_door_plan_literal = models.ricability_to_dvla_door_plan_literal.get(door_plan_text)
								if dvla_door_plan_literal is not None:
									door_plan_literal = dvla_door_plan_literal
									logging.info(door_plan_literal)
						# Extract Year Of Manufacture
						regexp_pattern_yom = re.compile('(\d{4})')
						regex_result_yom = regexp_pattern_yom.findall(vehicle_name)
						if len(regex_result_yom) > 0:
							yom = regex_result_yom[0]
							logging.info(yom)


						# Extract Boot dimensions
						all_tables = div.getElementsByTagName('table')
						for table in all_tables:
							tbody = table.getElementsByTagName('tbody')[0]
							trows = tbody.getElementsByTagName('tr')
							trow_focus = trows[0]
							thead_cells = trow_focus.getElementsByTagName('th')

							if len(thead_cells) > 0:
								thead_cell = thead_cells[0]
								# Get the final TextNode
								thead_nodes = thead_cell.childNodes
								thead_node_value = thead_nodes[-1].nodeValue
								thead_node_value = thead_node_value.strip()
								if thead_node_value == 'Boot size':
									logging.info('Boot Dimensions')

									# For each Row data
									for row in trows:
										# Get all the TD cells
										cells = row.getElementsByTagName('td')
										# If any TD cells exist
										if len(cells) > 0:
											# Collect Boot Aperture Bottom
											first_cell_text = cells[0].childNodes[-1].nodeValue.strip()
											if first_cell_text == 'Bottom':
												try:
													second_cell = cells[1].childNodes[-1].nodeValue.strip()
													if second_cell != 'n / a':
														boot_aperture_bottom = float(second_cell)
												except Exception, e:
													logging.exception('Aperture Bottom')
													logging.exception(e)
																							
											if first_cell_text == 'Middle':
												try:
													second_cell = cells[1].childNodes[-1].nodeValue.strip()
													if second_cell != 'n / a':
														boot_aperture_middle = float(second_cell)
												except Exception, e:
													logging.exception('Aperture Middle')
													logging.exception(e)

											if first_cell_text == 'Top':
												try:
													second_cell = cells[1].childNodes[-1].nodeValue.strip()
													if second_cell != 'n / a':
														boot_aperture_top = float(second_cell)
												except Exception, e:
													logging.exception('Aperture Top')
													logging.exception(e)

											if first_cell_text == 'Height':
												try:
													second_cell = cells[1].childNodes[-1].nodeValue.strip()
													if second_cell != 'n / a':
														boot_aperture_height = float(second_cell)
												except Exception, e:
													logging.exception('Aperture Height')
													logging.exception(e)

											if first_cell_text == 'Vertical height':
												try:
													second_cell = cells[1].childNodes[1].nodeValue.strip()
													# Get the second TextNode from the available Nodes, such that a dingle value or any range values
													# will yield the first and lowest result, e.g. '50-60' should yield '50'
													if second_cell != 'n / a to n / a':
														boot_aperture_height_text = second_cell
														regexp_pattern_boot_aperture_verticalheight = re.compile('(\d{2})')
														regex_result_boot_aperture_verticalheight = regexp_pattern_boot_aperture_verticalheight.findall(boot_aperture_height_text)
														logging.info('regex_result_boot_aperture_verticalheight')
														logging.info(regex_result_boot_aperture_verticalheight)
														logging.info('regex_result_boot_aperture_verticalheight[0]')
														logging.info(regex_result_boot_aperture_verticalheight[0])
														boot_aperture_verticalheight = float(regex_result_boot_aperture_verticalheight[0])
														logging.info('boot_aperture_verticalheight')
														logging.info(boot_aperture_verticalheight)
												except Exception, e:
													logging.exception('Aperture Vertical Height')
													logging.exception(e)

									# Break out of table loop
									break

						vehicle = datastore.set_vehicle(**dict(
							make=make,
							model=model,
							year_of_manufacture=yom,
							door_plan=door_plan,
							door_plan_literal=door_plan_literal,
							boot_aperture_bottom=boot_aperture_bottom,
							boot_aperture_middle=boot_aperture_middle,
							boot_aperture_top=boot_aperture_top,
							boot_aperture_height=boot_aperture_height,
							boot_aperture_verticalheight=boot_aperture_verticalheight
						))
						
						# Break #container-content
						break
	            
			else:
				logging.warning(f)
				logging.warning(f.status_code)
				logging.warning(f.content)

			return True

		except Exception, e:
			logging.exception(e)
			raise e		

	def get(self):
		self.process()
	def post(self):
		self.process()