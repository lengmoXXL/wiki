#!/usr/bin/env python3

import argparse
import hashlib
import mimetypes
import os
import sys
from pathlib import Path

import oss2
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
OSS_BUCKET = "lengmo-asserts"
OSS_ENDPOINT = "https://oss-cn-beijing.aliyuncs.com"
OSS_PREFIX = "blog/"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Publish dist/ to oss://{OSS_BUCKET}/{OSS_PREFIX}"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only print what would be uploaded/deleted",
    )
    args = parser.parse_args()

    if not DIST_DIR.is_dir():
        print("dist/ does not exist, run doc-research build first (see README)", file=sys.stderr)
        return 1

    load_dotenv(PROJECT_ROOT / ".env")
    auth = oss2.Auth(
        os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"],
        os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"],
    )
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)

    local = {}
    for path in sorted(DIST_DIR.rglob("*")):
        if path.is_file():
            key = OSS_PREFIX + path.relative_to(DIST_DIR).as_posix()
            local[key] = path
    # 域名根路径 / 由静态托管映射到根 index.html；同步一份到无前缀 key，
    # 使从根路径访问时 <base href="/blog/"> 的相对链接仍指向 /blog/ 下的资源
    local["index.html"] = DIST_DIR / "index.html"
    # ETag 即简单上传对象的内容 MD5，一次 list 调用取回，增量对比
    remote = {}
    for obj in oss2.ObjectIteratorV2(bucket, prefix=OSS_PREFIX):
        if not obj.key.endswith("/"):
            remote[obj.key] = obj.etag.strip('"').lower()
    try:
        remote["index.html"] = bucket.head_object("index.html").etag.strip('"').lower()
    except oss2.exceptions.NoSuchKey:
        pass

    uploads = {}
    for key, path in local.items():
        md5 = hashlib.md5(path.read_bytes()).hexdigest()
        if remote.get(key) != md5:
            uploads[key] = path
    deletions = [key for key in remote if key not in local]

    for key, path in uploads.items():
        print(f"upload {key} ({path.stat().st_size} bytes)")
        if args.dry_run:
            continue
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/"):
            content_type += "; charset=utf-8"
        bucket.put_object_from_file(key, str(path), headers={"Content-Type": content_type})

    for key in deletions:
        print(f"delete {key}")
        if not args.dry_run:
            bucket.delete_object(key)

    action = "would sync" if args.dry_run else "synced"
    print(f"{action}: {len(uploads)} uploaded, {len(deletions)} deleted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
