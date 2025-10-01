"""
Broken Test Plugin for EvoNote V0.1
This plugin contains an intentional syntax error to test the PluginManager's
error handling capabilities (NFR-2).
"""

def register(app_context):
    # This line has a syntax error
    print "This is a syntax error in Python 3"
