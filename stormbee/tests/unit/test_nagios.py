from io import StringIO
from unittest import TestCase
from unittest.mock import Mock, patch

from stormbee.nagios import report


CONF = {
    'NagiosTargetHost': 'vds.example.com',
    'NagiosURL': 'http://nagios.example.com/xrdp-endpoint',
    'NagiosToken': 'magic',
    'NagiosServiceName': 'silver',
}


class NagiosTests(TestCase):

    @patch('requests.post')
    def test_report_bad_config(self, mock_post):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.assertIsNone(report({}))
            self.assertRegex(fake_out.getvalue(),
                             r'.*Skipping Nagios reporting\.')
        mock_post.assert_not_called()

    @patch('requests.post')
    def test_report(self, mock_post):
        fake_response = Mock(text='<result><message>Happy</message></result>')
        mock_post.return_value = fake_response
        message = report(CONF, state=42, output='cheese')
        self.assertEqual("Happy", message)
        data = ('<checkresults>'
                '<checkresult type="service" checktype="1">'
                f'<hostname>{CONF["NagiosTargetHost"]}</hostname>'
                f'<servicename>{CONF["NagiosServiceName"]}</servicename>'
                '<state>42</state>'
                '<output>cheese</output>'
                '</checkresult>'
                '</checkresults>').encode()
        mock_post.assert_called_with(
            CONF['NagiosURL'],
            params={
                'token': CONF['NagiosToken'],
                'cmd': 'submitcheck',
                'XMLDATA': data})
