"""Index native PDF text, detected table grids, scans, and verified visual transcriptions."""
import argparse
import hashlib
import json
import re
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import fitz

from src.benchmark import read, write

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "3f34ce114dd553421e4a5c9d44c8baa39a8608afd2067c79dcb731a8f8c459fe"
OCR_SHA = "79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1"
GLYPHS = str.maketrans("ƣƢƢ", "ưƯƯ")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def clean(value):
    return " ".join(unicodedata.normalize("NFC", (value or "").translate(GLYPHS)).split())


def bounds(rect):
    return [round(v, 1) for v in rect]


def block_chunks(page, blocks, kind):
    groups, lines, region = [], [], None
    for block in blocks:
        text = clean(block[4])
        if not text or text.isdecimal():
            continue
        # Leave room for neighbouring context in the model prompt.
        slices = re.findall(r".{1,880}(?:\s|$)|\S{1,880}", text)
        rect = fitz.Rect(block[:4])
        for part in slices:
            if lines and sum(map(len, lines)) + len(part) > 950:
                groups.append({"page": page, "kind": kind, "bbox": bounds(region), "text": "\n".join(lines)})
                lines, region = [], None
            lines.append(part.strip())
            region = rect if region is None else region | rect
    if lines:
        groups.append({"page": page, "kind": kind, "bbox": bounds(region), "text": "\n".join(lines)})
    return groups


def table_chunks(page):
    result = []
    for number, table in enumerate(page.find_tables().tables, 1):
        cells = [[clean(value) for value in row] for row in table.extract()]
        if len(cells) < 2:
            continue
        header_end = next((i for i in range(1, len(cells)) if cells[i][0] or cells[i][1]), 1)
        header = [" ".join(row[col] for row in cells[:header_end] if row[col])
                  for col in range(len(cells[0]))]
        nearby = [clean(block[4]) for block in page.get_text("blocks", sort=True)
                  if table.bbox[1] - 50 <= block[3] <= table.bbox[1]
                  and re.search(r"bảng|thống kê|chỉ tiêu", block[4], re.I)]
        caption = nearby[-1][-160:] if nearby else ""
        groups, current, top = [], [], header_end
        for i, row in enumerate(cells[header_end:], header_end):
            if not any(row):
                continue
            line = " | ".join(f"{header[j] or 'Cột '+str(j+1)}: {value}"
                              for j, value in enumerate(row) if value)
            if current and sum(map(len, current)) + len(line) > 750:
                groups.append((top, i - 1, current))
                current, top = [], i
            current.append(line)
        if current:
            groups.append((top, len(cells) - 1, current))
        for lo, hi, lines in groups:
            rect = (fitz.Rect(table.rows[0].bbox) | fitz.Rect(table.rows[lo].bbox)
                    | fitz.Rect(table.rows[hi].bbox))
            result.append({
                "page": page.number + 1, "kind": "table", "bbox": bounds(rect),
                "table": number, "rows": [lo + 1, hi + 1], "table_bbox": bounds(table.bbox),
                "text": "\n".join([caption, *lines]).strip(),
            })
    return result


def extract_page(job):
    pdf, number, tessdata = job
    with fitz.open(pdf) as document:
        page = document[number - 1]
        native = page.get_text("blocks", sort=True)
        has_text = any(len(clean(block[4])) > 20 for block in native)
        parts = block_chunks(number, native, "text")
        tables = table_chunks(page) if has_text else []
        media = page.get_image_info()
        raster_page = any(
            fitz.Rect(item["bbox"]).get_area() >= .70 * page.rect.get_area() for item in media
        )
        ocr_count = 0
        if raster_page or (media and not has_text):
            layer = page.get_textpage_ocr(language="vie", dpi=180, full=True, tessdata=tessdata)
            ocr = block_chunks(number, page.get_text("blocks", sort=True, textpage=layer), "ocr")
            ocr_count = len(ocr)
            parts.extend(ocr)
        return number, parts + tables, {
            "native": has_text, "ocr": ocr_count, "tables": len(tables),
            "images": len(media), "width": page.rect.width, "height": page.rect.height,
            "raster_page": raster_page,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--tessdata", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/bonus")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if sha(args.pdf) != SOURCE_SHA or sha(args.tessdata / "vie.traineddata") != OCR_SHA:
        raise ValueError("Unexpected PDF or Vietnamese OCR weights SHA-256")
    output = args.output.resolve()
    state = output / "pages"
    state.mkdir(parents=True, exist_ok=True)
    with fitz.open(args.pdf) as pdf:
        count = len(pdf)
    todo = [(str(args.pdf.resolve()), n, str(args.tessdata.resolve()))
            for n in range(1, count + 1) if not (state / f"{n:03d}.json").exists()]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for number, chunks, info in pool.map(extract_page, todo, chunksize=3):
            write(state / f"{number:03d}.json", {"chunks": chunks, "profile": info})
            if number % 20 == 0:
                print(f"Processed page {number}/{count}", flush=True)
    rows, profile = [], []
    for number in range(1, count + 1):
        data = read(state / f"{number:03d}.json")
        rows.extend(data["chunks"])
        profile.append({"page": number, **data["profile"]})
    write(output / "extracted.json", {"chunks": rows, "pages": profile})


if __name__ == "__main__":
    main()
