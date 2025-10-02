import sys
import time
from PySide6.QtWidgets import QApplication
from core.signals import GlobalSignalBus
from plugins.completion_service import CompletionServicePlugin
from services.file_indexer_service import FileIndexerService

class HeadlessTester:
    def __init__(self):
        self.app = QApplication(sys.argv)
        # The indexer needs to run to populate the database
        self.file_indexer_service = FileIndexerService(vault_path=".")
        self.file_indexer_service.start()
        
        # Give the indexer a moment to discover and process the new files
        # Wait for the initial indexing to complete
        print("Waiting for file indexer to become idle...")
        self.file_indexer_service.wait_for_idle()

        self.completion_plugin = CompletionServicePlugin(self)
        GlobalSignalBus.completion_results_ready.connect(self.on_results)
        
        self.results = {}
        self.expected_tests = 0
        self.completed_tests = 0

    def on_results(self, completion_type, query_text, results):
        print(f"Received results for '{query_text}' ({completion_type}): {results}")
        self.results[query_text] = results
        self.completed_tests += 1
        if self.completed_tests >= self.expected_tests:
            self.app.quit()

    def run_test(self, tests):
        self.expected_tests = len(tests)
        self.completed_tests = 0
        
        for test_query in tests:
            self.current_query = test_query # This is now only for debugging if needed
            print(f"\nRequesting completion for: '{test_query}'")
            GlobalSignalBus.completion_requested.emit('page_link', test_query)
        
        self.app.exec()

    def stop_services(self):
        self.file_indexer_service.stop()

def run_all_tests():
    tester = HeadlessTester()
    
    # Define test cases
    test_queries = ["Note", "Another", "NonExistent"]
    
    tester.run_test(test_queries)
    
    # --- Verification ---
    print("\n--- Test Verification ---")
    success = True
    
    # Test case 1: "Note"
    if "Note" in tester.results and \
       set(tester.results["Note"]) == {"Note A.md", "Note B.md"}:
        print("✅ Test 'Note' PASSED")
    else:
        print(f"❌ Test 'Note' FAILED. Got: {tester.results.get('Note')}")
        success = False

    # Test case 2: "Another"
    if "Another" in tester.results and \
       set(tester.results["Another"]) == {"Another Note C.md"}:
        print("✅ Test 'Another' PASSED")
    else:
        print(f"❌ Test 'Another' FAILED. Got: {tester.results.get('Another')}")
        success = False
        
    # Test case 3: "NonExistent"
    if "NonExistent" in tester.results and \
       len(tester.results["NonExistent"]) == 0:
        print("✅ Test 'NonExistent' PASSED")
    else:
        print(f"❌ Test 'NonExistent' FAILED. Got: {tester.results.get('NonExistent')}")
        success = False

    tester.stop_services()
    return success

if __name__ == "__main__":
    if run_all_tests():
        print("\n🎉 All backend tests passed!")
        sys.exit(0)
    else:
        print("\n🔥 Some backend tests failed.")
        sys.exit(1)