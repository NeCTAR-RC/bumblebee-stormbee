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


import argparse
import configparser
import logging
from os.path import expanduser
import sys
import traceback

from pyvirtualdisplay import Display
from stormbee import db
from stormbee.driver import BumblebeeDriver
from stormbee.nagios import report


def main():
    parser = argparse.ArgumentParser(
        prog='stormbee',
        description="Perform scripted actions on a Bumblebee site. "
        "This is promarily intended for running functional tests, "
        "but could be used for other purposes.",
    )
    parser.add_argument(
        '-c', '--config', action='store', help='the configuration file'
    )
    parser.add_argument(
        '-p',
        '--show-progress',
        action='store_true',
        help='enable showing the "progress bar" information',
    )
    parser.add_argument(
        '-d', '--debug', action='store_true', help='show debug-level logging'
    )
    parser.add_argument(
        '-s',
        '--site',
        action='store',
        help="choose Bumblebee site to interact with.  Values are "
        "the section names in the config file.",
    )
    parser.add_argument(
        '--nagios',
        action='store_true',
        help='report results as a nagios event',
    )
    parser.add_argument(
        '--desktop', action='store', help='the type of desktop to launch'
    )
    parser.add_argument(
        '-z',
        '--zone',
        action='store',
        help='the availability zone to launch in',
    )
    parser.add_argument(
        '--username',
        action='store',
        help='the user name to use for tests (overriding the config file)',
    )
    parser.add_argument(
        '--password',
        action='store',
        help='the password to use for tests (overriding the config file)',
    )

    sub_parsers = parser.add_subparsers(help="Subcommand help", dest='action')
    sub_parsers.add_parser('status', help='Show status of desktop')
    sub_parsers.add_parser('launch', help='Launch a desktop')
    sub_parsers.add_parser('delete', help='Delete the desktop')
    sub_parsers.add_parser('shelve', help='Shelve the desktop')
    sub_parsers.add_parser('unshelve', help='Unshelve the desktop')
    sub_parsers.add_parser('boost', help='Boost the desktop')
    sub_parsers.add_parser('downsize', help='Downsize the desktop')
    reboot = sub_parsers.add_parser('reboot', help='Reboot the desktop')
    reboot.add_argument('--hard', action='store_true', help='do a hard reboot')
    scenario = sub_parsers.add_parser('scenario', help='Run a scenario.')
    scenario.add_argument('name', help='the name of the scenario')
    reset = sub_parsers.add_parser('reset', help='clear database errors')
    reset.add_argument(
        '--force',
        action='store_true',
        help='run remediations even if no errors are reported',
    )

    (args, extra_args) = parser.parse_known_args()
    config = configparser.ConfigParser()
    config_file = args.config or expanduser("~/.stormbee.ini")
    if not config.read(config_file):
        print(f"Cannot read the config file: '{config_file}'")
        exit(code=2)
    site_name = args.site or config['DEFAULT'].get('DefaultSite')
    if not site_name:
        print("We need --site option or a DefaultSite in the config file")
        exit(code=2)
    if site_name not in config:
        print(f"There is no section for site '{site_name}' in the config file")
        exit(code=2)
    if args.nagios:
        if not (
            getattr(args, 'name', None)
            and getattr(args, 'zone', None)
            and getattr(args, 'desktop', None)
        ):
            print("Nagios reporting needs a zone, desktop type and scenario")
            exit(code=2)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    failure = None

    site_config = config[site_name]
    if args.action == 'reset':
        if not site_config.get('DbHost', None):
            print("DbHost is not configured: cannot reset DB")
            exit(code=2)
        try:
            rep = db.DBRepairer(site_config)
            errors = rep.error_counts()
            if errors or args.force:
                print(f"Clearing DB errors: {errors}")
                rep.clear_errors()
                print("DB reset done")
            else:
                print(
                    "DB reset skipped: no Volume, Instance or VMStatus "
                    "records in error state"
                )
        except Exception:
            failure = sys.exc_info()
    else:
        with Display(backend="xvfb", visible=0, size=[800, 600]):
            bd = BumblebeeDriver(
                site_config,
                site_name,
                username=args.username,
                password=args.password,
            )
            try:
                if args.action not in ['reset']:
                    bd.login(args)
                    bd.run(args.action, args, extra_args)
            except Exception:
                failure = sys.exc_info()
            finally:
                # Don't leak external web browser processes!
                bd.close()

    if args.nagios:
        # Service name will need to match what Nagios expects.
        # See `profile::core::tempest_nagios::tests:` in Hiera
        svcname = f"tempest_{args.zone}_desktop_{args.name}_{args.desktop}"
        if failure:
            report(
                site_config,
                svcname,
                state=2,
                output=f"ERROR: {args.action} failed: {str(failure)}",
                verbose=True,
            )
        else:
            report(
                site_config,
                svcname,
                state=0,
                output=f"OK: {args.action} succeeded",
                verbose=True,
            )

    if failure:
        print(f"Stormbee failure for action {args.action} on site {site_name}")
        traceback.print_exception(*failure)
        exit(code=1)
    else:
        exit(code=0)


if __name__ == "__main__":
    main()
