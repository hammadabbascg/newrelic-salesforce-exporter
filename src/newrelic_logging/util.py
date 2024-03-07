from datetime import datetime, timedelta
import hashlib
import pytz

def is_logfile_response(records):
    if len(records) > 0:
        return 'LogFile' in records[0]
    else:
        return True


def get_row_timestamp(row):
    epoch = row.get('TIMESTAMP')

    if epoch:
        return pytz.utc.localize(
            datetime.strptime(epoch, '%Y%m%d%H%M%S.%f')
        ).replace(microsecond=0).timestamp()

    return datetime.utcnow().replace(microsecond=0).timestamp()


def generate_record_id(id_keys: list[str], row: dict) -> str:
    compound_id = ''
    for key in id_keys:
        if key not in row:
            raise Exception(
                f'error building compound id, key \'{key}\' not found'
            )

        compound_id = compound_id + str(row.get(key, ''))

    if compound_id != '':
        m = hashlib.sha3_256()
        m.update(compound_id.encode('utf-8'))
        return m.hexdigest()

    return ''


# NOTE: this sandbox can be jailbroken using the trick to exec statements inside
# an exec block, and run an import (and other tricks):
# https://book.hacktricks.xyz/generic-methodologies-and-resources/python/bypass-python-sandboxes#operators-and-short-tricks
# https://stackoverflow.com/a/3068475/2076108
# Would be better to use a real sandbox like
# https://pypi.org/project/RestrictedPython/ or https://doc.pypy.org/en/latest/sandbox.html
# or parse a small language that only supports funcion calls and binary
# expressions.
#
# @TODO See if we can do this a different way We shouldn't be executing eval ever.

def sandbox(code):
    __import__ = None
    __loader__ = None
    __build_class__ = None
    exec = None


    def sf_time(t: datetime):
        return t.isoformat(timespec='milliseconds') + "Z"

    def now(delta: timedelta = None):
        if delta:
            return sf_time(datetime.utcnow() + delta)
        else:
            return sf_time(datetime.utcnow())

    try:
        return eval(code)
    except Exception as e:
        return e


def substitute(args: dict, template: str, env: dict) -> str:
    for key, command in env.items():
        args[key] = sandbox(command)
    for key, val in args.items():
        template = template.replace('{' + key + '}', val)
    return template
