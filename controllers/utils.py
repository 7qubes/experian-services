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

class BaseHandler(webapp2.RequestHandler):
	context = {}
	now = None
	def __init__(self, request=None, response=None):
		self.initialize(request, response)
		self.now = datetime.datetime.now()
		self.content = dict()
		self.status_code = 200
		self.populateContext()

		self.urlfetch = dict(
			method='POST',
			deadline=30,
			headers={
				'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/21.0.1180.89 Safari/535.19',
				'Accept':'application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5',
				'Content-Type':'text/xml'
			}
		)

		self.experian_config = dict(
			url='https://www.AutomotiveMXIN.com/UAT/',
			username='AUTOMXINUATF1006',
    		password='CKEWYN9C',
    		transaction_type='03'
		)

		self.ricability_config = dict(
			url='http://www.ricability.org.uk/consumer_reports/mobility_reports/car_measurement_guide/view.aspx?%s',
			method='GET',
			deadline=50,
			headers={
				'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/21.0.1180.89 Safari/535.19',
				'Accept':'application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5'
			}
		)
		

	def populateContext(self):
		self.context['request_args'] = None

	def set_request_arguments(self):
		request_args = dict()
		for arg in self.request.arguments():
			request_args[str(arg)] = str(self.request.get(arg))
				
		self.context['request_args'] = request_args
		
		logging.info(self.context['request_args'])

		return
	
	def set_response_error(self, error, status_code):
		self.content['error'] = error
		self.response.set_status(status_code)
		return

	def render(self, template_name):
		template = jinja_environment.get_template(template_name+'.html')
		self.response.out.write(template.render(self.context))
		return

	def render_json(self):
		self.data_output = json.dumps(self.content)
		if self.status_code is not None:
			self.response.set_status(self.status_code)
		else:
			self.response.set_status(200)
		self.response.headers['Content-Type'] = 'application/json'
		self.response.out.write(self.data_output)
		return

def create_memcache_key(key_prefix, **kwargs):
	memcache_key = key_prefix+':'
	if kwargs is not None:
		for request_arg, value in kwargs.items():
			if type(value) == list or type(value) == int or value == None:
				value = str(value)
			memcache_key+=request_arg+'='+value
	return memcache_key