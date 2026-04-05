import pytest

import camisole.schema


def validate_schema(obj, schema):
    try:
        camisole.schema.validate_schema(obj, schema)
        return True
    except camisole.schema.ValidationError as e:
        print(e)
        return False


def test_schema_empty():
    assert validate_schema({}, {})


def test_schema_simple():
    s = {'a': int}
    assert validate_schema({'a': 1}, s)
    assert not validate_schema({}, s)
    assert not validate_schema({'a': 1.2}, s)
    assert not validate_schema({'a': 'b'}, s)


def test_schema_optional():
    from camisole.schema import O
    s = {'a': O(int)}
    assert validate_schema({}, s)
    assert validate_schema({'a': 1}, s)
    assert validate_schema({'a': None}, s)


def test_schema_union():
    from camisole.schema import Union
    s = {'a': Union(int, str)}
    assert validate_schema({'a': 1}, s)
    assert validate_schema({'a': 'b'}, s)
    assert not validate_schema({}, s)
    assert not validate_schema({'a': 1.1}, s)


def test_schema_list():
    s = {'a': [int]}
    assert validate_schema({'a': []}, s)
    assert validate_schema({'a': [1]}, s)
    assert validate_schema({'a': [1, 2, 3]}, s)
    assert not validate_schema({'a': [1, 2, 'b']}, s)
    assert not validate_schema({'a': 42}, s)


def test_schema_nested():
    s = {'a': {'b': [{'c': int}]}}
    assert validate_schema({'a': {'b': []}}, s)
    assert validate_schema({'a': {'b': [{'c': 1}, {'c': 2}]}}, s)
    assert not validate_schema({'a': {'b': [{'c': 1}, {'c': None}]}}, s)
    assert not validate_schema({'a': [1, 2]}, s)


def test_correct_simple():
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'tests': [{}],
    }
    camisole.schema.validate_run(json)


def test_correct_complex():
    json = {
        'lang': 'c',
        'source': '''
#include <stdio.h>
int main(void) {
    printf("42\n");
    return 0;
}''',
        'execute': {
            'fsize': 19,
            'time': 78,
            'wall-time': 404,
            'extra-time': 1.0,
            'quota': '1,8',
            'mem': 1337,
            'processes': 42,
        },
        'compile': {
            'quota': '1,8',
            'processes': 27,
            'fsize': 19,
            'mem': 44444444,
            'time': 546546,
            'wall-time': 200,
        },
        'tests': [
            {
                'name': 'test01',
                'stdin': '4224242422',
                'mem': 44444444,
            },
            {
                'quota': '1,8',
                'processes': 27,
                'fsize': 19,
                'mem': 44444444,
                'time': 546546,
                'wall-time': 200,
                'extra-time': 0.5,
            },
            {},
        ],
    }
    camisole.schema.validate_run(json)


def test_bad_type():
    json = {
        'lang': 'python',
        'source': 42,
    }
    with pytest.raises(camisole.schema.ValidationError) as e:
        camisole.schema.validate_run(json)
    assert "expected a string or binary data, got an integer" in str(e)


def test_extra_time():
    # extra-time can be set at execute, compile, and per-test levels
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'compile': {'extra-time': 2},
        'execute': {'extra-time': 1.5},
        'tests': [{'extra-time': 0.5}],
    }
    camisole.schema.validate_run(json)


def test_extra_time_bad_type():
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'execute': {'extra-time': 'not-a-number'},
    }
    with pytest.raises(camisole.schema.ValidationError):
        camisole.schema.validate_run(json)


def test_missing_field():
    json = {
        'source': 'print(42)',
    }
    with pytest.raises(camisole.schema.ValidationError) as e:
        camisole.schema.validate_run(json)
    assert "expected a string, got nothing" in str(e)


def test_per_test_user_execution():
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'tests': [
            {
                'name': 'test01',
                'stdin': 'hello',
                'user_execution': {
                    'time': 2.0,
                    'mem': 128000000,
                    'wall-time': 5.0,
                },
            },
        ],
    }
    camisole.schema.validate_run(json)


def test_per_test_judge_execution():
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'judge_source': 'import sys; sys.exit(0)',
        'judge_lang': 'python',
        'tests': [
            {
                'name': 'test01',
                'judge_execution': {
                    'time': 10.0,
                    'mem': 256000000,
                },
            },
        ],
    }
    camisole.schema.validate_run(json)


def test_per_test_user_and_judge_execution():
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'judge_source': 'import sys; sys.exit(0)',
        'judge_lang': 'python',
        'tests': [
            {
                'name': 'test01',
                'user_execution': {
                    'time': 2.0,
                    'mem': 64000000,
                },
                'judge_execution': {
                    'time': 10.0,
                    'mem': 256000000,
                    'processes': 1,
                },
            },
        ],
    }
    camisole.schema.validate_run(json)


def test_per_test_execution_bad_type():
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'tests': [
            {
                'user_execution': {
                    'time': 'not-a-number',
                },
            },
        ],
    }
    with pytest.raises(camisole.schema.ValidationError):
        camisole.schema.validate_run(json)


def test_per_test_judge_execution_bad_type():
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'tests': [
            {
                'judge_execution': {
                    'mem': 'not-an-int',
                },
            },
        ],
    }
    with pytest.raises(camisole.schema.ValidationError):
        camisole.schema.validate_run(json)


def test_interactive_initial_stdin_fields():
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'judge_source': 'import sys; sys.exit(0)',
        'judge_lang': 'python',
        'stdin_user': 'seed-for-user',
        'stdin_judge': 'seed-for-judge',
        'execute': {
            'stdin_user': 'default-user-seed',
            'stdin_judge': 'default-judge-seed',
        },
        'tests': [
            {
                'stdin_user': 'test-user-seed',
                'stdin_judge': 'test-judge-seed',
            },
        ],
    }
    camisole.schema.validate_run(json)


def test_interactive_initial_stdin_bad_type():
    json = {
        'lang': 'python',
        'source': 'print(42)',
        'judge_source': 'import sys; sys.exit(0)',
        'judge_lang': 'python',
        'stdin_judge': 123,
    }
    with pytest.raises(camisole.schema.ValidationError):
        camisole.schema.validate_run(json)
