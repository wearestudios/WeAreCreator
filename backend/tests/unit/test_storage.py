"""Where uploaded bytes live, and the refusal that stops them living nowhere.

Uploads were local disk and nothing else, on a host whose filesystem is
ephemeral. That is not a robustness concern, it is a data-loss bug with a
schedule: **every redeploy destroyed every verification document, profile
photo, campaign cover, draft and story proof**, leaving the database rows
pointing at files that were not there. The rows survive, so the failure is
invisible until a reviewer opens a GST certificate weeks later and gets a 410.

Two things are tested here, and the second is the one that would actually have
prevented it:

- the backends behave the same way through one interface, driven against a
  real temporary directory and a fake S3 client rather than read for their
  shape; and
- **a production box refuses to start on local disk.** A warning in a deploy
  log is a line nobody reads until they are already looking for the cause.

`boto3` is deliberately not installed in the unit environment — the local
backend must not need it — so the S3 half runs against a stub that records
what it was asked to do. That is enough for the questions worth asking here:
which prefix, which cache header, what a signed URL is for, and whether a
missing object reads as absent rather than as an exception.
"""

from __future__ import annotations

import importlib
import inspect
import io
import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

import server


# ---------------------------------------------------------------------------
# The local backend, driven
# ---------------------------------------------------------------------------


@pytest.fixture
def disk(tmp_path, monkeypatch):
    """Point both directories at a temporary one.

    `LocalStorage` reads the module constants at call time rather than binding
    them in `__init__`, which is what makes this work — the first version
    captured them and a test like this watched an empty tmpdir while the real
    directory filled up.
    """
    public = tmp_path / "uploads"
    private = tmp_path / "private"
    monkeypatch.setattr(server, "UPLOAD_DIR", public)
    monkeypatch.setattr(server, "PRIVATE_UPLOAD_DIR", private)
    monkeypatch.setattr(server, "STORAGE", server.LocalStorage())
    return public, private


class TestLocalStorage:
    def test_a_file_written_can_be_read_back(self, disk):
        server.STORAGE.put(
            "a.jpg", io.BytesIO(b"hello"), content_type="image/jpeg", private=False
        )
        assert server.STORAGE.exists("a.jpg", private=False) is True
        with server.STORAGE.open("a.jpg", private=False) as fh:
            assert fh.read() == b"hello"

    def test_public_and_private_are_different_places(self, disk):
        public, private = disk
        server.STORAGE.put(
            "same.jpg", io.BytesIO(b"pub"), content_type="image/jpeg", private=False
        )
        server.STORAGE.put(
            "same.jpg", io.BytesIO(b"priv"), content_type="image/jpeg", private=True
        )

        # The same name in both, and they are not the same file. A cover is
        # meant to be seen by strangers; a GST certificate never is.
        assert (public / "same.jpg").read_bytes() == b"pub"
        assert (private / "same.jpg").read_bytes() == b"priv"

    def test_a_missing_file_is_absent_rather_than_an_error(self, disk):
        assert server.STORAGE.exists("nope.jpg", private=True) is False
        assert server.STORAGE.open("nope.jpg", private=True) is None
        assert server.STORAGE.path("nope.jpg", private=True) is None

    def test_deleting_is_idempotent(self, disk):
        """Erasure has to be repeatable: a file already gone is the state we
        wanted, not a failure to report to somebody exercising a right."""
        server.STORAGE.put(
            "x.pdf", io.BytesIO(b"1"), content_type="application/pdf", private=True
        )
        assert server.STORAGE.delete("x.pdf", private=True) is True
        assert server.STORAGE.delete("x.pdf", private=True) is False
        assert server.STORAGE.exists("x.pdf", private=True) is False

    @pytest.mark.parametrize(
        "name", ["../secret.pdf", "a/b.pdf", "a\\b.pdf", "", ".", "..", "../../etc/passwd"]
    )
    def test_it_will_not_be_walked_out_of_its_directory(self, disk, name):
        assert server.STORAGE.path(name, private=True) is None
        assert server.STORAGE.exists(name, private=True) is False
        assert server.STORAGE.delete(name, private=True) is False

    def test_it_offers_no_signed_url(self, disk):
        """**Absent is an answer, not a failure.** `_private_file_response`
        reads a `None` here as "stream the bytes", which is what local disk
        does and has always done."""
        assert server.STORAGE.signed_url("x.pdf", private=True) is None

    def test_a_public_url_is_still_the_path_we_issued(self, disk):
        assert server.STORAGE.public_url("cover.jpg") == "/uploads/cover.jpg"


