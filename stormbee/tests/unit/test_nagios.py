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


from io import StringIO
from unittest import TestCase
from unittest.mock import Mock, patch

from stormbee.nagios import report


CONF = {
    'NagiosTargetHost': 'vds.example.com',
    'NagiosURL': 'http://nagios.example.com/xrdp-endpoint',
    'NagiosToken': 'magic',
}


class NagiosTests(TestCase):
    @patch('requests.post')
    def test_report_bad_config(self, mock_post):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.assertIsNone(report({}, 'fake_service_name'))
            self.assertRegex(
                fake_out.getvalue(), r'.*Skipping Nagios reporting\.'
            )
        mock_post.assert_not_called()

    @patch('requests.post')
    def test_report(self, mock_post):
        fake_response = Mock(text='<result><message>Happy</message></result>')
        mock_post.return_value = fake_response
        message = report(CONF, 'tempest_foo_bar', state=42, output='cheese')
        self.assertEqual("Happy", message)
        data = (
            '<checkresults>'
            '<checkresult type="service" checktype="1">'
            f'<hostname>{CONF["NagiosTargetHost"]}</hostname>'
            '<servicename>tempest_foo_bar</servicename>'
            '<state>42</state>'
            '<output>cheese</output>'
            '</checkresult>'
            '</checkresults>'
        ).encode()
        mock_post.assert_called_with(
            CONF['NagiosURL'],
            params={
                'token': CONF['NagiosToken'],
                'cmd': 'submitcheck',
                'XMLDATA': data,
            },
        )
