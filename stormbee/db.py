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


import MySQLdb

# Hacky code for repairing / resetting the database after (or before)
# a stormbee test run.


class DBRepairer:
    def __init__(self, config):
        self.config = config
        self.db = self._connect()
        self.db.autocommit = False
        self.user_id = self._get_user_id()

    def error_counts(self):
        """Check for errors for the stormbee test user.

        Returns a dict with error counts, or an empty dict if there are
        no errors
        """

        c = self.db.cursor()
        try:
            c.execute(
                "SELECT count(id) from vm_manager_vmstatus "
                "where status = 'VM_Error' and user_id = %s",
                (self.user_id,),
            )
            vmstatus_errors = c.fetchone()[0]
            c.execute(
                "SELECT count(id) from vm_manager_cloudresource "
                "where error_flag is not NULL and deleted is NULL "
                "and user_id = %s",
                (self.user_id,),
            )
            resource_errors = c.fetchone()[0]
        finally:
            c.close()

        if vmstatus_errors > 0 or resource_errors > 0:
            return {
                'vmstatus_errors': vmstatus_errors,
                'resource_errors': resource_errors,
            }
        else:
            return {}

    def clear_errors(self):
        """Clear any errors for the stormbee test user.

        VMStatus records are set to No_VM.  Volume and Instance records are
        marked as deleted.
        """

        c = self.db.cursor()
        try:
            c.execute(
                "update vm_manager_vmstatus set status = 'No_VM' "
                "where status = 'VM_Error' and user_id = %s",
                (self.user_id,),
            )
            # Also mark any VM_OK records for the user as No_VM so that
            # get_vm_state doesn't throw exceptions.
            c.execute(
                "update vm_manager_vmstatus set status = 'No_VM' "
                "where status = 'VM_OK' and user_id = %s",
                (self.user_id,),
            )
            c.execute(
                "update vm_manager_cloudresource set deleted = now() "
                "where error_flag is not NULL and deleted is NULL "
                "and user_id = %s",
                (self.user_id,),
            )
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e
        finally:
            c.close()

    def _get_user_id(self):
        username = self.config['BumblebeeUsername']
        c = self.db.cursor()
        try:
            c.execute(
                "SELECT id from researcher_workspace_user where "
                "username = %s",
                (username,),
            )
            row = c.fetchone()
            if row is None:
                raise Exception(f"Cannot find user {username}")
            return row[0]
        finally:
            c.close()

    def _connect(self):
        return MySQLdb.connect(
            host=self.config.get('DbHost', '127.0.0.1'),
            user=self.config.get('DbUsername', 'bumblebee'),
            password=self.config.get('DbPassword', ''),
            database=self.config.get('DbDatabase', 'bumblebee'),
            port=int(self.config.get('DbPort', '3306')),
        )
