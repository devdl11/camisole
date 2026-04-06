class ValidationError(ValueError):
    def __init__(self, path, msg):
        self.path = path
        self.msg = msg
        super().__init__(str(self))

    def __str__(self):
        return f"{self.path}: {self.msg}"


class O:
    """Optional."""

    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __repr__(self):
        return f"O[{self.wrapped}]"


class Union:
    """Any of."""

    def __init__(self, *wrapped):
        self.wrapped = wrapped

    def __repr__(self):
        return f"Union[{self.wrapped}]"


def human_type_name(cls):
    return {
        bytes: "binary data",
        int: "an integer",
        str: "a string",
        type(None): "nothing",
    }.get(cls, f"a {cls.__name__}")


def validate_schema(obj, schema: dict) -> None:
    """ Validate that obj matches a given schema. Raises ValidationError if not.

    Args:
        obj(object): object to validate
        schema (dict): schema to validate against

    Raises:
        ValidationError: if obj does not match the schema, with a message describing the error
    """

    htn = human_type_name

    def explore(obj, schema, path):
        if isinstance(schema, O):
            if obj is None:
                return
            explore(obj, schema.wrapped, path)

        elif isinstance(schema, Union):
            for subtype in schema.wrapped:
                try:
                    explore(obj, subtype, path)
                    # one of the types is OK, early stop
                    return
                except ValidationError:
                    pass
            expected = ' or '.join(htn(s) for s in schema.wrapped)
            raise ValidationError(
                path, f"expected {expected}, got {htn(obj.__class__)}")

        elif isinstance(schema, list):
            subtype, = schema
            try:
                for i, item in enumerate(obj):
                    explore(item, subtype, f'{path}[{i}]')
            except TypeError:
                raise ValidationError(
                    path, f"expected a list, got {htn(obj.__class__)}")

        elif isinstance(schema, tuple):
            try:
                for i, item in enumerate(obj):
                    explore(item, schema[i], f'{path}[{i}]')
            except TypeError:
                raise ValidationError(
                    path, f"expected a list, got {htn(obj.__class__)}")

        elif isinstance(schema, dict):
            try:
                for key, subtype in schema.items():
                    explore(obj.get(key), subtype, f'{path}.{key}')
            except ValidationError:
                raise
            except Exception:
                raise ValidationError(
                    path, f"expected a mapping, got {htn(obj.__class__)}")

        elif not isinstance(obj, schema):
            raise ValidationError(
                path, f"expected {htn(schema)}, got {htn(obj.__class__)}")

    explore(obj, schema, '')


str_bytes = Union(str, bytes)
number = Union(float, int)

ISOLATE_OPTS_PROPERTIES = {
    'extra-time': O(number),
    'fsize': O(int),
    'mem': O(int),
    'processes': O(int),
    'quota': O(str),
    'stack': O(int),
    'time': O(number),
    'virt-mem': O(int),
    'wall-time': O(number),
}


# Request-level judge configuration (defines judge code to use for all tests)
JUDGE_REQUEST_PROPERTIES = {
    'judge_source': O(str_bytes),  # judge program source code
    'judge_lang': O(str),          # judge program language
    'judge_compile': O(ISOLATE_OPTS_PROPERTIES),  # isolate options for judge compilation
    'judge_fault_exitcode': O(int),  # custom judge exit code meaning WRONG ANSWER / FAULT
}


# Firewall rules for user → judge I/O filtering
FIREWALL_PROPERTIES = {
    'allowed_chars': O(str),      # regex pattern for allowed characters
    'max_line_length': O(int),    # max bytes per line
    'max_total_bytes': O(int),    # max total bytes user can send
    'format_rules': O([str]),     # custom validator names
    'violation_action': O(str),   # 'STOP' or 'WARN'
}

# Test-level judge configuration (enables judge for a specific test)
JUDGE_TEST_PROPERTIES = {
    'judge': O(bool),  # whether to use judge for this test
    'stdin_judge': O(str_bytes),
    'firewall_rules': O(FIREWALL_PROPERTIES),  # filtering rules for user → judge I/O
    'judge_execution': O(ISOLATE_OPTS_PROPERTIES),  # per-test isolate limits for judge code
}

EXECUTE_PROPERTIES = {
    **ISOLATE_OPTS_PROPERTIES,
}

TEST_PROPERTIES = {
    'name': O(str),
    'fatal': O(bool),
    'stdin': O(str_bytes),
    'user_execution': O(ISOLATE_OPTS_PROPERTIES),  # per-test isolate limits for user code
    'judge': O(JUDGE_TEST_PROPERTIES),
    'expected': O(str_bytes),
}

RUN_SCHEMA = {
    'lang': str,
    'source': str_bytes,
    'all_fatal': O(bool),
    'compile': O(ISOLATE_OPTS_PROPERTIES),
    'execute': O(EXECUTE_PROPERTIES),
    **JUDGE_REQUEST_PROPERTIES,  # request-level judge config
    'tests': O([TEST_PROPERTIES]),
}


def validate_run(json):
    validate_schema(json, RUN_SCHEMA)
