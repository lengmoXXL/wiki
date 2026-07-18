# OSS PDF to local Markdown

The script downloads a PDF from the configured OSS bucket, submits it to Alibaba
Cloud Document Mind, then rebuilds Markdown from the returned layout blocks.

1. Fill `ALIBABA_CLOUD_ACCESS_KEY_ID` and
   `ALIBABA_CLOUD_ACCESS_KEY_SECRET` in `.env`.
2. Make sure the RAM user can read `lengmo-asserts` and call DocMind.
3. Install and run with the PDF's OSS path:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tools/parse_docmind.py papers/distributed-systems/kafka-2011.pdf
```

The result is written to `raw/kafka-2011/`:

```text
raw/kafka-2011/
├── content.md
└── images/
```

The OSS bucket, service endpoints, and VLM enhancement setting are constants in
`tools/parse_docmind.py`. `.env` contains only the Alibaba Cloud access key and
secret.
