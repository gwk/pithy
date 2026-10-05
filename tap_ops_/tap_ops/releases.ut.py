# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tap_ops.releases import (CheckReleases, Component, components, describe, installed_version, parse_python_release,
  parse_python_sha256, parse_release_digests, parse_sqlite_products, parse_tags, python_versions, read_versions, report,
  sqlite_product_header, Upstream, version_key)
from utest import utest, utest_exc, utest_run, utest_val


py_pattern = r'v(\d+\.\d+\.\d+)'
sha_a = 'a' * 64
sha_b = 'b' * 64

utest(True, lambda: version_key('0.100.0') > version_key('0.99.9'))
utest(True, lambda: version_key('3.53.3.1') > version_key('3.53.3'))
ordered_python_versions = ['3.14.9', '3.15.0a2', '3.15.0a10', '3.15.0b1', '3.15.0rc2',
  '3.15.0rc3', '3.15.0rc10', '3.15.0', '3.15.1']
utest(ordered_python_versions, sorted, reversed(ordered_python_versions), key=version_key)
for invalid in ('v3.15.0rc3', '3.15.0rc', '3.15.0dev1'):
  utest_exc(ValueError, version_key, invalid)
utest({'3.14.7', '3.15.0'}, parse_tags,
  'abc refs/tags/v3.14.7\nabc refs/tags/v3.14.7^{}\nabc refs/tags/v3.15.0rc1\nabc refs/tags/v3.15.0\n', py_pattern)
utest({'0.58.0'}, parse_tags, 'abc refs/tags/v0.58.0\nabc refs/tags/vdev-v0.3.24\nabc refs/tags/v0.59.0-rc.1\n', py_pattern)
utest_exc(ValueError, parse_tags, 'unexpected response body', py_pattern)


@utest_run
def test_release_digests() -> None:
  names = {'uv_sha256_linux_x86_64': 'uv-x86_64-unknown-linux-gnu.tar.gz',
    'uv_sha256_linux_aarch64': 'uv-aarch64-unknown-linux-gnu.tar.gz'}
  assets = [
    dict(name='uv-x86_64-unknown-linux-gnu.tar.gz', digest=f'sha256:{sha_a}'),
    dict(name='uv-aarch64-unknown-linux-gnu.tar.gz', digest=f'sha256:{sha_b}'),
    dict(name='uv-x86_64-unknown-linux-gnu.tar.gz.sha256', digest=f'sha256:{"c" * 64}')]
  release = dict(tag_name='0.12.19', draft=False, prerelease=False, assets=assets)
  utest({'uv_sha256_linux_x86_64': sha_a, 'uv_sha256_linux_aarch64': sha_b}, parse_release_digests, release, names)
  utest_exc(ValueError, parse_release_digests, {**release, 'prerelease': True}, names)
  utest_exc(ValueError, parse_release_digests, {**release, 'assets': assets[:1]}, names)
  utest_exc(ValueError, parse_release_digests, {**release, 'assets': [dict(name=assets[0]['name'], digest='md5:abc')]}, names)
  utest_exc(ValueError, parse_release_digests, {'message': 'rate limited'}, names)


@utest_run
def test_github_tool() -> None:
  tags = 'abc refs/tags/v0.58.0\nabc refs/tags/v0.59.0\nabc refs/tags/vdev-v0.3.24\n'
  assets = [dict(name=f'vector-0.59.0-{arch}-unknown-linux-gnu.tar.gz', digest=f'sha256:{sha}')
    for arch, sha in (('x86_64', sha_a), ('aarch64', sha_b))]
  assets.append(dict(name='vector-0.59.0-arm64-apple-darwin.tar.gz', digest=f'sha256:{"c" * 64}'))
  release = dict(tag_name='v0.59.0', draft=False, prerelease=False, assets=assets)
  proc = patch('tap_ops.releases.run', return_value=type('Proc', (), {'stdout': tags})())
  with proc, patch('tap_ops.releases.github_json', return_value=release) as request:
    expected = Upstream({'0.58.0', '0.59.0'},
      {'vector_version': '0.59.0', 'vector_sha256_linux_x86_64': sha_a, 'vector_sha256_linux_aarch64': sha_b,
       'vector_sha256_macos_arm64': 'c' * 64})
    utest(expected, components[2].lookup, '0.58.0')
    assert request.call_args.args[0].endswith('/releases/tags/v0.59.0')
    # No release fetch when nothing is newer.
    utest(Upstream({'0.58.0', '0.59.0'}), components[2].lookup, '0.59.0')
    utest_val(1, request.call_count)
  with proc, patch('tap_ops.releases.github_json', return_value=None):
    upstream = components[2].lookup('0.58.0')
    utest_val({}, upstream.values)
    assert 'no published release' in upstream.note
    assert 'no published release' in '\n'.join(describe(components[2], {components[2].variable: '0.58.0'}, upstream, '0.58.0'))
  with patch('tap_ops.releases.run', return_value=type('Proc', (), {'stdout': 'abc refs/tags/vdev-v0.3.24\n'})()):
    utest_exc(ValueError, components[2].lookup, '0.58.0')


