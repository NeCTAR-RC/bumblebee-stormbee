import requests
import sys
import traceback
from xml.etree import ElementTree as ET


def report(config_section, state=0, output="OK", verbose=False):
    "Report results as to Nagios as a passive check using NRDP"

    try:
        hostname = config_section['NagiosTargetHost']
        url = config_section['NagiosURL']
        token = config_section['NagiosToken']
    except KeyError:
        print("Missing NagiosTargetHost, NagiosURL or NagiosToken "
              "config settings for the selected site.  "
              "Skipping Nagios reporting.")
        return None

    checkresults = ET.Element('checkresults')
    checkresult = ET.SubElement(checkresults, 'checkresult',
                                type='service', checktype='1')
    ET.SubElement(checkresult, 'hostname').text = hostname
    ET.SubElement(checkresult, 'servicename').text = 'bumblebee-lifecycle'
    ET.SubElement(checkresult, 'state').text = str(state)
    ET.SubElement(checkresult, 'output').text = output
    xml = ET.tostring(checkresults, 'utf-8')

    params = {'token': token.strip(),
              'cmd': 'submitcheck',
              'XMLDATA': xml}
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
        print("ERROR: Cannot connect to Nagios NRDP URL %s: %s" % (url, e))

    if result:
        message = result.getroot().find('message').text
        if verbose:
            print("Nagios NRDP returned: %s" % message)
        return message
    else:
        return None
