# tap_backblaze integration tests

This suite exercises `tap_backblaze.api` and `B2BackupStore` against the real B2 service.
It is linted and typechecked by `just check`, but never executed automatically.
Run it with `just test-backblaze`.

## Configuration

The suite takes two credentials paths, a read-only key and a read-write key, as positional arguments.
`just test-backblaze` passes these paths, relative to the project root:

* `../creds/backblaze/tap-backblaze-test-ro.json`
* `../creds/backblaze/tap-backblaze-test-rwd.json`

Both are `B2Creds` JSON files, as written by `tap_backblaze.key`.

Every upload and every cleanup delete uses the read-write key.
Every listing and every download uses the read-only key.
This mirrors our practice, where developers and test servers can restore from production backups but cannot write them,
so the suite fails if the restore path ever comes to depend on write access.

The test bucket is the sole bucket recorded in the read-write credentials' `buckets` mapping;
pass `-bucket` to choose one when the credentials record several.

## Required capabilities

The read-write key needs: `listFiles`, `readFiles`, `writeFiles`, `deleteFiles`; this is the `file-rwd` group.
`deleteFiles` is required rather than optional because cleanup depends on it;
the run exits before uploading anything if the key cannot delete what it is about to write.

The read-only key needs: `listFiles`, `readFiles`; this is the `file-ro` group.
It must not have `writeFiles` or `deleteFiles`; the suite checks that the service refuses both.

Create the keys with `tap_backblaze.key`, using a key that can list buckets and create keys:

```sh
python -m tap_backblaze.key create -creds ADMIN_CREDS -name tap-backblaze-test-ro -buckets tap-backblaze-test \
  -capabilities file-ro -output ../creds/backblaze/tap-backblaze-test-ro.json
python -m tap_backblaze.key create -creds ADMIN_CREDS -name tap-backblaze-test-rwd -buckets tap-backblaze-test \
  -capabilities file-rwd -output ../creds/backblaze/tap-backblaze-test-rwd.json
```

The capabilities that the suite checks are the ones the service reports at authorization,
not the copy recorded in the creds file, so a stale creds file cannot mask a mismatch.

`listBuckets` is not required for either key: the bucket id is resolved from the creds file's `buckets` mapping,
or from the authorize response's allowed buckets for a bucket-restricted key.

`listKeys` and `writeKeys` on the read-write key enable two optional key-management checks,
which are skipped when the key lacks them.

## Cost

Every object is written under a unique per-run prefix, so concurrent or repeated runs cannot collide.
The run deletes every version it created on the way out, including on failure, so it leaves no storage behind.
The transfer is roughly 20 MB up and down (the large-file case uploads two parts at the absolute minimum part size);
the cost is a few cents at most and generally far less.