@utest_run
def test_python() -> None:
  release = [dict(name='Python 3.14.8', is_published=True, pre_release=False,
    resource_uri='https://www.python.org/api/v2/downloads/release/1117/')]
  utest(1117, parse_python_release, release, '3.14.8')
  utest(None, parse_python_release, release, '3.14.9')
  utest(None, parse_python_release, [{**release[0], 'is_published': False}], '3.14.8')
  utest_exc(ValueError, parse_python_release, [{**release[0], 'resource_uri': None}], '3.14.8')
  utest_exc(ValueError, parse_python_release, {'detail': 'error'}, '3.14.8')
  files = [
    dict(name='Gzipped source tarball', url='https://www.python.org/ftp/python/3.14.8/Python-3.14.8.tgz', sha256_sum='e' * 64),
    dict(name='XZ compressed source tarball', url='https://www.python.org/ftp/python/3.14.8/Python-3.14.8.tar.xz',
      sha256_sum=sha_a.upper())]
  utest(sha_a, parse_python_sha256, files, '3.14.8')
  utest_exc(ValueError, parse_python_sha256, files[:1], '3.14.8')
  utest_exc(ValueError, parse_python_sha256, [{**files[1], 'sha256_sum': ''}], '3.14.8')
  tags = ('abc refs/tags/v3.13.99\nabc refs/tags/v3.14.7\nabc refs/tags/v3.14.8\nabc refs/tags/v3.15.0\n'
    'abc refs/tags/v3.15.0rc1\n')
  proc = patch('tap_ops.releases.run', return_value=type('Proc', (), {'stdout': tags})())
  with proc, patch('tap_ops.releases.fetch_json', side_effect=[release, files]) as request:
    upstream = python_versions('3.14.7')
    utest_val({'py_point_version': '3.14.8', 'py_sha256': sha_a}, upstream.values)
    assert request.call_args_list[0].args[0].endswith('/release/?name=Python%203.14.8')
    assert request.call_args_list[1].args[0].endswith('/release_file/?release=1117')
    lines = describe(components[0], {components[0].variable: '3.14.7'}, upstream, '3.14.7')
    assert any('New patch tag' in line and '3.14.8' in line for line in lines)
    assert any('New major/minor series: 3.15.0' in line for line in lines)
    assert "  py_point_version='3.14.8'" in lines
    # A new series alone yields no values and no requests.
    utest(Upstream({'3.13.99', '3.14.7', '3.14.8', '3.15.0'}), python_versions, '3.14.8')
    utest_val(2, request.call_count)
  with proc, patch('tap_ops.releases.fetch_json', return_value=[]):
    assert 'no published release' in python_versions('3.14.7').note
  with patch('tap_ops.releases.run', return_value=type('Proc', (), {'stdout': 'abc refs/tags/v3.15.0\n'})()):
    utest_exc(ValueError, python_versions, '3.14.7')
  utest_exc(ValueError, describe, components[0], {'py_point_version': '3.14.7'}, Upstream(set()), '3.14.7')
  assert 'verify upstream version' in describe(components[1], {components[1].variable: '3.53.3'}, Upstream({'3.53.2'}), '3.53.3')[0]


