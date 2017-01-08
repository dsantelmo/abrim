import sys
import os
import unittest
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim import node, sync


class SyncTestCase(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        sys.argv = [__name__]
        self.port_to_test = 5001

        file_format = node.app.config['DB_FILENAME_FORMAT']
        if "_test" not in file_format:
            node.app.config['DB_FILENAME_FORMAT'] += "_test"

    def tearDown(self):
        if 'DB_PATH' in node.app.config:
            try:
                os.unlink(node.app.config['DB_PATH'])
            except OSError:
                pass
        else:  # pragma: no cover
            raise Exception
        logging.disable(logging.NOTSET)

    def _standard_init(self):
        sys.argv.append('-i')
        sys.argv.append('-p')
        sys.argv.append(str(self.port_to_test))
        node._init()
        node.app.preprocess_request()

    def test_step_1_create_diff(self):
        self.assertEqual([(0, 'text '), (-1, 'shadow'), (1, 'text')],
                         sync.step_1_create_diff("text text", "text shadow", 0.1))

    def test_step_2_create_edits(self):
        self.assertEqual("""@@ -2,10 +2,8 @@
 ext """ + """
-shadow
+text
""",
                         sync.step_2_create_edits([(0, 'text '), (-1, 'shadow'), (1, 'text')]))

    def test_get_or_create_shadow(self):
        with node.app.test_request_context():
            self._standard_init()
            self.assertEqual((1, "", 0, 0,),
                             sync._get_or_create_shadow('1', '1', '1', ""))


def _main():
    unittest.main()


if __name__ == '__main__':  # pragma: no cover
    _main()
