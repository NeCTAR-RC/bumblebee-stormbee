import argparse
from copy import copy
import importlib

from stormbee.constants import \
    DESKTOP_SUPERSIZED, DESKTOP_EXISTS, DESKTOP_SHELVED, \
    DESKTOP_FAILED, NO_DESKTOP


def find_scenario_class(name):
    if name == "lifecycle":
        return DesktopLifecycleScenario
    else:
        try:
            pkg = importlib.import_module(name)
            try:
                return pkg.Scenario
            except AttributeError:
                raise Exception(
                    f"Scenario module '{name}' does not "
                    "define a 'Scenario' class")
        except ModuleNotFoundError:
            raise Exception(
                f"Cannot find the python module for Scenario '{name}'")


class ScenarioBase(object):

    def __init__(self, bd, args, extra_args):
        self.bd = bd
        self.parser = argparse.ArgumentParser()
        self.args = copy(args)
        self.extra_args = extra_args

    def add_scenario_arguments(self):
        """Add argument specifications to the arg parser.

        This is designed to be overrriden in subclasses.  The default is
        to do nothing; i.e. by default a Scenario expects no arguments
        """

        pass

    def add_argument(self, *args, **kwargs):
        """Register an argument with the scenario's subparser.

        A scenario's add_scenario_arguments method calls 'add_argument'
        to register scenario arguments or options.  The args and kwargs are
        passed as-is to the subparser's add_argument call.
        """

        self.parser.add_argument(*args, **kwargs)

    def do_run_scenario(self):
        "This is the entry-point for the Scenario."

        raise NotImplementedError("'do_run_scenario' must be implemented "
                                  "by each Scenario")

    def run(self):
        """Run the scenario.

        Runs the scenario with the args and the driver supplied to the
        constructor.  The args will be enhanced with scenario-specific
        argument.
        """

        self.add_scenario_arguments()
        self.parser.parse_args(args=self.extra_args, namespace=self.args)
        self.do_run_scenario()


class DesktopLifecycleScenario(ScenarioBase):
    """This is the basic "test if Bumblebee is working" Scenario.

    The scenario launches, a desktop, shelves and unshelves it, boosts
    and downsizes it, reboots it and finally deletes it.
    """

    def add_scenario_arguments(self):
        self.add_argument('-d', '--desktop', action='store',
                          help='the type of desktop to launch')
        self.add_argument('-z', '--zone', action='store',
                          help='the availability zone to launch in')

    def do_run_scenario(self):

        state = self.bd.get_desktop_state()
        if state in [DESKTOP_EXISTS, DESKTOP_SHELVED,
                     DESKTOP_SUPERSIZED, DESKTOP_FAILED]:
            print("Reset: deleting existing desktop")
            self.bd.delete(self.args)
            state = self.bd.get_desktop_state()
        if state != NO_DESKTOP:
            raise Exception(f"Reset failed: state is '{state}'")
        with self.bd.timeit_context(f"{self.args.name} scenario"):
            self.bd.launch(self.args)
            self.bd.boost(self.args)
            self.bd.downsize(self.args)
            self.bd.shelve(self.args)
            self.bd.unshelve(self.args)
            self.args.hard = True
            self.bd.reboot(self.args)
            self.bd.delete(self.args)
        print("Scenario completed")
