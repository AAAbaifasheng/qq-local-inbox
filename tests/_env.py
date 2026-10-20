import os
import tempfile

# Force a throwaway data directory even if the caller has QQLI_DATA_DIR set to
# a real profile. Import this before any src module that resolves DB_PATH.
os.environ["QQLI_DATA_DIR"] = tempfile.mkdtemp(prefix="qqli-test-")
