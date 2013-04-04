#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
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
try:
    import xml.etree.cElementTree as etree
except ImportError:
    import xml.etree.ElementTree as etree

# Import local modules
from controllers import utils
from controllers import datastore
from controllers import default
from controllers import cron
from controllers import tasks
from models import models

# URLs
requestDSStub = '/dsstub'

# CRON
cronRicabilityVehicleCollection = '/cron/ricability-vehicle-collection'

# Tasks
taskRicabilityVehicleCollection = '/tasks/ricability-vehicle-collection'

class MainHandler(utils.BaseHandler):
    def get(self):
        self.set_request_arguments()
        transaction_type = self.experian_config['transaction_type']
        try:
            if 'vrm' in self.context['request_args'] and self.context['request_args']['vrm'] != '':
                memcache_key = utils.create_memcache_key('willitfitinmycar', **self.context['request_args'])
                logging.info('Request : memcache_key')
                logging.info(memcache_key)
                memcache_response = memcache.get(memcache_key)

                if memcache_response is not None:
                    self.content = memcache_response
                else:
                    if 'transactionType' in self.context['request_args'] and self.context['request_args']['transactionType'] != '':
                        transaction_type = self.context['request_args']['transactionType']
                    
                    payload = '<EXPERIAN><ESERIES><FORM_ID>B2INT</FORM_ID></ESERIES><MXIN><TRANSACTIONTYPE>'+transaction_type+'</TRANSACTIONTYPE><PAYMENTCOLLECTIONTYPE>02</PAYMENTCOLLECTIONTYPE><USERNAME>'+self.experian_config['username']+'</USERNAME><PASSWORD>'+self.experian_config['password']+'</PASSWORD><VRM>'+self.context['request_args']['vrm']+'</VRM></MXIN></EXPERIAN>'
                    
                    response = urlfetch.fetch(
                        url=self.experian_config['url'],
                        method='POST',
                        payload=payload,
                        deadline=30,
                        headers=self.urlfetch['headers']
                    )
                    if response.status_code == 200:
                        logging.info(response.content)

                        # Create a Vehicle dictionary                        
                        vehicle = dict()
                        json_vehicle_data = self.create_json_response(response.content)
                        logging.info(json_vehicle_data)

                        # Add the DVLA vehicle data or error
                        vehicle['dvla'] = json_vehicle_data
                        
                        # Check we have a successful vehicle lookup
                        if json_vehicle_data.get('MAKE') is not None:
                            # Get Make
                            make = json_vehicle_data.get('MAKE').lower()
                            make = make.title()
                            logging.info(make)

                            # Get Model
                            model = json_vehicle_data.get('MODEL').lower()
                            model = model.title()
                            # Now select the first word of the model, as we will use this to match our Datastore models
                            model = model.split(' ')[0]
                            logging.info(model)

                            # Get Year Of Manufacture
                            year_of_manufacture = json_vehicle_data.get('YEAROFMANUFACTURE')
                            logging.info(year_of_manufacture)

                            # Get Door Plan Literal
                            door_plan_literal = ''
                            door_plan_literal_string = json_vehicle_data.get('DOORPLANLITERAL')
                            door_plan_literal_string = door_plan_literal_string.lower()
                            door_plan_literal_string = door_plan_literal_string.title()
                            if door_plan_literal_string in models.dvla_door_plan_literal_inv:
                                logging.info(door_plan_literal_string)
                                door_plan_literal = models.dvla_door_plan_literal_inv.get(door_plan_literal_string)

                            logging.info(door_plan_literal)

                            # Query the DB for the Vehicle
                            try:
                                query = datastore.get_vehicle(**dict(
                                    make=make,
                                    model=model,
                                    door_plan_literal=door_plan_literal,
                                    year_of_manufacture=year_of_manufacture
                                ))

                                logging.info(query)
                                # Add the DB Query data
                                vehicle['datastore'] = query
                                if query is not None:
                                    vehicle['datastore']['door_plan_literal_string'] = door_plan_literal_string
                                # Set the response context data
                                self.content = dict(data=vehicle)
                                # Cache for longevity
                                memcache.set(memcache_key, self.content)
                            except Exception, e:
                                # Add the DB Query error
                                vehicle['datastore'] = str(e)
                                # Set the response context data
                                self.content = dict(data=vehicle)
                                # Cache for a short period
                                memcache.set(memcache_key, self.content, time=8000)

                    else:
                        raise Exception('Bad Experian Response')
            else:
                raise Exception('VRM parameter value missing')
                
        except Exception, e:
            logging.exception(e)
            self.set_response_error(e.message, 500)
        finally:
            self.render_json()


    def create_json_response(self, xml_content):
        """

        Failure:
        <?xml version='1.0' standalone='yes'?>
        <GEODS exp_cid='jmny'>
            <REQUEST type='RETURN' subtype='CALLBUR' EXP_ExperianRef='' success='N' timestamp='Wed, 3 Apr 2013 at 6:10 PM' id='jmny'>
                <MXE1>
                    <CODE>0009</CODE>
                    <LENGTH>029</LENGTH>
                    <SEVERITY>4</SEVERITY>
                    <MSG>VEHICLE NOT FOUND ON DATABASE</MSG>
                </MXE1>
            </REQUEST>
        </GEODS>

        Failure:
        <?xml version='1.0' standalone='yes'?>
        <GEODS>
            <REQUEST type='RETURN' success='N'>
                <ERR1>
                    <CODE>TM01</CODE>
                    <SEVERITY>4</SEVERITY>
                    <MESSAGE>The length of the supplied field is invalid(MXIN_VRM 0)</MESSAGE>
                </ERR1>
            </REQUEST>
        </GEODS>


        Success:
        <?xml version='1.0' standalone='yes'?>
        <GEODS exp_cid='86sq'>
            <REQUEST type='RETURN' subtype='CALLBUR' EXP_ExperianRef='' success='Y' timestamp='Tue, 2 Apr 2013 at 1:40 PM' id='86sq'>
                <MB01 seq='01'>
                    <DATEOFTRANSACTION>20120813</DATEOFTRANSACTION>
                    <VRM>P874OPP </VRM>
                    <VINCONFIRMATIONFLAG>0</VINCONFIRMATIONFLAG>
                    <ENGINECAPACITY>01392</ENGINECAPACITY>
                    <DOORPLAN>14</DOORPLAN>
                    <DATEFIRSTREGISTERED>19961030</DATEFIRSTREGISTERED>
                    <YEAROFMANUFACTURE>1996</YEAROFMANUFACTURE>
                    <SCRAPPED>0</SCRAPPED>
                    <EXPORTED>0</EXPORTED>
                    <IMPORTED>0</IMPORTED>
                    <MAKE>NISSAN</MAKE>
                    <MODEL>ALMERA EQUATION</MODEL>
                    <COLOUR>GREEN</COLOUR>
                    <TRANSMISSION>MANUAL 5 GEARS</TRANSMISSION>
                    <ENGINENUMBER>GA14-202726</ENGINENUMBER>
                    <VINSERIALNUMBER>JN1FAAN15U0013185</VINSERIALNUMBER>
                    <DOORPLANLITERAL>5 DOOR HATCHBACK</DOORPLANLITERAL>
                    <MVRISMAKECODE>S8</MVRISMAKECODE>
                    <MVRISMODELCODE>TBB</MVRISMODELCODE>
                    <DTPMAKECODE>RA</DTPMAKECODE>
                    <DTPMODELCODE>289</DTPMODELCODE>
                    <TRANSMISSIONCODE>M</TRANSMISSIONCODE>
                    <GEARS>5</GEARS>
                    <FUEL>PETROL</FUEL>
                    <CO2EMISSIONS>*</CO2EMISSIONS>
                    <USEDBEFORE1STREG>0</USEDBEFORE1STREG>
                    <IMPORTNONEU>0</IMPORTNONEU>
                    <UKDATEFIRSTREGISTERED>19961030</UKDATEFIRSTREGISTERED>
                    <MAKEMODEL>NISSAN ALMERA EQUATION</MAKEMODEL>
                </MB01>
                <MB37 seq='01'>
                    <V5CDATACOUNT>01</V5CDATACOUNT>
                    <V5CDATAITEMS>
                        <DATE>20111021</DATE>
                    </V5CDATAITEMS>
                </MB37>
            </REQUEST>
        </GEODS>
        """
        response = dict()
        try:
            root = etree.fromstring(xml_content)
            request = root.find('REQUEST')
            success = request.get('success')
            if success is not None and success == 'Y':
                mb01 = root.find('REQUEST/MB01')
                for item in mb01:
                    response[item.tag] = item.text
            else:
                response['error'] = root.find('REQUEST/ERR1/MESSAGE').text
        except Exception, e:
            raise e
        finally:
            return response
        

app = webapp2.WSGIApplication([
    (cronRicabilityVehicleCollection, cron.RicabilityVehicleCollection),
    (taskRicabilityVehicleCollection, tasks.RicabilityVehicleCollection),
    (requestDSStub, default.DSStub),
    ('/', MainHandler)
], debug=True)
