import os
import sys
from pathlib import Path

from abrim.util import get_log
from datastore import DataStore

log = get_log('critical')


class Config(object):
    def load_config(self):
        name = "Abrim"
        author = "DST"

        if sys.platform == 'darwin':
            self.config_folder_path = "~/Library/Application Support/{}".format(name, )
        elif sys.platform == 'win32':
            try:
                appdata = os.environ['APPDATA']
                self.config_folder_path = "{}/{}/{}".format(appdata, author, name, )
            except KeyError:
                log.error("I think this is a Windows OS and %APPDATA% variable is missing")
                raise
        else:
            self.config_folder_path = "~/.config/{}".format(name, )

        self.config_folder = Path(self.config_folder_path)
        self.config_file_path = self.config_folder / "abrim_config.ini"

        if self.config_file_path.exists():
            log.debug("trying to load config from {}".format(self.config_file_path, ))
            # create node id if it doesn't exist
            # node_id = uuid.uuid4().hex
            raise Exception  # FIXME: add configparser
        else:
            log.debug("no config file, checking environment variable")
            try:
                self.node_id = os.environ['ABRIM_NODE_ID']
            except KeyError:
                log.error("can't locate NODE_ID value")
                raise

    def __init__(self, node_id, port, db_prefix="", drop_db=False):
        if not node_id:
            self.load_config()
        else:
            self.node_id = node_id
        self.db = DataStore(self.node_id, port, db_prefix, drop_db)
        self.edit_queue_limit = 50
