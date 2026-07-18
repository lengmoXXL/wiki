#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

import oss2
from PIL import Image
from alibabacloud_docmind_api20220711 import models as docmind_models
from alibabacloud_docmind_api20220711.client import Client as DocMindClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OSS_BUCKET = "lengmo-asserts"
OSS_ENDPOINT = "https://oss-cn-beijing.aliyuncs.com"
DOCMIND_ENDPOINT = "docmind-api.cn-hangzhou.aliyuncs.com"
VLM_ENHANCEMENT = True
POLL_INTERVAL_SECONDS = 5.0
TIMEOUT_SECONDS = 1800.0


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Download a PDF from OSS and parse it locally with Alibaba Cloud DocMind."
    )
    parser.add_argument(
        "file_path",
        metavar="OSS_PATH",
        help="PDF path in the configured OSS bucket",
    )
    args = parser.parse_args()

    object_key = args.file_path
    file_name = Path(object_key).name

    access_key_id = os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"]
    access_key_secret = os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"]

    raw_dir = PROJECT_ROOT / "raw"
    output_dir = raw_dir / Path(file_name).stem

    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)

    with tempfile.TemporaryDirectory(prefix="pdf-markdown-") as temp_dir:
        temp_path = Path(temp_dir)
        pdf_path = temp_path / file_name
        pages_dir = temp_path / "pages"
        result_dir = temp_path / "result"
        images_dir = result_dir / "images"
        pages_dir.mkdir()
        images_dir.mkdir(parents=True)

        print(f"Downloading oss://{OSS_BUCKET}/{object_key} ...")
        try:
            bucket.get_object_to_file(object_key, str(pdf_path))
        except oss2.exceptions.OssError as error:
            print(f"OSS download failed: {error}", file=sys.stderr)
            print(
                "Check that OSS_ENDPOINT matches the bucket region and the RAM user has oss:GetObject.",
                file=sys.stderr,
            )
            return 1
        print(f"Downloaded {pdf_path.stat().st_size / 1024 / 1024:.1f} MiB")

        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        )
        config.endpoint = DOCMIND_ENDPOINT
        client = DocMindClient(config)

        print(f"Submitting DocMind job (VLM enhancement: {VLM_ENHANCEMENT}) ...")
        with pdf_path.open("rb") as pdf_file:
            response = client.submit_doc_parser_job_advance(
                docmind_models.SubmitDocParserJobAdvanceRequest(
                    file_name=pdf_path.name,
                    file_name_extension=pdf_path.suffix.lstrip("."),
                    file_url_object=pdf_file,
                    formula_enhancement=True,
                    output_format=["visualLayoutInfo"],
                    llm_enhancement=VLM_ENHANCEMENT,
                    enhancement_mode="VLM" if VLM_ENHANCEMENT else None,
                ),
                util_models.RuntimeOptions(),
            )
        job_id = response.body.data.id
        print(f"Job ID: {job_id}")

        started_at = time.monotonic()
        while True:
            response = client.query_doc_parser_status(
                docmind_models.QueryDocParserStatusRequest(id=job_id)
            )
            status_data = response.body.data.to_map()
            status = status_data["Status"]
            progress = status_data["Processing"]
            print(f"Status: {status}" + (f" ({progress}%)" if progress is not None else ""))

            if status == "success":
                break
            if status == "fail":
                print(json.dumps(status_data, ensure_ascii=False, indent=2), file=sys.stderr)
                return 1
            if time.monotonic() - started_at >= TIMEOUT_SECONDS:
                print(f"Timed out after {TIMEOUT_SECONDS:.0f} seconds", file=sys.stderr)
                return 1
            time.sleep(POLL_INTERVAL_SECONDS)

        page_records = status_data["OutputFormatResult"][0]["Pages"]

        layouts = []
        layout_offset = 0
        layout_step_size = 300
        while True:
            response = client.get_doc_parser_result(
                docmind_models.GetDocParserResultRequest(
                    id=job_id,
                    layout_num=layout_offset,
                    layout_step_size=layout_step_size,
                )
            )
            batch = response.body.data["layouts"]
            if not batch:
                break
            layouts.extend(batch)
            layout_offset += len(batch)
            if len(batch) < layout_step_size:
                break

        figure_pages = {
            layout["pageNum"] for layout in layouts if layout["type"] == "figure"
        }
        pages_by_number = {}
        for page in page_records:
            page_number = page["PageIdCurDoc"]
            if page_number not in figure_pages:
                continue
            page_path = pages_dir / f"page-{page_number:04d}"
            with urlopen(page["ImageUrl"], timeout=120) as source, page_path.open(
                "wb"
            ) as target:
                shutil.copyfileobj(source, target)
            pages_by_number[page_number] = {
                "path": page_path,
                "width": page["ImageWidth"],
                "height": page["ImageHeight"],
            }

        local_markdown = []
        figure_number = 0
        for layout in layouts:
            layout_type = layout["type"]
            if layout_type != "figure":
                markdown = layout["markdownContent"]
                if markdown:
                    local_markdown.append(markdown)
                continue
            page_number = layout["pageNum"]
            points = layout["pos"]

            page_info = pages_by_number[page_number]

            xs = [point["x"] for point in points]
            ys = [point["y"] for point in points]
            with Image.open(page_info["path"]) as page_image:
                source_width = page_info["width"]
                source_height = page_info["height"]
                box = (
                    round(min(xs) * page_image.width / source_width),
                    round(min(ys) * page_image.height / source_height),
                    round(max(xs) * page_image.width / source_width),
                    round(max(ys) * page_image.height / source_height),
                )
                figure_number += 1
                image_path = images_dir / f"{layout_type}-{figure_number:04d}.png"
                page_image.crop(box).save(image_path)
                local_image = image_path.relative_to(result_dir).as_posix()
                local_markdown.append(f"![{layout_type}]({local_image})")

        rendered_markdown = "\n\n".join(
            block.rstrip("\n") for block in local_markdown
        ).strip() + "\n"
        (result_dir / "content.md").write_text(rendered_markdown, encoding="utf-8")

        raw_dir.mkdir(exist_ok=True)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        shutil.move(result_dir, output_dir)

    print(f"Saved local results to {output_dir}")
    print(f"- Markdown: {output_dir / 'content.md'}")
    print(f"- Cropped figures: {output_dir / 'images'} ({figure_number})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
