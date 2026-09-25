# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tap_ops.releases import (CheckReleases, components, describe, parse_releases, parse_tags, read_versions, report,
  upstream_versions, version_key)
from utest import utest, utest_exc, utest_run, utest_val


utest(True, lambda: version_key('0.100.0') > version_key('0.99.9'))
utest(True, lambda: version_key('3.53.3.1') > version_key('3.53.3'))
utest_exc(ValueError, version_key, '3.15.0rc1')
utest({'3.14.7', '3.15.0'}, parse_tags,
  'abc refs/tags/v3.14.7\nabc refs/tags/v3.14.7^{}\nabc refs/tags/v3.15.0rc1\nabc refs/tags/v3.15.0\n',
  components[0].tag_pattern)
utest({'3.53.3', '3.53.3.1'}, parse_tags,
  'abc refs/tags/version-3.53.3\nabc refs/tags/version-3.53.3.1\nabc refs/tags/version-3.54.0-beta\n',
  components[1].tag_pattern)
utest_exc(ValueError, parse_tags, 'unexpected response body', components[0].tag_pattern)


@utest_run
def test_release_filtering() -> None:
  releases = [
    dict(tag_name='vdev-v9.0.0', draft=False, prerelease=False),
    dict(tag_name='v0.59.0', draft=False, prerelease=False),
    dict(tag_name='v0.60.0', draft=False, prerelease=True),
    dict(tag_name='v0.61.0', draft=True, prerelease=False),
    dict(tag_name='v0.62.0-rc.1', draft=False, prerelease=False)]
  utest(({'0.59.0'}, 5), parse_releases, releases, components[2].tag_pattern)
  utest_exc(ValueError, parse_releases, {'message': 'rate limited'}, components[2].tag_pattern)
  utest_exc(ValueError, parse_releases, [{'tag_name': 'v0.59.0'}], components[2].tag_pattern)


@utest_run
def test_pagination() -> None:
  # The actual product release can follow a page full of unrelated releases.
  first = [dict(tag_name=f'vdev-v0.0.{i}', draft=False, prerelease=False) for i in range(100)]
  second = [dict(tag_name='v0.59.0', draft=False, prerelease=False)]
  with patch('tap_ops.releases.github_json', side_effect=[first, second]) as request:
    utest({'0.59.0'}, upstream_versions, components[2])
    utest_val(2, request.call_count)
    assert 'page=2' in request.call_args.args[0]
  with patch('tap_ops.releases.github_json', return_value=[]):
    utest_exc(ValueError, upstream_versions, components[2])
  # Partial results must not conceal a failed later page.
  with patch('tap_ops.releases.github_json', side_effect=[first, OSError('offline')]):
    utest_exc(OSError, upstream_versions, components[2])


@utest_run
def test_literal_versions() -> None:
  base = "py_point_version='3.14.7'\nsqlite_version='3.53.3'\nvector_version='0.58.0'\nuv_version=\"0.11.31\" # Comment.\n"
  with TemporaryDirectory() as temp:
    path = Path(temp) / 'versions.sh'
    path.write_text(base)
    utest_val('3.14.7', read_versions(path)['py_point_version'])
    for extra in ['uv_version="0.11.32"\n', 'other=$(touch marker)\n', 'source other.sh\n']:
      path.write_text(base + extra)
      utest_exc(ValueError, read_versions, path)
    path.write_text('py_point_version="3.14.7"\n')
    utest_exc(ValueError, read_versions, path)


@utest_run
def test_python_series() -> None:
  lines = describe(components[0], '3.14.7', {'3.13.99', '3.14.10', '3.15.0'})
  assert any('New patch tag' in line and '3.14.10' in line for line in lines)
  assert any('New major/minor series: 3.15.0' in line for line in lines)
  utest_exc(ValueError, describe, components[0], '3.14.7', {'3.15.0'})
  assert 'no newer version found' in describe(components[1], '3.53.3', {'3.53.2'})[0]


@utest_run
def test_failure_does_not_skip_other_components() -> None:
  values = dict(py_point_version='3.14.7', sqlite_version='3.53.3', vector_version='0.58.0', uv_version='0.11.31')
  def lookup(component:object) -> set[str]:
    if component == components[1]: raise OSError('offline')
    if component == components[0]: return {'3.14.7'}
    return {'0.100.0'}
  out, err = StringIO(), StringIO()
  with patch('tap_ops.releases.upstream_versions', side_effect=lookup), redirect_stdout(out), patch('tap_ops.releases.stderr', err):
    utest(False, report, values)
  assert 'SQLite: lookup failed' in err.getvalue()
  for name in ('Python:', 'Vector:', 'uv:'): assert name in out.getvalue()


utest('ops/versions.sh', lambda: CheckReleases.parse([]).versions)
utest('/tmp/versions.sh', lambda: CheckReleases.parse(['-versions', '/tmp/versions.sh']).versions)
