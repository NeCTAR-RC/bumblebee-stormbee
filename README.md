# Stormbee - the Bumblebee test tool

Stormbee is a command line tool designed primarily for running Selenium-based
scenarios tests against various Bumblebee sites.

## Installation and dependencies

The installation prerequisites for Stormbee are Firefox, Xvfb, libxi6
and libgconf-2-4.

You can then install it by running "pip3 install -e ."

## Config file

Details of the sites that can be tested are read from an INI file whose default
location is "$HOME/.bumblebee.ini".  (You can use the '-c' option to specify a
different location.)  Each site is represented by a section in the file.  The
standard Python config defaulting mechanisms apply.  The config file needs to
specify user credentials for running the tests.

There is a template for the config file in ./stormbee.ini.sample.  Copy it to
the expected location and edit it to add details for your Bumblebee site(s).

## Usage

`<name> [-d] [-c config] [-s site] <action>`

where <action> is one of:

- `status` - show the status us the user's desktop
- `launch` - launch a desktop
- `boost` - boost the desktop
- `downsize` - downsize the desktop
- `shelve` - shelve the desktop
- `unshelve` - unshelve the desktop
- `reboot` - reboot the desktop
- `delete` - delete the desktop

The '-d' option enables debug logging.  The other options allow you to select
the Bumblebee site to run against, and give an alternative location for the
config file.

## Login

The command currently has two ways of authenticating the test user prior to
running any tests.

### Classic mode

In 'classic' mode, the Bumblebee instance provides its own login form that
we fill in and submit.  This form may be hidden so that normal users don't
try to log in that way.  The selenium script looks for a `<form>` with `id`
of `kc-form-login`, unhides it if necessary, fills it in and submits it.

The server needs to be run with `USE_OIDC=False` in the shell environment.
The command told to use this mode by setting `UseOIDC = False` in the site's
section of the config file.

### OIDC mode

In 'OIDC' mode, the Bumblebee instance relies on a KeyCloak server to do
its authentication.  The standard KeyCloak login page  has a form that
we fill in and submit.

The server needs to be run with `USE_OIDC=True` in the shell environment.
The command is told to use this mode by setting `UseOIDC = True` in the site's
section of the config file.

### Account setup

In the Classic case, you need to use either Django `manage.py` or the site
Admin commands to create the User object and set the user's password.

In the OIDC case, the account needs to be created and suitably configured in
your Keycloak server.

In both cases, the test account then needs to go through the standard
Bumblebee new user sequence.  The 'user' needs to have agreed to the
Terms of Service, and created their Project.  This tool does not deal
with this:

  - In the Classic case, simply login as the test user from your web browser
    and go through the procedure.
  - In the OIDC case, you need to use your browser's dev tools to unhide
    the Keycloak username / password form in your browser so that you can
    login.  (Look for a `<form>` element with `id="kc-form-login"`.)
    Once you are logged in, go through the procedure.
