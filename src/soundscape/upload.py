"""Upload archives to a Harvard Dataverse dataset via the S3 direct-upload API.

Harvard Dataverse stores files on S3 and supports direct upload, where the client
requests presigned URLs, PUTs the bytes straight to S3, then registers the file with
the dataset. Files larger than the installation's part size are uploaded in parts
(multipart). See:
https://guides.dataverse.org/en/latest/developers/s3-direct-upload-api.html
"""

import hashlib
import time
from pathlib import Path

import requests

DEFAULT_SERVER = "https://dataverse.harvard.edu"
MIME_TYPE = "application/gzip"
_READ_CHUNK = 8 * 1024 * 1024  # 8 MB streaming chunk


class _BoundedReader:
    """File-like wrapper exposing exactly ``length`` bytes from the current offset.

    Lets ``requests`` stream a single multipart slice of a large file without reading
    the whole file into memory. ``requests`` calls ``read(chunk)`` repeatedly until it
    is exhausted.
    """

    def __init__(self, fileobj, length: int):
        self._fileobj = fileobj
        self._remaining = length

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        if size is None or size < 0:
            size = self._remaining
        size = min(size, self._remaining)
        data = self._fileobj.read(size)
        self._remaining -= len(data)
        return data


def _md5(path: Path) -> str:
    """Compute the hex MD5 of a file, streaming it in chunks.

    Args:
        path: File to hash.

    Returns:
        Lowercase hex MD5 digest.
    """
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_READ_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _existing_filenames(server: str, doi: str, token: str) -> set[str]:
    """Return the set of filenames already present in the dataset's latest version.

    Args:
        server: Dataverse base URL.
        doi: Dataset persistent identifier.
        token: Dataverse API token.

    Returns:
        Set of filenames currently in the dataset (empty if the dataset has no files).
    """
    resp = requests.get(
        f"{server}/api/datasets/:persistentId/versions/:latest",
        params={"persistentId": doi},
        headers={"X-Dataverse-key": token},
        timeout=60,
    )
    resp.raise_for_status()
    files = resp.json().get("data", {}).get("files", [])
    names = set()
    for entry in files:
        data_file = entry.get("dataFile", {})
        name = data_file.get("filename") or entry.get("label")
        if name:
            names.add(name)
    return names


