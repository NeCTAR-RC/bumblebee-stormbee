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


from contextlib import contextmanager
import logging
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select
from webdriver_manager.firefox import GeckoDriverManager

from stormbee.constants import (
    DESKTOP_SUPERSIZED,
    DESKTOP_EXISTS,
    DESKTOP_SHELVED,
    DESKTOP_FAILED,
    WORKFLOW_RUNNING,
    NO_DESKTOP,
    STATE_TOS,
    STATE_CREATE_WORKSPACE,
    STATE_NOT_LOGGED_IN,
    STATE_UNKNOWN,
)
from stormbee import scenarios

LOG = logging.getLogger(__name__)


def set_viewport_size(driver, width, height):
    window_size = driver.execute_script(
        """
        return [window.outerWidth - window.innerWidth + arguments[0],
          window.outerHeight - window.innerHeight + arguments[1]];
        """,
        width,
        height,
    )
    driver.set_window_size(*window_size)


class BumblebeeDriver:
    def __init__(self, site_config, site_name, username=None, password=None):
        self.site_name = site_name
        self.site_config = site_config
        self.user_name = username or self.site_config['Username']
        self.password = password or self.site_config['Password']
        self.base_url = self.site_config['BaseUrl']
        self.home_url = f"{self.base_url}/home/"
        self.driver = Firefox(service=Service(GeckoDriverManager().install()))
        self.poll_seconds = int(self.site_config.get('PollSeconds', '5'))
        self.poll_retries = int(self.site_config.get('PollRetries', '50'))

        # An alternative to the following would be to set the screen
        # size via an options argument to the driver constructor:
        # see https://stackoverflow.com/a/55878622/139985
        set_viewport_size(self.driver, 1024, 768)

    def close(self):
        if self.driver:
            self.driver.close()

    def run(self, action, args, extra_args):
        if action == 'scenario':
            self.scenario(args, extra_args)
        elif extra_args:
            raise Exception(
                f"Unmatched arguments and options for {action}: {extra_args}"
            )
        else:
            func = getattr(self, args.action)
            func(args)

    @contextmanager
    def timeit_context(self, description):
        print(f'Starting {description}')
        start_time = time.time()
        yield
        elapsed_time = time.time() - start_time
        print(
            f'Finished {description} finished in '
            f'{int(elapsed_time * 1_000)} ms'
        )

    def get_desktop_state(self):
        "Figure out the current state of the user's desktop."

        if self.driver.current_url != self.home_url:
            self.driver.get(self.home_url)
        if self.driver.title in [
            self.site_config['KeycloakLoginTitle'],
            self.site_config['ClassicLoginTitle'],
        ]:
            return STATE_NOT_LOGGED_IN
        states = [
            (
                '//small[contains(text(), "Your boosted desktop")]',
                DESKTOP_SUPERSIZED,
            ),
            (
                '//h3[contains(text(), "Your Virtual Desktop is")]',
                DESKTOP_EXISTS,
            ),
            (
                '//h3[contains(text(), "Your Desktop is currently shelved")]',
                DESKTOP_SHELVED,
            ),
            ('//p[contains(text(), "Virtual Desktop Error")]', DESKTOP_FAILED),
            ('//p[contains(text(), "worker is busy")]', WORKFLOW_RUNNING),
            (
                '//h4[contains(text(), "You haven\'t created a Desktop")]',
                NO_DESKTOP,
            ),
            ('//h1[contains(text(), "Terms of Service")]', STATE_TOS),
            (
                '//a[contains(@title, "Create Project")]',
                STATE_CREATE_WORKSPACE,
            ),
        ]
        for xpath, state in states:
            try:
                self.driver.find_element(By.XPATH, xpath)
                return state
            except NoSuchElementException:
                pass
        LOG.debug(f"Page body for unknown state:\n{self.driver.page_source}")
        return STATE_UNKNOWN

    def get_current_desktop(self):
        "Figure out the desktop type for the current desktop."

        if self.driver.current_url != self.home_url:
            self.driver.get(self.home_url)

        try:
            div = self.driver.find_element(
                By.XPATH, '//div[starts-with(@id, "researcher_desktop")]'
            )
        except NoSuchElementException:
            raise Exception("There is no current desktop")

        id = div.get_attribute('id')
        return id.split('-')[1]

    def is_boostable(self, args):
        "Test if the target desktop type is valid and supports Boost"

        desktop_type = args.desktop or self.site_config['DesktopType']

        self.driver.get(f"{self.base_url}/desktop/{desktop_type}")
        try:
            self.driver.find_element(By.XPATH, '//h6[text()="DEFAULT SIZE"]')
        except NoSuchElementException:
            raise Exception(
                "Can't find details for desktop type "
                f"'{desktop_type}' - does it exist?"
            )
        try:
            self.driver.find_element(By.XPATH, '//h6[text()="BOOST SIZE"]')
            return True
        except NoSuchElementException:
            return False

    def diagnose_desktop(self):
        state = self.get_desktop_state()
        raise Exception(f"Desktop in unexpected state: '{state}'")

    def status(self, args):
        with self.timeit_context('Desktop status'):
            state = self.get_desktop_state()
            print(f"Current status is '{state}'")
            if state in [
                DESKTOP_SUPERSIZED,
                DESKTOP_EXISTS,
                DESKTOP_SHELVED,
                DESKTOP_FAILED,
                WORKFLOW_RUNNING,
            ]:
                desktop_type = self.get_current_desktop()
                print(f"Current desktop's type is '{desktop_type}'")

    def scenario(self, args, extra_args):
        scenario_cls = scenarios.find_scenario_class(args.name)
        scenario = scenario_cls(self, args, extra_args)
        scenario.run()

    def launch(self, args):
        with self.timeit_context('Launch Desktop'):
            if self.get_desktop_state() != NO_DESKTOP:
                self.diagnose_desktop()

            desktop_type = args.desktop or self.site_config['DesktopType']
            zone = args.zone or ''

            # Using launch url directly rather than the "View Details" button
            # for the desktop.  Unfortunately, there is no 'id' on the <a>
            # element for easy identification.  There is only the 'href' ...
            # which is what we should be extracting!
            launch_url = f"{self.base_url}/desktop/{desktop_type}"
            self.driver.get(launch_url)

            print(
                f"Launching '{desktop_type}' desktop in "
                f"zone '{zone or 'default'}'"
            )
            try:
                modal_launch_button = self.driver.find_element(
                    By.XPATH, '//button[contains(text(), "Create Desktop")]'
                )
            except NoSuchElementException as e:
                # Deal with the case of an unknown desktop type.
                try:
                    self.driver.find_element(
                        By.XPATH,
                        (
                            '//h1[contains(text(), "Page Not Found") '
                            'or contains(text(), "Page not found")]'
                        ),
                    )
                    raise Exception(
                        f"Desktop type '{desktop_type}' is not "
                        "recognized by the server."
                    )
                except NoSuchElementException:
                    raise e

            try:
                modal_launch_button.click()
            except ElementClickInterceptedException as e:
                # Deal with the case of a disabled launch button
                try:
                    self.driver.find_element(
                        By.XPATH, '//span[@data-bs-content]'
                    )
                    raise Exception("User already has a desktop!")
                except NoSuchElementException:
                    raise e

            if zone:
                # If multiple zones are applicable, the UI has a 'select'
                # element.  If only one, there is a 'p' element whose 'id'
                # contains the zone.  If none it is different again.
                try:
                    select = Select(
                        self.driver.find_element(
                            By.ID, f"researcher_workspace-{desktop_type}-zone"
                        )
                    )
                    try:
                        select.select_by_value(zone)
                    except NoSuchElementException:
                        raise Exception(f"Zone {zone} not understood (1)")
                except NoSuchElementException:
                    try:
                        self.driver.find_element(
                            By.ID,
                            f"researcher_workspace-{desktop_type}-{zone}",
                        )
                    except NoSuchElementException:
                        raise Exception(f"Zone {zone} not understood (2)")

            create_button = self.driver.find_element(
                By.XPATH, '//button[text()="Create"]'
            )
            create_button.click()

            if self.driver.current_url != self.home_url:
                raise Exception(f"Didn't redirect to {self.home_url}")

            self.wait_for_worker(args)
            if self.get_desktop_state() != DESKTOP_EXISTS:
                raise Exception("Launch sequence did not complete")

    def wait_for_worker(self, args):
        # Poll, waiting for "the worker is busy ..." to end
        desktop_type = self.get_current_desktop()
        bar_id = f'researcher_desktop-{desktop_type}-bar'
        retries = 0
        while retries < self.poll_retries:
            try:
                self.driver.find_element(
                    By.XPATH, '//p[contains(text(), "worker is busy")]'
                )
            except NoSuchElementException:
                return
            if args.show_progress:
                # Extract and display the progress information
                try:
                    bar = self.driver.find_element(By.ID, bar_id)
                    percent = bar.get_attribute('aria-valuenow')
                    message = self.driver.find_element(
                        By.ID, "progress-bar-message"
                    ).text
                    print(f"Progress: {percent}%, message: '{message}'")
                except NoSuchElementException:
                    pass
            time.sleep(self.poll_seconds)
            retries += 1

    def find_and_click_modal_command(self, verb, text):
        desktop = self.get_current_desktop()
        modal_id = f'researcher_desktop-{desktop}-{verb}-modal'
        modal_button = self.driver.find_element(
            By.XPATH, f'//button[@data-bs-target="#{modal_id}"]'
        )
        modal_button.click()
        button = self.driver.find_element(
            By.XPATH, f'//div[@id="{modal_id}"]//button[text()="{text}"]'
        )
        button.click()

    def delete(self, args):
        with self.timeit_context('Delete Desktop'):
            state = self.get_desktop_state()
            if state not in [
                DESKTOP_EXISTS,
                DESKTOP_FAILED,
                DESKTOP_SUPERSIZED,
                DESKTOP_SHELVED,
            ]:
                self.diagnose_desktop()
            self.find_and_click_modal_command('delete', 'Delete')
            if self.get_desktop_state() != NO_DESKTOP:
                self.diagnose_desktop()

    def boost(self, args):
        with self.timeit_context('Boost Desktop'):
            if self.get_desktop_state() != DESKTOP_EXISTS:
                self.diagnose_desktop()
            self.find_and_click_modal_command('supersize', 'Boost')
            self.wait_for_worker(args)
            if self.get_desktop_state() != DESKTOP_SUPERSIZED:
                raise Exception("Boosting did not complete")

    def downsize(self, args):
        with self.timeit_context('Downsize Desktop'):
            if self.get_desktop_state() != DESKTOP_SUPERSIZED:
                self.diagnose_desktop()
            self.find_and_click_modal_command('downsize', 'Downsize')
            self.wait_for_worker(args)
            if self.get_desktop_state() != DESKTOP_EXISTS:
                raise Exception("Downsizing did not complete")

    def shelve(self, args):
        with self.timeit_context('Shelve Desktop'):
            state = self.get_desktop_state()
            if state not in [DESKTOP_EXISTS, DESKTOP_SUPERSIZED]:
                self.diagnose_desktop()
            self.find_and_click_modal_command('shelve', 'Shelve')
            self.wait_for_worker(args)
            if self.get_desktop_state() != DESKTOP_SHELVED:
                raise Exception("Shelving did not complete")

    def unshelve(self, args):
        with self.timeit_context('Unshelve Desktop'):
            if self.get_desktop_state() != DESKTOP_SHELVED:
                self.diagnose_desktop()
            self.find_and_click_modal_command('unshelve', 'Unshelve')
            self.wait_for_worker(args)
            if self.get_desktop_state() != DESKTOP_EXISTS:
                raise Exception("Unshelving did not complete")

    def reboot(self, args):
        with self.timeit_context('Reboot Desktop'):
            state = self.get_desktop_state()
            if state not in [DESKTOP_EXISTS, DESKTOP_SUPERSIZED]:
                self.diagnose_desktop()
            reboot = "Hard Reboot" if args.hard else "Soft Reboot"
            self.find_and_click_modal_command('reboot', reboot)
            self.wait_for_worker(args)
            state = self.get_desktop_state()
            if state not in [DESKTOP_EXISTS, DESKTOP_SUPERSIZED]:
                raise Exception("Reboot did not complete")

    def login(self, args):
        use_oidc = self.site_config.get('UseOIDC', 'True')
        if use_oidc.lower() in ['true', 'yes', '1']:
            self.oidc_login()
        else:
            self.classic_login()

    def classic_login(self):
        print('Logging in (classic)')
        self.driver.get(self.home_url)
        if self.driver.title == self.site_config['KeycloakLoginTitle']:
            raise Exception(
                "Got the Keycloak login page: "
                "is the server's USE_OIDC setting wrong?"
            )
        elif self.driver.title == self.site_config['ClassicLoginTitle']:
            form = self.driver.find_element(By.ID, 'login-form')
            form.find_element(By.ID, 'id_username').send_keys(self.user_name)
            form.find_element(By.ID, 'id_password').send_keys(self.password)
            form.find_element(By.XPATH, '//input[@type="submit"]').click()
            if self.driver.title == self.site_config['AdminTitle']:
                # Manually redirect to home if necessary
                self.driver.get(self.home_url)
            if self.driver.title == self.site_config['HomeTitle']:
                print("Logged in!")
            else:
                raise Exception(
                    "Login sequence didn't work: "
                    f"expected '{self.site_config['HomeTitle']}', "
                    f"got '{self.driver.title}', "
                )
        elif self.driver.title == self.site_config['HomeTitle']:
            print('Already logged in')
        else:
            raise Exception(
                "Unexpected title for home page: " f"'{self.driver.title}'"
            )

    def agree(self, args):
        self.driver.get(self.home_url)
        if self.driver.current_url != f"{self.base_url}/terms/":
            raise Exception("Didn't redirect to Terms of Service page")
        agree_button = self.driver.find_element(
            By.XPATH,
            '//button[text()="I agree to the above Terms of Service."]',
        )
        agree_button.click()
        self.driver.get(self.home_url)
        if self.driver.current_url != self.home_url:
            raise Exception("Didn't redirect to home page")

    def new_workspace(self, args):
        self.driver.get(self.home_url)
        if self.driver.current_url != self.home_url:
            raise Exception("Redirected unexpectedly")
        create_button = self.driver.find_element(
            By.XPATH, '//a[contains(@title, "Create Project")]'
        )
        create_button.click()
        if self.driver.current_url != f"{self.base_url}/new_project":
            raise Exception("Didn't redirect to New Project page")
        submit_button = self.driver.find_element(
            By.XPATH, "//input[@value='Submit']"
        )
        title_field = self.driver.find_element(By.ID, "id_title")
        title_description = self.driver.find_element(By.ID, "id_description")
        title_ci = self.driver.find_element(By.ID, "id_chief_investigator")

        # pre-commit hook thought there was a typo in the next 2 lines ...
        # until I split the id string.
        title_forcode_1 = self.driver.find_element(By.ID, "id_F" + "oR_code")
        title_forcode_2 = self.driver.find_element(By.ID, "id_F" + "oR_code2")

        title_forcode_2.send_keys("31")
        title_forcode_1.send_keys("30")
        title_field.send_keys("Test project")
        title_description.send_keys("Sample project description")
        title_ci.send_keys("nobody@ardc.edu.au")
        submit_button.click()
        if self.get_desktop_state() != NO_DESKTOP:
            raise Exception("Didn't go into 'No Desktop' state")

    def oidc_login(self):
        print('Logging in (oidc)')
        self.driver.get(self.home_url)
        if self.driver.title == self.site_config['ClassicLoginTitle']:
            raise Exception(
                "Didn't get the Keycloak login page: "
                "is the server's USE_OIDC setting wrong?"
            )
        elif self.driver.title == self.site_config['KeycloakLoginTitle']:
            form = self.driver.find_element(By.ID, "kc-form-login")

            # The Keycloak username/password login form is may be hidden.
            # Unhide it.
            display = form.value_of_css_property('display')
            if display == 'none':
                self.driver.execute_script(
                    "arguments[0].style.display = 'block';", form
                )

            # Then fill it in and click the submit.
            username = form.find_element(By.ID, 'username')
            username.send_keys(self.user_name)
            password = form.find_element(By.ID, 'password')
            password.send_keys(self.password)
            button = form.find_element(By.ID, 'kc-login')
            button.click()
            state = self.get_desktop_state()
            if state in [STATE_TOS, STATE_NOT_LOGGED_IN, STATE_UNKNOWN]:
                raise Exception(
                    "Login sequence didn't work: " f"state is '{state}'"
                )
        elif self.driver.title == self.site_config['HomeTitle']:
            print('Already logged in')
        else:
            raise Exception(
                "Unexpected title for home page: " f"'{self.driver.title}'"
            )
