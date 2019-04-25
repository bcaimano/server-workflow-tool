#  Copyright 2019 MongoDB Inc.
#
#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.
import getpass
import os
import pathlib
import pickle

import jira
import keyring


class _Config(object):
    instance = None

    # Constants
    HOME = pathlib.Path.home()
    OPT = pathlib.Path('/opt')
    CONFIG_FILE = HOME / '.config' / 'server-workflow-tool' / 'config.pickle'

    JIRA_URL = 'https://jira.mongodb.org'

    def __init__(self):
        self.git_branches = []
        self.jira_user = None
        self.jira_pwd = None

        self._jira = None

    def __getstate__(self):
        d = self.__dict__.copy()

        # Remove sensitive and unnecessary info.
        d['jira_pwd'] = None
        d['_jira'] = None

        return d

    def __setstate__(self, state):
        # Restore instance attributes.
        self.__dict__.update(state)
        self._setup_jira_credentials()

    def _setup_jira_credentials(self, reset_keyring=False):
        """
        :param reset_keyring: set to true if the user is suspected of having
                              entered the wrong password
        """
        if not self.jira_user:
            while True:
                self.jira_user = input(
                    'Please enter your Jira username (firstname.lastname): ')
                break

        if reset_keyring:
            keyring.delete_password(self.JIRA_URL, self.jira_user)

        if not self.jira_pwd:
            jira_pwd = keyring.get_password(self.JIRA_URL, self.jira_user)
            if not jira_pwd:
                jira_pwd = getpass.getpass(prompt='Please enter your Jira password: ')
            keyring.set_password(self.JIRA_URL, self.jira_user, jira_pwd)
            self.jira_pwd = jira_pwd

    @property
    def jira(self):
        """
        lazily get a jira client.
        """
        if not self._jira:
            if self.jira_user is None:
                # Probably running the workflow tool for the first time.
                self._setup_jira_credentials()

            while True:
                try:
                    _jira = jira.JIRA(
                        options={'server': self.JIRA_URL},
                        basic_auth=(self.jira_user, self.jira_pwd),
                        validate=True,
                        logging=False,
                        max_retries=0,
                        timeout=5,  # I think the unit is seconds.
                    )
                    if _jira:
                        self._jira = _jira
                        break
                except jira.exceptions.JIRAError as e:
                    if e.status_code == '403' or e.status_code == 403:
                        input('Failed to login to Jira. Please re-enter your username and '
                              'password. If this failure persists, please open a browser and login '
                              'to Jira. If that still doesn\'t work, seek help in #asdf')
                        self.jira_user = None
                        self.jira_pwd = None
                        self._setup_jira_credentials(reset_keyring=True)
                        # TODO: slack channel.
                    else:
                        raise

        return self._jira

    def dump(self):
        try:
            os.mkdir(os.path.dirname(str(self.CONFIG_FILE)))
        except FileExistsError:
            # Directory exists.
            pass

        with open(str(self.CONFIG_FILE), 'wb') as fh:
            pickle.dump(
                self,
                fh,
                protocol=pickle.HIGHEST_PROTOCOL,  # Use protocol version 4.
                fix_imports=False  # Don't support Python 2.
            )

    @staticmethod
    def load():
        if not _Config.CONFIG_FILE.exists():
            return _Config()

        with open(str(_Config.CONFIG_FILE), 'rb') as fh:
            return pickle.load(fh)


# Singleton _Config object
def Config():
    if _Config.instance is None:
        _Config.instance = _Config.load()
    return _Config.instance

