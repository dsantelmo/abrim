import os
import abrim
import unittest
import tempfile

class FlaskrTestCase(unittest.TestCase):

    def setUp(self):
        # self.db_fd, flaskr.app.config['DB_SCHEMA_PATH'] = tempfile.mkstemp()
        abrim.app.config['TESTING'] = True
        self.app = abrim.app.test_client()
        #with flaskr.app.app_context():
        #    flaskr.init_db()

    def tearDown(self):
        # os.close(self.db_fd)
        # os.unlink(flaskr.app.config['DATABASE'])
        pass

if __name__ == '__main__':
    unittest.main()