import argparse
import configparser
import logging
from os.path import expanduser
import sys
import traceback

from pyvirtualdisplay import Display
from stormbee.driver import BumblebeeDriver
from stormbee.nagios import report


def main():
    parser = argparse.ArgumentParser(
        prog='stormbee',
        description="Perform scripted actions on a Bumblebee site. "
        "This is promarily intended for running functional tests, "
        "but could be used for other purposes.")
    parser.add_argument(
        '-c', '--config', action='store',
        help='the configuration file')
    parser.add_argument(
        '-p', '--show-progress', action='store_true',
        help='enable showing the "progress bar" information')
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='show debug-level logging')
    parser.add_argument(
        '-s', '--site', action='store',
        help="choose Bumblebee site to interact with.  Values are "
        "the section names in the config file.")
    parser.add_argument(
        '--nagios', action='store_true',
        help='report results as a nagios event')
    sub_parsers = parser.add_subparsers(help="Subcommand help",
                                        dest='action')
    sub_parsers.add_parser('status', help='Show status of desktop')
    launch = sub_parsers.add_parser('launch', help='Launch a desktop')
    launch.add_argument('-d', '--desktop', action='store',
                        help='the type of desktop to launch')
    launch.add_argument('-z', '--zone', action='store',
                        help='the availability zone to launch in')
    sub_parsers.add_parser('delete', help='Delete the desktop')
    sub_parsers.add_parser('shelve', help='Shelve the desktop')
    sub_parsers.add_parser('unshelve', help='Unshelve the desktop')
    sub_parsers.add_parser('boost', help='Boost the desktop')
    sub_parsers.add_parser('downsize', help='Downsize the desktop')
    reboot = sub_parsers.add_parser('reboot', help='Reboot the desktop')
    reboot.add_argument('--hard', action='store_true',
                        help='do a hard reboot')
    scenario = sub_parsers.add_parser('scenario', help='Run a scenario.')
    scenario.add_argument('name',
                          help='the name of the scenario')

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
        print(f"There is no section for site '{site_name}' "
              "in the config file")
        exit(code=2)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    failure = None
    with Display(backend="xvfb", visible=0, size=[800, 600]):
        bd = BumblebeeDriver(config, site_name)
        try:
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
        svcname = f"tempest_{site_name}_{args.desktop}_{args.scenario}_desktop"
        if failure:
            report(config[site_name],
                   svcname,
                   state=2,
                   output=f"ERROR: {args.action} failed: {str(failure)}",
                   verbose=True)
        else:
            report(config[site_name],
                   svcname,
                   state=0,
                   output=f"OK: {args.action} succeeded",
                   verbose=True)
    if failure:
        print(f"Stormbee failure for action {args.action} on site {site_name}")
        traceback.print_exception(*failure)
        exit(code=1)
    else:
        exit(code=0)


if __name__ == "__main__":
    main()
