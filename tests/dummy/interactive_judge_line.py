import sys

# Dummy judge: read one line from user and emit a verdict line.
line = sys.stdin.readline()
if line == "hello\n":
    sys.stdout.write("PASS\n")
else:
    sys.stdout.write("FAIL\n")
sys.stdout.flush()
