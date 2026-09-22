"""Publish collector bundles to an existing Lakehouse using immutable DFS files.

publish_bundle(path, workspace_id, lakehouse_id, *, session=None, token=None)
validates locally before authentication and returns evidence URIs and identities.
The collector's canonical bundle.json bytes define the content-addressed revision.
Unique staging files are flushed before conditional rename; bundle.json is last.
Conflicting final files are never overwritten. Failed staging cleanup may leave
an unreferenced .tmp file, which does not prevent retrying the same bundle.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from uuid import UUID, uuid4

import requests


HOST = "https://onelake.dfs.fabric.microsoft.com"
FILES = ("manifest.json", "summary.json", "telemetry.json", "diagnostics.json")
MAX_FILE_BYTES = 16 * 1024 * 1024
TIMEOUT = (10, 60)


class PublishError(ValueError):
    """A sanitized local validation, authentication, or publication failure."""


def _uuid(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise PublishError("Expected a canonical lowercase UUID") from None
    return value


def _load_bundle(path):
    directory = Path(path).absolute()
    try:
        if any(parent.is_symlink() for parent in (directory, *directory.parents)):
            raise PublishError("Bundle paths must not contain symlinks")
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if set(os.listdir(descriptor)) != {*FILES, "bundle.json"}:
                raise PublishError("Bundle must contain exactly the five supported files")
            contents = {}
            for name in (*FILES, "bundle.json"):
                file_descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                          dir_fd=descriptor)
                with os.fdopen(file_descriptor, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise PublishError("Bundle entries must be regular files, not symlinks")
                    content = stream.read(MAX_FILE_BYTES + 1)
                if len(content) > MAX_FILE_BYTES:
                    raise PublishError("Each bundle file must be at most 16 MiB")
                contents[name] = content
        finally:
            os.close(descriptor)
    except OSError:
        raise PublishError("Cannot read bundle: require regular files without symlinks") from None
    try:
        index = json.loads(contents["bundle.json"])
        if not isinstance(index, dict) or set(index) != {"schema_version", "run_id", "execution_id", "files"}:
            raise ValueError
        if index["schema_version"] != "live-test-bundle.v1":
            raise ValueError
        _uuid(index["run_id"])
        if not isinstance(index["execution_id"], str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", index["execution_id"]):
            raise ValueError
        if not isinstance(index["files"], dict) or set(index["files"]) != set(FILES):
            raise ValueError
        for name in FILES:
            entry = index["files"][name]
            if not isinstance(entry, dict) or set(entry) != {"sha256", "size_bytes"}:
                raise ValueError
            if type(entry["size_bytes"]) is not int or entry["size_bytes"] != len(contents[name]):
                raise ValueError
            if entry["sha256"] != hashlib.sha256(contents[name]).hexdigest():
                raise ValueError
        canonical = (json.dumps(index, sort_keys=True, indent=2, ensure_ascii=True,
                                allow_nan=False) + "\n").encode("utf-8")
        if contents["bundle.json"] != canonical:
            raise ValueError
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise PublishError("Invalid bundle index, identities, canonical encoding, or file hashes/sizes") from None
    return index, contents, hashlib.sha256(canonical).hexdigest()


def _access_token():
    try:
        result = subprocess.run(
            ["az", "account", "get-access-token", "--resource", "https://storage.azure.com/",
             "--query", "accessToken", "--output", "tsv"],
            capture_output=True, text=True, check=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        raise PublishError("Azure CLI token acquisition failed; check az login and retry") from None
    return result.stdout.strip()


class _Publisher:
    def __init__(self, session, token):
        self.session = session
        self.headers = {"Authorization": "Bearer " + token, "x-ms-version": "2021-06-08"}

    def request(self, method, path, *, params=None, headers=None, data=None):
        try:
            with self.session.request(
                method, HOST + path, params=params, headers={**self.headers, **(headers or {})},
                data=data, timeout=TIMEOUT, allow_redirects=False, stream=True,
            ) as response:
                content = b""
                if method == "GET" and response.status_code == 200:
                    chunks, size = [], 0
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        size += len(chunk)
                        if size > MAX_FILE_BYTES:
                            raise PublishError("Remote file exceeds 16 MiB; publication stopped")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                return response.status_code, response.headers.get("x-ms-error-code"), content
        except requests.RequestException:
            raise PublishError("OneLake transport failed; retry the same bundle") from None

    def directory(self, path):
        status, code, _ = self.request("PUT", path, params={"resource": "directory"})
        if status != 201 and not (status == 409 and code == "PathAlreadyExists"):
            raise PublishError(f"OneLake directory creation failed (HTTP {status})")

    def matches(self, path, expected):
        status, _, actual = self.request("GET", path)
        if status == 404:
            return False
        if status != 200:
            raise PublishError(f"OneLake verification failed (HTTP {status})")
        if actual != expected:
            raise PublishError("Conflicting final file; nothing overwritten. Have the Lakehouse owner "
                               "investigate this revision or collect a genuinely new bundle revision")
        return True

    def cleanup(self, staging):
        status, _, _ = self.request("DELETE", staging)
        if status not in (200, 202, 204, 404):
            raise PublishError(f"Staging cleanup failed (HTTP {status}); retry the same bundle")

    def file(self, directory, name, content):
        final = directory + "/" + name
        if self.matches(final, content):
            return
        staging = directory + f"/.{name}.{uuid4()}.tmp"
        status, _, _ = self.request("PUT", staging, params={"resource": "file"},
                                    headers={"If-None-Match": "*"})
        if status != 201:
            raise PublishError(f"Staging creation failed (HTTP {status}); retry the same bundle")
        try:
            status, _, _ = self.request("PATCH", staging, params={"action": "append", "position": "0"},
                                        data=content, headers={"Content-Type": "application/octet-stream"})
            if status != 202:
                raise PublishError(f"Staging append failed (HTTP {status})")
            status, _, _ = self.request("PATCH", staging,
                                        params={"action": "flush", "position": str(len(content))})
            if status != 200:
                raise PublishError(f"Staging flush failed (HTTP {status})")
            if not self.matches(staging, content):
                raise PublishError("Staging file disappeared before rename; retry the same bundle")
            status, _, _ = self.request("PUT", final,
                                        headers={"x-ms-rename-source": staging, "If-None-Match": "*"})
            if status not in (201, 409, 412):
                raise PublishError(f"Final rename failed (HTTP {status})")
            renamed = status == 201
            if not self.matches(final, content):
                raise PublishError("Final file missing after rename; retry the same bundle")
        except PublishError:
            try:
                self.cleanup(staging)
            except PublishError:
                pass
            raise
        if not renamed:
            self.cleanup(staging)


def publish_bundle(path, workspace_id, lakehouse_id, *, session=None, token=None):
    """Validate and publish without overwrites; injected sessions remain caller-owned."""
    workspace_id, lakehouse_id = _uuid(workspace_id), _uuid(lakehouse_id)
    index, contents, bundle_hash = _load_bundle(path)
    token = _access_token() if token is None else token
    if not isinstance(token, str) or not token or not re.fullmatch(r"[\x21-\x7e]+", token):
        raise PublishError("A nonempty valid storage token is required")
    owned_session = session is None
    session = requests.Session() if owned_session else session
    directory = f"/{workspace_id}/{lakehouse_id}/Files/live-test-evidence"
    publisher = _Publisher(session, token)
    try:
        publisher.directory(directory)
        directory += "/" + index["run_id"]
        publisher.directory(directory)
        directory += "/" + bundle_hash
        publisher.directory(directory)
        for name in (*FILES, "bundle.json"):
            publisher.file(directory, name, contents[name])
    finally:
        if owned_session:
            session.close()
    return {"run_id": index["run_id"], "execution_id": index["execution_id"],
            "bundle_sha256": bundle_hash, "bundle_uri": HOST + directory + "/bundle.json",
            "manifest_uri": HOST + directory + "/manifest.json", "directory_uri": HOST + directory + "/"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--lakehouse-id", required=True)
    parser.add_argument("--bundle-directory", required=True)
    args = parser.parse_args(argv)
    try:
        result = publish_bundle(args.bundle_directory, args.workspace_id, args.lakehouse_id)
    except PublishError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())