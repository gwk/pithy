# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import datetime

from pithytools.bin.watch_systemd_units import (classify_record, default_since, interrupt_exit_code, level_for_priority,
  parse_message_key_specs, parse_ready_specs, parse_show_output, parse_systemd_timestamp, unit_name, UnitStatus,
  WatchSystemdUnitsCmd)
from utest import utest, utest_val


cmd = WatchSystemdUnitsCmd.parse(['webapp.service', 'worker', '-ready', 'webapp=started', '-message-key', 'webapp=message',
  '-since=-5min', '-settle=10', '-timeout', '120', '-interval', '0.5'])
utest_val(['webapp.service', 'worker'], cmd.units, 'parsed units')
utest_val(['webapp=started'], cmd.ready, 'parsed ready spec')
utest_val(['webapp=message'], cmd.message_key, 'parsed message key spec')
utest_val(('-5min', 10.0, 120.0, 0.5), (cmd.since, cmd.settle, cmd.timeout, cmd.interval), 'parsed options')

utest('webapp', unit_name, 'webapp.service')
utest('webapp', unit_name, 'webapp')

utest({'a': 'x.'}, lambda specs: {k: p.pattern for k, p in parse_ready_specs(specs).items()}, ['a.service=x.'])
utest({'a': 'message'}, parse_message_key_specs, ['a.service=message'])

show_text = '''Id=webapp.service
ActiveState=active
SubState=running
Result=success
NRestarts=0
InactiveExitTimestamp=Tue 2026-08-25 10:00:05 PDT

Id=keap-apiary.service
ActiveState=activating
SubState=auto-restart
Result=success
NRestarts=3
InactiveExitTimestamp=Tue 2026-08-25 10:00:02 PDT
'''
show = parse_show_output(show_text)
utest_val(['webapp', 'keap-apiary'], list(show), 'parsed unit names')
utest_val('auto-restart', show['keap-apiary']['SubState'], 'parsed property')

utest(datetime(2026, 8, 25, 10, 0, 5), parse_systemd_timestamp, 'Tue 2026-08-25 10:00:05 PDT')
utest(None, parse_systemd_timestamp, 'n/a')
utest(None, parse_systemd_timestamp, '')

utest('2026-08-25 10:00:01', default_since, show) # One second before the earliest start.
utest('-1min', default_since, {'x': {'InactiveExitTimestamp': 'n/a'}})

utest('error', level_for_priority, '3')
utest('warn', level_for_priority, 4)
utest('info', level_for_priority, '6')
utest('info', level_for_priority, None)


# Record classification.

e = classify_record({'_SYSTEMD_UNIT': 'webapp.service', 'PRIORITY': '6', 'MESSAGE': '{"level":"warn","_":"slow","ms":900}'})
utest_val(('webapp', 'info', 'slow'), (e.unit, e.kind, e.msg), 'journal priority overrides pithy json level')

e = classify_record({'_SYSTEMD_UNIT': 'webapp.service', 'PRIORITY': '3', 'MESSAGE': '{"level":"error","_":"boom"}'})
utest_val(('webapp', 'error', 'boom'), (e.unit, e.kind, e.msg), 'pithy json error')

e = classify_record({'_SYSTEMD_UNIT': 'webapp.service', 'PRIORITY': '6', 'MESSAGE': '{"message":"started"}'},
  message_keys={'webapp': 'message'})
utest_val(('started', True), (e.msg, 'started' in e.text), 'custom message key')

e = classify_record({'_SYSTEMD_UNIT': 'vector.service', 'PRIORITY': '3', 'MESSAGE': 'sink failed'})
utest_val(('vector', 'error', 'sink failed'), (e.unit, e.kind, e.msg), 'plain error by priority')

e = classify_record({'_SYSTEMD_UNIT': 'vector.service', 'PRIORITY': '6', 'MESSAGE': 'hello'})
utest_val(('vector', 'info'), (e.unit, e.kind), 'plain info')

e = classify_record({'_SYSTEMD_UNIT': 'init.scope', 'UNIT': 'keap-apiary.service', 'PRIORITY': '6',
  'EXIT_CODE': 'exited', 'EXIT_STATUS': '0', 'MESSAGE': 'Deactivated successfully.'})
utest_val(('keap-apiary', 'exit', True), (e.unit, e.kind, e.ok), 'clean exit')

e = classify_record({'_SYSTEMD_UNIT': 'init.scope', 'UNIT': 'keap-apiary.service', 'PRIORITY': '5',
  'EXIT_CODE': 'exited', 'EXIT_STATUS': '1', 'MESSAGE': 'Main process exited, code=exited, status=1/FAILURE'})
utest_val(('keap-apiary', 'exit', False), (e.unit, e.kind, e.ok), 'failed exit')

e = classify_record({'UNIT': 'webapp.service', 'JOB_TYPE': 'start', 'JOB_RESULT': 'failed', 'MESSAGE': 'Failed to start Web app.'})
utest_val(('webapp', 'fail'), (e.unit, e.kind), 'failed job')

e = classify_record({'UNIT': 'webapp.service', 'JOB_TYPE': 'start', 'JOB_RESULT': 'done', 'MESSAGE': 'Started Web app.'})
utest_val(('webapp', 'info'), (e.unit, e.kind), 'done job')

e = classify_record({'_SYSTEMD_UNIT': 'webapp.service', 'MESSAGE': [104, 105]})
utest_val('hi', e.msg, 'byte array message')


# Unit status from polled properties.

u = UnitStatus(name='webapp')
utest_val([], u.update_from_show({'ActiveState': 'activating', 'SubState': 'start', 'Result': 'success', 'NRestarts': '0'}), 'not yet')
utest_val(False, u.is_ready, 'not ready while activating')
utest_val([], u.update_from_show({'ActiveState': 'active', 'SubState': 'running', 'Result': 'success', 'NRestarts': '0'}), 'active')
utest_val(True, u.is_ready, 'ready when active without a pattern')
utest_val(['result: exit-code'], u.update_from_show({'ActiveState': 'activating', 'SubState': 'auto-restart', 'Result': 'exit-code', 'NRestarts': '1'}), 'crash')
utest_val([], u.update_from_show({'ActiveState': 'activating', 'SubState': 'auto-restart', 'Result': 'exit-code', 'NRestarts': '1'}), 'crash reported once')
utest_val(True, u.is_failed, 'failed')


# Interrupt exit status.

ready = UnitStatus(name='ready', ready_time=0)
waiting = UnitStatus(name='waiting')
failed = UnitStatus(name='failed', failures=['failed'])
errored = UnitStatus(name='errored', ready_time=0, errors=1)
utest(0, interrupt_exit_code, [ready])
utest(130, interrupt_exit_code, [ready, waiting])
utest(1, interrupt_exit_code, [ready, failed])
utest(1, interrupt_exit_code, [ready, waiting, errored])