def _request_upload_urls(server: str, doi: str, token: str, size: int) -> dict:
    """Request presigned upload URL(s) for a file of the given size.

    Args:
        server: Dataverse base URL.
        doi: Dataset persistent identifier.
        token: Dataverse API token.
        size: File size in bytes.

    Returns:
        The ``data`` object from the response (single-part has ``url``; multipart has
        ``urls``, ``complete``, ``abort``).
    """
    resp = requests.get(
        f"{server}/api/datasets/:persistentId/uploadurls",
        params={"persistentId": doi, "size": size},
        headers={"X-Dataverse-key": token},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def _put_part(url: str, reader, length: int) -> str:
    """PUT bytes to a presigned S3 URL and return the ETag.

    Args:
        url: Presigned S3 PUT URL.
        reader: File-like object yielding exactly ``length`` bytes.
        length: Number of bytes to upload.

    Returns:
        The ETag returned by S3, with surrounding quotes stripped.
    """
    headers = {"Content-Length": str(length)}
    # The presigned URL declares which headers S3 expects in its signature; if it
    # was signed with x-amz-tagging, that header must be sent or S3 returns 403.
    if "x-amz-tagging" in url.lower():
        headers["x-amz-tagging"] = "dv-state=temp"
    resp = requests.put(
        url,
        data=reader,
        headers=headers,
        timeout=3600,
    )
    resp.raise_for_status()
    return resp.headers["ETag"].strip('"')


def _complete_multipart(server: str, complete_url: str, token: str, etags: dict[str, str]) -> None:
    """Finalize a multipart upload by submitting the part ETags.

    Args:
        server: Dataverse base URL.
        complete_url: Relative ``complete`` path returned by the uploadurls call.
        token: Dataverse API token.
        etags: Mapping of part number (as string) to ETag.
    """
    resp = requests.put(
        f"{server}{complete_url}",
        json=etags,
        headers={"X-Dataverse-key": token},
        timeout=300,
    )
    resp.raise_for_status()


def _abort_multipart(server: str, abort_url: str, token: str) -> None:
    """Abort a multipart upload, discarding any uploaded parts.

    Args:
        server: Dataverse base URL.
        abort_url: Relative ``abort`` path returned by the uploadurls call.
        token: Dataverse API token.
    """
    requests.delete(
        f"{server}{abort_url}",
        headers={"X-Dataverse-key": token},
        timeout=300,
    )


def _register_file(
    server: str,
    doi: str,
    token: str,
    storage_id: str,
    filename: str,
    md5: str,
) -> None:
    """Register an uploaded S3 object as a file in the dataset.

    Args:
        server: Dataverse base URL.
        doi: Dataset persistent identifier.
        token: Dataverse API token.
        storage_id: Storage identifier returned by the uploadurls call.
        filename: Name to give the file in the dataset.
        md5: Hex MD5 checksum of the file.
    """
    json_data = (
        '{"storageIdentifier":"%s","fileName":"%s","mimeType":"%s",'
        '"checksum":{"@type":"MD5","@value":"%s"}}' % (storage_id, filename, MIME_TYPE, md5)
    )
    resp = requests.post(
        f"{server}/api/datasets/:persistentId/add",
        params={"persistentId": doi},
        headers={"X-Dataverse-key": token},
        files={"jsonData": (None, json_data)},
        timeout=300,
    )
    resp.raise_for_status()


def upload_file(server: str, doi: str, token: str, path: Path) -> None:
    """Upload a single file to the dataset via S3 direct upload.

    Args:
        server: Dataverse base URL.
        doi: Dataset persistent identifier.
        token: Dataverse API token.
        path: File to upload.
    """
    size = path.stat().st_size
    md5 = _md5(path)
    info = _request_upload_urls(server, doi, token, size)
    storage_id = info["storageIdentifier"]

    if "urls" in info:
        # Multipart upload.
        part_size = int(info["partSize"])
        urls = info["urls"]
        etags: dict[str, str] = {}
        try:
            with path.open("rb") as f:
                for part_no in sorted(urls, key=int):
                    remaining = size - f.tell()
                    length = min(part_size, remaining)
                    etags[part_no] = _put_part(urls[part_no], _BoundedReader(f, length), length)
            _complete_multipart(server, info["complete"], token, etags)
        except Exception:
            _abort_multipart(server, info["abort"], token)
            raise
    else:
        # Single-part upload.
        with path.open("rb") as f:
            _put_part(info["url"], f, size)

    _register_file(server, doi, token, storage_id, path.name, md5)


def upload_archives(
    archives_dir: Path,
    doi: str,
    token: str,
    server: str = DEFAULT_SERVER,
    skip_existing: bool = True,
    files: list[Path] | None = None,
) -> None:
    """Upload tar.gz archives to a Harvard Dataverse dataset.

    Args:
        archives_dir: Directory containing ``*.tar.gz`` archives.
        doi: Dataset persistent identifier (e.g. ``doi:10.7910/DVN/S8ZBLX``).
        token: Dataverse API token.
        server: Dataverse base URL.
        skip_existing: Skip archives whose filename already exists in the dataset.
        files: Specific archive paths to upload instead of scanning ``archives_dir``.

    Raises:
        ValueError: If no archives are found to upload.
    """
    if files:
        archives = sorted(files)
    else:
        archives = sorted(archives_dir.glob("*.tar.gz"))
    if not archives:
        raise ValueError(f"No .tar.gz archives found in {archives_dir}")

    existing: set[str] = set()
    if skip_existing:
        existing = _existing_filenames(server, doi, token)

    uploaded = 0
    skipped = 0
    for path in archives:
        size_gb = path.stat().st_size / (1024**3)
        if skip_existing and path.name in existing:
            print(f"skip: {path.name} (already in dataset)")
            skipped += 1
            continue
        print(f"uploading: {path.name} ({size_gb:.2f} GB)...")
        start = time.monotonic()
        upload_file(server, doi, token, path)
        elapsed = time.monotonic() - start
        print(f"  done in {elapsed:.0f}s ({size_gb / max(elapsed, 1) * 1024:.1f} MB/s)")
        uploaded += 1

    print(f"\nUploaded {uploaded} archive(s), skipped {skipped}.")
