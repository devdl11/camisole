import sys

# Dummy judge: read one line from user.
# - exit 0 means PASS
# - exit 42 means WRONG ANSWER / FAULT
line = sys.stdin.readline()
if line == "hello\n":
    sys.stdout.write("PASS\n")
    sys.stdout.flush()
    sys.exit(0)
else:
    sys.stderr.write("WRONG_ANSWER\n")
    sys.stderr.flush()
    sys.exit(42)