@utest_run
def test_sqlite_products() -> None:
  sha3 = 'b834d474b9b393d85a9e3ee4cc11f1329e007e9376a424ee740796f5c4bda3a8'
  page = f'''<html>
<!-- Download product data for scripts to read
{sqlite_product_header}
PRODUCT,2026-07-31 22:45 UTC,snapshot/sqlite-snapshot-202607312245.tar.gz,3312178,{'f' * 64}
PRODUCT,3.53.4,2026/sqlite-src-3530400.zip,14557315,{sha3}
PRODUCT,3.53.4,2026/sqlite-amalgamation-3530400.zip,2946650,{'e' * 64}
-->
'''
  expected = Upstream({'3.53.4'},
    {'sqlite_version': '3.53.4', 'sqlite_zip_remote_path': '2026/sqlite-src-3530400.zip', 'sqlite_sha3': sha3})
  utest(expected, parse_sqlite_products, page)
  utest_exc(ValueError, parse_sqlite_products, '<html>no table</html>')
  utest_exc(ValueError, parse_sqlite_products,
    f'{sqlite_product_header}\nPRODUCT,3.53.4,2026/sqlite-doc-3530400.zip,1,{sha3}\n')
  utest_exc(ValueError, parse_sqlite_products, f'{sqlite_product_header}\nPRODUCT,3.53.4,2026/sqlite-src-3530400.zip,1,bad\n')
  utest_exc(ValueError, parse_sqlite_products, f'{sqlite_product_header}\nPRODUCT,3.53.4,2026/sqlite-src-3530400.zip\n')
  lines = describe(components[1], {components[1].variable: '3.53.3'}, expected, '3.53.3')
  assert 'review and approve 3.53.4' in lines[0]
  assert f"  sqlite_sha3='{sha3}'" in lines


@utest_run
def test_literal_versions() -> None:
  base = "py_point_version='3.14.7'\nsqlite_version='3.53.3'\nvector_version='0.58.0'\nuv_version=\"0.11.31\" # Comment.\n"
  with TemporaryDirectory() as temp:
    path = Path(temp) / 'versions.sh'
    path.write_text(base)
    utest_val('3.14.7', read_versions(path)['py_point_version'])
    path.write_text(base.replace('3.14.7', '3.15.0rc3'))
    utest_val('3.15.0rc3', read_versions(path)['py_point_version'])
    for extra in ['uv_version="0.11.32"\n', 'other=$(touch marker)\n', 'source other.sh\n']:
      path.write_text(base + extra)
      utest_exc(ValueError, read_versions, path)
    path.write_text('py_point_version="3.14.7"\n')
    utest_exc(ValueError, read_versions, path)


@utest_run
def test_failure_does_not_skip_other_components() -> None:
  values = dict(py_point_version='3.14.7', sqlite_version='3.53.3', vector_version='0.58.0', uv_version='0.11.31')
  def fail(approved:str) -> Upstream: raise OSError('offline')
  def found(approved:str) -> Upstream: return Upstream({approved})
  fakes = tuple(Component(c.name, c.variable, c.executable, fail if c.name == 'SQLite' else found, c.review_url)
    for c in components)
  out, err = StringIO(), StringIO()
  with redirect_stdout(out), patch('tap_ops.releases.stderr', err), patch('tap_ops.releases.installed_version', return_value=None):
    utest(False, report, values, fakes)
  assert 'SQLite: lookup failed' in err.getvalue()
  for name in ('Python:', 'Vector:', 'uv:'): assert name in out.getvalue()


utest('ops/versions.sh', lambda: CheckReleases.parse([]).versions)
utest('/tmp/versions.sh', lambda: CheckReleases.parse(['-versions', '/tmp/versions.sh']).versions)


@utest_run
def test_installed_versions() -> None:
  outputs = ('Python 3.14.7\n', '3.53.4 2026-09-01 hash (64-bit)\n', 'vector 0.58.0 (arch revision date)\n',
    'uv 0.11.31 (revision date)\n')
  versions = ('3.14.7', '3.53.4', '0.58.0', '0.11.31')
  for component, output, version in zip(components, outputs, versions):
    with patch('tap_ops.releases.run', return_value=CompletedProcess([], 0, stdout=output)) as command:
      utest(version, installed_version, component)
      command.assert_called_once_with([component.executable, '--version'],
        capture_output=True, text=True, timeout=10, check=True)
  with patch('tap_ops.releases.run', side_effect=FileNotFoundError):
    utest(None, installed_version, components[2])
  for exc in (CalledProcessError(1, 'vector'), TimeoutExpired('vector', 10)):
    with patch('tap_ops.releases.run', side_effect=exc):
      utest_exc(type(exc), installed_version, components[2])
  with patch('tap_ops.releases.run', return_value=CompletedProcess([], 0, stdout='unexpected output')):
    utest_exc(ValueError, installed_version, components[0])
  with patch('tap_ops.releases.run', return_value=CompletedProcess([], 0, stdout='Python 3.15.0rc1\n')):
    utest('3.15.0rc1', installed_version, components[0])


