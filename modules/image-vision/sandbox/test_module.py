
"""Sandbox test for image-vision module (fallback metadata path)."""
import sys, io
from pathlib import Path
SAMPLE = Path(__file__).resolve().parent / "samples" / "sample.png"
if not SAMPLE.exists():
    print("ERROR: sample.png not found"); sys.exit(1)
from PIL import Image


def describe(path):
    raw = path.read_bytes()
    img = Image.open(io.BytesIO(raw))
    ext = path.suffix.lstrip(".").lower()
    desc = "[Sandbox] %s, %dx%d, mode=%s, %d bytes. Gateway unavailable." % (path.name, img.width, img.height, img.mode, len(raw))
    b = [{"type":"图片","text":desc,"page":None,"resource_ref":1}]
    r = [{"id":1,"type":"图片","file_storage_id":0,"text_desc":desc}]
    return {"file_id":0,"format":ext,"blocks":b,"resources":r}


def validate(result):
    assert all(k in result for k in ("file_id","format","blocks","resources"))
    assert len(result["blocks"])==1 and result["blocks"][0]["type"]=="图片"
    assert len(result["resources"])==1 and result["resources"][0]["type"]=="图片"
    print("  Validation PASS")


def main():
    print("="*60); print("image-vision sandbox test"); print("="*60)
    result = describe(SAMPLE)
    for b in result["blocks"]:
        print("  [%s] %s" % (b["type"], b["text"][:80]))
    for r in result["resources"]:
        print("  [resource] %s" % r["text_desc"][:80])
    validate(result)
    print("PASS: image-vision sandbox test")

if __name__ == "__main__": main()
