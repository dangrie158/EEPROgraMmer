import doctest
import unittest

import eepro

suite = unittest.TestSuite()
suite.addTest(doctest.DocTestSuite(eepro))

runner = unittest.TextTestRunner(verbosity=2)
runner.run(suite)
