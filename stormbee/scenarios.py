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
from copy import copy
import importlib

from stormbee.constants import (
    DESKTOP_SUPERSIZED,
    DESKTOP_EXISTS,
    DESKTOP_SHELVED,
    DESKTOP_FAILED,
    NO_DESKTOP,
    STATE_TOS,
    STATE_CREATE_WORKSPACE,
)


def find_scenario_class(name):
    if name == "lifecycle":
        return DesktopLifecycleScenario
    elif name == "basic":
        return DesktopBasicScenario
    elif name == "newuser":
        return NewUserScenario
    else:
        try:
            pkg = importlib.import_module(name)
            try:
                return pkg.Scenario
            except AttributeError:
                raise Exception(
                    f"Scenario module '{name}' does not "
                    "define a 'Scenario' class"
                )
        except ModuleNotFoundError:
            raise Exception(
                f"Cannot find the python module for Scenario '{name}'"
            )


class ScenarioBase:
    def __init__(self, bd, args, extra_args):
        self.bd = bd
        self.parser = argparse.ArgumentParser()
        self.args = copy(args)
        self.extra_args = extra_args

    def add_scenario_arguments(self):
        """Add argument specifications to the arg parser.

        This is designed to be overridden in subclasses.  The default is
        to do nothing; i.e. by default a Scenario expects no arguments
        """

        pass

    def do_run_scenario(self):
        "This is the entry-point for the Scenario."

        raise NotImplementedError(
            "'do_run_scenario' must be implemented " "by each Scenario"
        )

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
    """This is the full "test if Bumblebee is working" Scenario.

    The scenario launches, a desktop, shelves and unshelves it, boosts
    and downsizes it, reboots it and finally deletes it.
    """

    def add_scenario_arguments(self):
        pass

    def do_run_scenario(self):
        state = self.bd.get_desktop_state()
        if state in [
            DESKTOP_EXISTS,
            DESKTOP_SHELVED,
            DESKTOP_SUPERSIZED,
            DESKTOP_FAILED,
        ]:
            print("Reset: deleting existing desktop")
            self.bd.delete(self.args)
            state = self.bd.get_desktop_state()
        if state != NO_DESKTOP:
            raise Exception(f"Reset failed: state is '{state}'")
        with self.bd.timeit_context(f"{self.args.name} scenario"):
            is_boostable = self.bd.is_boostable(self.args)
            self.bd.launch(self.args)
            if is_boostable:
                self.bd.boost(self.args)
                self.bd.downsize(self.args)
            else:
                print("Reset: skipping boost / downsize: not boostable")
            self.bd.shelve(self.args)
            self.bd.unshelve(self.args)
            self.args.hard = True
            self.bd.reboot(self.args)
            self.bd.delete(self.args)
        print("Scenario completed")


class DesktopBasicScenario(ScenarioBase):
    "This Scenario simply launches and deletes a desktop."

    def add_scenario_arguments(self):
        pass

    def do_run_scenario(self):
        state = self.bd.get_desktop_state()
        if state in [
            DESKTOP_EXISTS,
            DESKTOP_SHELVED,
            DESKTOP_SUPERSIZED,
            DESKTOP_FAILED,
        ]:
            print("Reset: deleting existing desktop")
            self.bd.delete(self.args)
            state = self.bd.get_desktop_state()
        if state != NO_DESKTOP:
            raise Exception(f"Reset failed: state is '{state}'")
        with self.bd.timeit_context(f"{self.args.name} scenario"):
            self.bd.launch(self.args)
            self.bd.delete(self.args)
        print("Scenario completed")


class NewUserScenario(ScenarioBase):
    "This Scenario sets up a new user."

    def add_scenario_arguments(self):
        self.parser.add_argument(
            '--as-required',
            action='store_true',
            help='skip steps that have already been done',
        )

    def do_run_scenario(self):
        print(self.bd.get_desktop_state())
        if self.bd.get_desktop_state() != STATE_TOS:
            if not self.args.as_required:
                raise Exception(
                    f"Cannot run 'newuser' scenario for {self.bd.user_name}: "
                    "T&Cs already agreed to?"
                )
        else:
            self.bd.agree(self.args)

        if self.bd.get_desktop_state() != STATE_CREATE_WORKSPACE:
            if not self.args.as_required:
                raise Exception(
                    f"Cannot run 'newuser' scenario for {self.bd.user_name}: "
                    "workspace already created?"
                )
        else:
            self.bd.new_workspace(self.args)
        print("Scenario completed")
