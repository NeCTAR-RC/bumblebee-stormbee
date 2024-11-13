#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#


import requests
import sys
import traceback
from xml.etree import ElementTree as ET


def report(config_section, service_name, state=0, output="OK", verbose=False):
    "Report results as to Nagios as a passive check using NRDP"

    try:
        hostname = config_section['NagiosTargetHost']
        url = config_section['NagiosURL']
        token = config_section['NagiosToken']
    except KeyError:
        print(
            "Missing NagiosTargetHost, NagiosURL or NagiosToken "
            "config settings for the selected site.  "
            "Skipping Nagios reporting."
        )
        return None

    checkresults = ET.Element('checkresults')
    checkresult = ET.SubElement(
        checkresults, 'checkresult', type='service', checktype='1'
    )
    ET.SubElement(checkresult, 'hostname').text = hostname
    ET.SubElement(checkresult, 'servicename').text = service_name
    ET.SubElement(checkresult, 'state').text = str(state)
    ET.SubElement(checkresult, 'output').text = output
    xml = ET.tostring(checkresults, 'utf-8')

    params = {'token': token.strip(), 'cmd': 'submitcheck', 'XMLDATA': xml}
    result = None
    try:
        if verbose:
            print(f"Raw Nagios NRDP request: {params}")
        response = requests.post(url, params=params)
        if verbose:
            print(f"Raw Nagios NRDP response: {response.text}")
        result = ET.ElementTree(ET.fromstring(response.text))
    except Exception as e:
        traceback.print_exception(*sys.exc_info())
        print(f"ERROR: Cannot connect to Nagios NRDP URL {url}: {e}")

    if result:
        message = result.getroot().find('message').text
        if verbose:
            print(f"Nagios NRDP returned: {message}")
        return message
    else:
        return None