# ---------------------------------------------------------------------------
# The S3 backend, against a stub
# ---------------------------------------------------------------------------


class FakeS3Client:
    """Enough of boto3's S3 client to answer the questions that matter."""

    def __init__(self):
        self.objects = {}
        self.uploads = []
        self.signed = []

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
        self.objects[key] = fileobj.read()
        self.uploads.append((bucket, key, ExtraArgs or {}))

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)  # botocore raises ClientError; both are Exception
        return {"Body": io.BytesIO(self.objects[Key])}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        return {"ContentLength": len(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def generate_presigned_url(self, op, Params, ExpiresIn):
        self.signed.append((Params["Key"], ExpiresIn))
        return f"https://signed.example/{Params['Key']}?expires={ExpiresIn}"


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "weare-test")
    monkeypatch.setenv("S3_REGION", "ap-south-1")
    backend = server.S3Storage.__new__(server.S3Storage)
    backend.bucket = "weare-test"
    backend.public_base = ""
    backend._client = FakeS3Client()
    monkeypatch.setattr(server, "STORAGE", backend)
    return backend


class TestS3Storage:
    def test_the_two_prefixes_are_the_separation(self, s3):
        """One bucket, two prefixes. The difference between a cover and a GST
        certificate is a policy on a prefix — two buckets would be two sets of
        credentials and two places to get public access wrong."""
        assert server.S3Storage.key("a.jpg", private=False) == "public/a.jpg"
        assert server.S3Storage.key("a.pdf", private=True) == "private/a.pdf"

    def test_a_private_object_is_written_no_store(self, s3):
        s3.put("d.pdf", io.BytesIO(b"x"), content_type="application/pdf", private=True)
        _bucket, key, extra = s3._client.uploads[-1]
        assert key == "private/d.pdf"
        assert extra["CacheControl"] == "no-store"
        assert extra["ContentType"] == "application/pdf"

    def test_a_public_object_is_cached_hard(self, s3):
        """A cover is addressed by a random name we generated and is never
        rewritten in place, so nothing is gained by revalidating it — and
        these are on every card of every list."""
        s3.put("c.jpg", io.BytesIO(b"x"), content_type="image/jpeg", private=False)
        _bucket, key, extra = s3._client.uploads[-1]
        assert key == "public/c.jpg"
        assert "immutable" in extra["CacheControl"]

    def test_a_missing_object_is_absent_rather_than_raising(self, s3):
        """The routes above this read absent as a 404 or a 410. An exception
        escaping here would be a 500 on a file that was simply purged."""
        assert s3.exists("gone.pdf", private=True) is False
        assert s3.open("gone.pdf", private=True) is None

    def test_a_signed_url_is_time_limited(self, s3, monkeypatch):
        monkeypatch.setenv("S3_SIGNED_URL_TTL_SECONDS", "90")
        url = s3.signed_url("d.pdf", private=True)
        assert url and "private/d.pdf" in url
        assert s3._client.signed[-1] == ("private/d.pdf", 90)

    @pytest.mark.parametrize(
        "raw,expected", [("10", 30), ("99999", 3600), ("not a number", 120), ("300", 300)]
    )
    def test_the_ttl_is_clamped(self, monkeypatch, raw, expected):
        """A day-long signature is a public link with extra steps; a
        one-second one is a document nobody on a slow connection can open."""
        monkeypatch.setenv("S3_SIGNED_URL_TTL_SECONDS", raw)
        assert server.signed_url_ttl_seconds() == expected

    def test_the_public_url_is_unchanged_so_no_row_had_to_move(self, s3):
        """**The whole reason this migration is a file copy.**

        `_our_image_path` validates that a case-study image is a path we
        issued, `_absolute_media_url` builds the share card's `og:image`
        against the backend, `_delete_upload` reads the name back out of the
        URL. Storing a bucket URL on the record would have broken all three.
        """
        assert s3.public_url("cover.jpg") == "/uploads/cover.jpg"
        assert server._our_image_path("/uploads/cover.jpg") == "/uploads/cover.jpg"

    def test_the_object_url_prefers_a_cdn(self, s3, monkeypatch):
        assert s3.object_url("c.jpg").endswith("/public/c.jpg")
        s3.public_base = "https://cdn.example"
        assert s3.object_url("c.jpg") == "https://cdn.example/public/c.jpg"


# ---------------------------------------------------------------------------
# Refusing to write somewhere the bytes will not survive
# ---------------------------------------------------------------------------


class TestItRefusesEphemeralStorage:
    """The check that would have caught the original bug.

    Every case calls the real `_refuse_ephemeral_storage` and reads back what
    it reports, rather than asserting on the source — a refusal that names the
    right variables and never fires is the shape this codebase keeps finding.
    """

    def _missing(self, monkeypatch, **env):
        for key in (
            "STORAGE_BACKEND",
            "S3_BUCKET",
            "S3_REGION",
            "S3_ACCESS_KEY_ID",
            "S3_SECRET_ACCESS_KEY",
            "APP_ENV",
            "ENV",
        ):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return dict(server._refuse_ephemeral_storage())

    def test_production_on_local_disk_is_refused(self, monkeypatch):
        missing = self._missing(monkeypatch, APP_ENV="production")
        assert "S3_BUCKET" in missing
        assert "wipes on deploy" in missing["S3_BUCKET"]

    def test_an_unset_app_env_counts_as_production(self, monkeypatch):
        """The same reading `_is_production` and `_simulation_allowed` take.
        Guessing the other way is how a real deployment ends up silently
        writing to a disk that is about to disappear."""
        assert self._missing(monkeypatch) != {}

    @pytest.mark.parametrize("env", ["development", "dev", "local", "test"])
    def test_a_laptop_and_the_test_suite_keep_the_disk(self, monkeypatch, env):
        """Local storage is not a lesser path — it is what `docker compose`,
        the unit suite and a laptop run, and a backend that only works with
        four credentials present is one nobody can develop against."""
        assert self._missing(monkeypatch, APP_ENV=env) == {}

    def test_an_explicit_local_override_is_allowed(self, monkeypatch):
        """There has to be a way through, or somebody edits the check out.
        It is explicit and it is named in .env.example as never right on a
        deployed box."""
        assert self._missing(monkeypatch, APP_ENV="production", STORAGE_BACKEND="local") == {}

    def test_every_missing_s3_setting_is_named_at_once(self, monkeypatch):
        """One boot, one list. Reporting only the first costs four deploys to
        fix four blanks — the reasoning `validate_environment` already holds."""
        missing = self._missing(
            monkeypatch, STORAGE_BACKEND="s3", S3_BUCKET="b", APP_ENV="production"
        )
        assert set(missing) == {"S3_REGION", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"}

    def test_a_fully_configured_bucket_passes(self, monkeypatch):
        assert (
            self._missing(
                monkeypatch,
                APP_ENV="production",
                STORAGE_BACKEND="s3",
                S3_BUCKET="b",
                S3_REGION="ap-south-1",
                S3_ACCESS_KEY_ID="k",
                S3_SECRET_ACCESS_KEY="s",
            )
            == {}
        )

    def test_a_bucket_set_and_not_declared_is_still_s3(self, monkeypatch):
        """A bucket configured and unused is a configuration somebody thinks
        is live."""
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        monkeypatch.setenv("S3_BUCKET", "b")
        assert server.storage_backend_name() == "s3"

    def test_the_refusal_actually_ends_the_process(self):
        """A check that reports and carries on is a check that changed
        nothing. This is the one structural assertion in the file, because the
        alternative is killing the interpreter running the suite."""
        src = inspect.getsource(server)
        assert "if _refuse_ephemeral_storage():\n    raise SystemExit(1)" in src


# ---------------------------------------------------------------------------
# How a private file reaches somebody who is allowed to see it
# ---------------------------------------------------------------------------


class TestPrivateDelivery:
    def test_local_streams_the_bytes(self, disk):
        server.STORAGE.put(
            "d.pdf", io.BytesIO(b"%PDF-x"), content_type="application/pdf", private=True
        )
        res = server._private_file_response(
            "d.pdf", original_name="gst.pdf", mime="application/pdf", inline=True
        )
        assert res.headers["cache-control"] == "no-store"
        assert 'filename="gst.pdf"' in res.headers["content-disposition"]

    def test_s3_redirects_to_a_signed_url(self, s3):
        s3.put("d.pdf", io.BytesIO(b"x"), content_type="application/pdf", private=True)
        res = server._private_file_response(
            "d.pdf", original_name="gst.pdf", mime="application/pdf", inline=True
        )
        assert res.status_code == 307
        assert "signed.example" in res.headers["location"]
        # Never cached: the link expires, and a cached redirect to a dead URL
        # breaks later for reasons nobody can reproduce.
        assert res.headers["cache-control"] == "no-store"

    def test_the_bytes_are_never_at_an_unsigned_address(self, s3):
        """The bucket's private prefix is blocked at the bucket; the only way
        in is a signature this server mints for somebody it has already
        authorised. There is no code path that hands out a bare object URL for
        a private file — `object_url` is public-only and says so."""
        src = inspect.getsource(server.S3Storage.object_url)
        assert "private=False" in src
        assert "private=True" not in src

    def test_a_purged_file_is_410_rather_than_a_crash(self, s3):
        """The row is a tombstone and the file went under the retention
        policy. An exception here would read as a bug in the app."""
        s3.signed_url = lambda name, private=True: None  # force the stream path
        with pytest.raises(HTTPException) as exc:
            server._private_file_response(
                "gone.pdf", original_name="x.pdf", mime=None, inline=True
            )
        assert exc.value.status_code == 410

    def test_a_download_name_cannot_break_the_header(self, disk):
        """The uploader's filename never touches the filesystem, but it is
        echoed into a `Content-Disposition`, and a quote or a newline in it is
        a header the client parses differently from the one we sent."""
        server.STORAGE.put(
            "d.pdf", io.BytesIO(b"x"), content_type="application/pdf", private=True
        )
        res = server._private_file_response(
            "d.pdf",
            original_name='ev"il\r\nX-Injected: 1.pdf',
            mime="application/pdf",
            inline=True,
        )
        header = res.headers["content-disposition"]
        assert '"' not in header.split("filename=", 1)[1][1:-1]
        assert "\n" not in header and "\r" not in header


# ---------------------------------------------------------------------------
# The migration
# ---------------------------------------------------------------------------


class TestTheMigration:
    def test_it_exists_and_is_a_script_rather_than_a_route(self):
        """The same reasoning `seed_demo.py` is held to: something that walks
        every stored file is not a thing to leave in the route table one
        misconfiguration from reachable."""
        path = Path(server.__file__).resolve().parent / "migrate_uploads_to_s3.py"
        assert path.is_file()
        src = path.read_text()
        assert "router" not in src and "@app." not in src

    def test_it_does_nothing_without_apply(self):
        """A migration that runs on being invoked is one somebody triggers by
        reading the help text."""
        src = (
            Path(server.__file__).resolve().parent / "migrate_uploads_to_s3.py"
        ).read_text()
        assert '"--apply"' in src
        assert "if not args.apply:" in src

    def test_it_deletes_nothing_from_disk(self):
        """The local copy is the fallback if a copy went wrong. A migration
        whose first act is a delete is one nobody can check afterwards."""
        src = (
            Path(server.__file__).resolve().parent / "migrate_uploads_to_s3.py"
        ).read_text()
        for destructive in ("unlink", "rmtree", "os.remove", "shutil.move"):
            assert destructive not in src, destructive

    def test_it_is_idempotent_by_default(self):
        src = (
            Path(server.__file__).resolve().parent / "migrate_uploads_to_s3.py"
        ).read_text()
        assert "storage.exists(" in src
        assert '"--overwrite"' in src


# ---------------------------------------------------------------------------
# boto3 is a dependency, and only the S3 path needs it
# ---------------------------------------------------------------------------


def test_boto3_is_declared_as_a_runtime_dependency():
    """It was not — the brief said it already was. `requirements.txt` is what
    a production build installs, so a backend that imports it has to say so
    there rather than in the dev set."""
    reqs = (Path(server.__file__).resolve().parent / "requirements.txt").read_text()
    assert "boto3" in reqs


def test_the_import_is_lazy_so_a_laptop_does_not_need_it():
    """The unit suite runs with boto3 absent — verified by the fact that this
    module imported at all — and that has to stay true. A top-level import
    would make the local backend depend on a package it never uses."""
    assert "boto3" not in sys.modules or importlib.util.find_spec("boto3")
    module_src = inspect.getsource(server)
    top = module_src[: module_src.index("class S3Storage")]
    assert "import boto3" not in top
    assert "import boto3" in inspect.getsource(server.S3Storage.__init__)
