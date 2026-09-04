#!/usr/bin/env python

import argparse
import mimetypes
from pathlib import Path
from urllib.parse import quote

import requests
from fabric_cli.core import fab_constant
from fabric_cli.core.fab_auth import FabAuth


def request(session, method, url, expected, **kwargs):
    response = session.request(method, url, timeout=240, **kwargs)
    if response.status_code not in expected:
        detail = response.text.strip() or response.reason
        raise RuntimeError(f"OneLake returned {response.status_code}: {detail}")
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace_id")
    parser.add_argument("lakehouse_id")
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()

    source = Path(args.source)
    destination = args.destination.strip("/")
    token = FabAuth().get_access_token(fab_constant.SCOPE_ONELAKE_DEFAULT)
    base_url = (
        "https://onelake.dfs.fabric.microsoft.com/"
        f"{args.workspace_id}/{args.lakehouse_id}"
    )

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "x-ms-version": "2023-11-03",
        }
    )

    current_directory = ""
    for part in destination.rsplit("/", 1)[0].split("/"):
        current_directory = f"{current_directory}/{part}".strip("/")
        directory_url = f"{base_url}/{quote(current_directory, safe='/')}"
        request(
            session,
            "put",
            directory_url,
            {201, 409},
            params={"resource": "directory"},
        )

    file_url = f"{base_url}/{quote(destination, safe='/')}"
    request(session, "delete", file_url, {200, 202, 404}, params={"recursive": "false"})
    request(session, "put", file_url, {201}, params={"resource": "file"})

    content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    position = 0
    with source.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            request(
                session,
                "patch",
                file_url,
                {202},
                params={"action": "append", "position": position},
                headers={
                    "Content-Length": str(len(chunk)),
                    "Content-Type": content_type,
                    "x-ms-content-type": content_type,
                },
                data=chunk,
            )
            position += len(chunk)

    request(
        session,
        "patch",
        file_url,
        {200},
        params={"action": "flush", "position": position},
        headers={"Content-Length": "0", "x-ms-content-type": content_type},
    )
    print(f"Uploaded {source.name} to {destination}")


if __name__ == "__main__":
    main()