@utest_run
def test_review_url() -> None:
  component = components[3]
  for installed, approved, latest in (
    ('0.11.31', '0.11.31', '0.11.31'),
    ('0.11.30', '0.11.31', '0.11.31'),
    ('0.11.32', '0.11.31', '0.11.31'),
    ('0.11.31', '0.11.31', '0.11.32'),
    ('0.11.32', '0.11.31', '0.11.32'),
    ('0.11.31', '0.11.32', '0.11.31'),
    (None, '0.11.31', '0.11.31'),
  ):
    lines = describe(component, {component.variable: approved}, Upstream({latest}), installed)
    assert f'installed {installed or "none"}; approved {approved}; latest {latest}' in lines[0]
    utest_val(approved != latest, component.review_url in '\n'.join(lines))


@utest_run
def test_actions_and_changed_assignments() -> None:
  component = components[1]
  values = {'sqlite_version': '3.53.4', 'sqlite_zip_remote_path': '2026/sqlite-src-3530400.zip', 'sqlite_sha3': sha_a}
  upstream = Upstream({'3.53.4'}, values)
  utest(['SQLite: installed 3.53.4; approved 3.53.4; latest 3.53.4.'],
    describe, component, values, upstream, '3.53.4')
  lines = describe(component, values, upstream, '3.53.3')
  utest_val('SQLite: installed 3.53.3; approved 3.53.4; latest 3.53.4; update installation to 3.53.4.', lines[0])
  utest_val(1, len(lines))
  lines = describe(component, {**values, 'sqlite_sha3': sha_b}, upstream, '3.53.4')
  utest_val(['SQLite: installed 3.53.4; approved 3.53.4; latest 3.53.4; update versions.sh.',
    '  Updated values for versions.sh:', f"  sqlite_sha3='{sha_a}'"], lines)
  lines = describe(component, {**values, 'sqlite_version': '3.53.3'}, upstream, '3.53.3')
  assert '; review and approve 3.53.4; update installation to 3.53.4; update versions.sh.' in lines[0]
  utest_val(["  sqlite_version='3.53.4'"], lines[3:])
  lines = describe(components[2], {'vector_version': '0.58.0'}, Upstream({'0.58.0'}), None)
  assert '; install 0.58.0.' in lines[0]
  lines = describe(components[3], {'uv_version': '0.11.31'}, Upstream({'0.12.19'}), '0.12.19')
  assert lines[0].endswith('; review and approve 0.12.19.')


@utest_run
def test_python_prereleases() -> None:
  tags = ''.join(f'abc refs/tags/v{v}\n' for v in ('3.14.7', '3.15.0rc2', '3.15.0rc3', '3.16.0a1'))
  release = [dict(name='Python 3.15.0rc3', is_published=True, pre_release=True,
    resource_uri='https://www.python.org/api/v2/downloads/release/1234/')]
  files = [dict(url='https://www.python.org/ftp/python/3.15.0/Python-3.15.0rc3.tar.xz', sha256_sum=sha_a)]
  utest(1234, parse_python_release, release, '3.15.0rc3')
  with patch('tap_ops.releases.run', return_value=CompletedProcess([], 0, stdout=tags)):
    with patch('tap_ops.releases.fetch_json', side_effect=[release, files]):
      upstream = python_versions('3.15.0rc2')
      utest_val({'3.14.7', '3.15.0rc2', '3.15.0rc3'}, upstream.versions)
      utest_val({'py_point_version': '3.15.0rc3', 'py_sha256': sha_a}, upstream.values)
    with patch('tap_ops.releases.fetch_json') as request:
      utest(Upstream({'3.14.7'}), python_versions, '3.14.7')
      utest_val({}, python_versions('3.15.0rc3').values)
      request.assert_not_called()
  release = [{**release[0], 'name': 'Python 3.15.0', 'pre_release': False}]
  files = [{**files[0], 'url': 'https://www.python.org/ftp/python/3.15.0/Python-3.15.0.tar.xz'}]
  with patch('tap_ops.releases.run', return_value=CompletedProcess([], 0, stdout=tags + 'abc refs/tags/v3.15.0\n')):
    with patch('tap_ops.releases.fetch_json', side_effect=[release, files]):
      upstream = python_versions('3.15.0rc3')
      utest_val('3.15.0', upstream.values['py_point_version'])
      lines = describe(components[0], {'py_point_version': '3.15.0rc3'}, upstream, '3.15.0rc3')
      assert 'review and approve 3.15.0;' in lines[0]
