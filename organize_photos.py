#!/usr/bin/env python3
"""
organize_photos.py — Batch face-recognition photo organizer for the Ryzen rig
Uses the existing InsightFace buffalo_l model and faces.npz enrollment file.

Usage:
    python3 organize_photos.py --source /path/to/photos --output ~/photos_sorted
    python3 organize_photos.py --source ~/Pictures --output ~/photos_sorted --copy
    python3 organize_photos.py --source ~/Pictures --output ~/photos_sorted --move
    python3 organize_photos.py --enroll-best --source ~/photos_sorted/matthew --name matthew

Options:
    --source DIR        Source directory to scan (recursive)
    --output DIR        Output directory for sorted photos (default: ~/photos_sorted)
    --copy              Copy files (default — original untouched)
    --move              Move files instead of copying
    --threshold FLOAT   Face match threshold (default: 0.35, same as Aubie)
    --enroll-best       Scan source dir and add high-confidence faces to faces.npz
    --name NAME         Person name for --enroll-best mode
    --faces-npz PATH    Path to faces.npz (default: ~/aubie_storage/faces/faces.npz)
    --dry-run           Show what would happen without doing it
    --workers INT       Parallel workers (default: 4)
"""

import os
import sys
import shutil
import argparse
import logging
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
import concurrent.futures

# ── logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("organize_photos")

# ── constants ──────────────────────────────────────────────────────────────────
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif", ".heic", ".heif"}
DEFAULT_FACES_NPZ = Path.home() / "aubie_storage" / "faces" / "faces.npz"
DEFAULT_OUTPUT    = Path.home() / "photos_sorted"
FACE_MATCH_THRESHOLD = 0.35        # matches Aubie's current threshold
ENROLL_MIN_BBOX_PX   = 80          # min face width/height to consider for enrollment
ENROLL_MIN_SCORE     = 0.70        # min cosine score to auto-enroll (high confidence only)

# ── InsightFace app (lazy singleton) ──────────────────────────────────────────
_face_app = None
_known_faces = None

def get_face_app():
    global _face_app
    if _face_app is None:
        log.info("Loading InsightFace buffalo_l model…")
        from insightface.app import FaceAnalysis
        _face_app = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
        log.info("InsightFace ready.")
    return _face_app

def load_known_faces(npz_path: Path) -> dict | None:
    if not npz_path.exists():
        log.error(f"faces.npz not found at {npz_path}")
        return None
    data = np.load(str(npz_path), allow_pickle=True)
    names   = data["names"]    # shape (N,)
    vectors = data["vectors"]  # shape (N, 512)
    counts = Counter(names.tolist())
    log.info(f"Loaded {len(names)} embeddings: {dict(counts)}")
    return {"names": names, "vectors": vectors}

def get_known_faces(npz_path: Path):
    global _known_faces
    if _known_faces is None:
        _known_faces = load_known_faces(npz_path)
    return _known_faces

# ── core recognition ───────────────────────────────────────────────────────────

def identify_faces_in_image(image_path: Path, npz_path: Path, threshold: float) -> list[str]:
    """
    Returns a list of names for every face found in the image.
    e.g. ["matthew", "gabriela"]  or  ["unknown"]  or  []
    """
    import cv2
    img = cv2.imread(str(image_path))
    if img is None:
        # Try PIL for HEIC / unusual formats
        try:
            from PIL import Image
            import numpy as _np
            pil_img = Image.open(image_path).convert("RGB")
            img = _np.array(pil_img)[:, :, ::-1]  # RGB→BGR
        except Exception:
            return []
    if img is None or img.size == 0:
        return []

    app = get_face_app()
    kf  = get_known_faces(npz_path)
    faces = app.get(img)
    if not faces:
        return []
    if kf is None:
        return ["unknown"] * len(faces)

    names_db   = kf["names"]
    vectors_db = kf["vectors"]
    results = []
    for face in faces:
        emb       = face.normed_embedding
        scores    = vectors_db @ emb
        best_idx  = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        if best_score >= threshold:
            results.append(str(names_db[best_idx]))
        else:
            results.append("unknown")
    return results

# ── destination folder logic ────────────────────────────────────────────────────

def decide_destination(names: list[str], output_root: Path) -> Path:
    """
    - No faces detected  → output_root/no_faces/
    - All unknown        → output_root/unknown/
    - One known person   → output_root/<name>/
    - Multiple known     → output_root/together/
    - Mix known+unknown  → output_root/together/
    """
    if not names:
        return output_root / "no_faces"
    known = [n for n in names if n != "unknown"]
    if not known:
        return output_root / "unknown"
    unique_known = sorted(set(known))
    if len(unique_known) == 1:
        return output_root / unique_known[0]
    return output_root / "together"

# ── file operations ────────────────────────────────────────────────────────────

def safe_dest_path(dest_dir: Path, src: Path) -> Path:
    """Return a non-colliding destination path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.exists():
        return dest
    stem, suffix = src.stem, src.suffix
    i = 1
    while True:
        candidate = dest_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1

# ── worker (runs in thread pool) ───────────────────────────────────────────────

def process_one(args_tuple):
    src, output_root, npz_path, threshold, action, dry_run = args_tuple
    try:
        names = identify_faces_in_image(src, npz_path, threshold)
        dest_dir = decide_destination(names, output_root)
        dest = safe_dest_path(dest_dir, src)
        tag = "/".join(sorted(set(names))) if names else "no_faces"

        if dry_run:
            return ("dry", src, dest, tag, names)

        if action == "move":
            shutil.move(str(src), str(dest))
        else:
            shutil.copy2(str(src), str(dest))

        return ("ok", src, dest, tag, names)
    except Exception as e:
        return ("err", src, None, str(e), [])

# ── enrollment helper ──────────────────────────────────────────────────────────

def enroll_best_faces(source_dir: Path, name: str, npz_path: Path, dry_run: bool):
    """
    Scan images in source_dir, find high-quality faces matching `name`,
    and add them to faces.npz.  Only adds faces with score >= ENROLL_MIN_SCORE
    AND bounding box >= ENROLL_MIN_BBOX_PX.
    """
    import cv2
    app = get_face_app()
    kf  = get_known_faces(npz_path) if npz_path.exists() else None

    new_embeddings = []
    images = list(source_dir.rglob("*"))
    images = [p for p in images if p.suffix.lower() in SUPPORTED_EXTS and p.is_file()]
    log.info(f"Scanning {len(images)} images for enrollment of '{name}'…")

    for img_path in images:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        faces = app.get(img)
        for face in faces:
            bbox = face.bbox  # [x1, y1, x2, y2]
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w < ENROLL_MIN_BBOX_PX or h < ENROLL_MIN_BBOX_PX:
                continue  # too small

            # Check if it already matches `name` well
            if kf is not None:
                emb    = face.normed_embedding
                scores = kf["vectors"] @ emb
                best_idx   = int(np.argmax(scores))
                best_score = float(scores[best_idx])
                matched_name = str(kf["names"][best_idx]) if best_score >= FACE_MATCH_THRESHOLD else "unknown"
                # Only enroll if already matching this name (no strangers)
                if matched_name != name:
                    continue
                if best_score < ENROLL_MIN_SCORE:
                    log.debug(f"  skip {img_path.name}: score {best_score:.3f} < {ENROLL_MIN_SCORE}")
                    continue
            else:
                # No existing db — enroll everything from this folder
                pass

            log.info(f"  → will enroll face from {img_path.name}  (bbox {w:.0f}×{h:.0f})")
            new_embeddings.append(face.normed_embedding)

    if not new_embeddings:
        log.info("No suitable faces found for enrollment.")
        return

    log.info(f"Found {len(new_embeddings)} new embedding(s) to add for '{name}'.")
    if dry_run:
        log.info("[dry-run] Would update faces.npz — skipping write.")
        return

    # Merge into existing npz
    if kf is not None:
        old_names   = list(kf["names"])
        old_vectors = list(kf["vectors"])
    else:
        old_names, old_vectors = [], []

    new_names   = old_names   + [name] * len(new_embeddings)
    new_vectors = old_vectors + new_embeddings

    np.savez(
        str(npz_path),
        names=np.array(new_names, dtype=object),
        vectors=np.array(new_vectors, dtype=np.float32),
    )
    final_counts = Counter(new_names)
    log.info(f"faces.npz updated: {dict(final_counts)}")
    log.info(f"REMEMBER: restart assistant_server.py to pick up new embeddings.")
    log.info(f"  sudo systemctl restart aubieeternal-assistant")

# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Organize photos by face recognition")
    parser.add_argument("--source",      type=Path, required=True,    help="Source directory")
    parser.add_argument("--output",      type=Path, default=DEFAULT_OUTPUT, help="Output root")
    parser.add_argument("--faces-npz",   type=Path, default=DEFAULT_FACES_NPZ)
    parser.add_argument("--threshold",   type=float, default=FACE_MATCH_THRESHOLD)
    parser.add_argument("--copy",        dest="action", action="store_const", const="copy", default="copy")
    parser.add_argument("--move",        dest="action", action="store_const", const="move")
    parser.add_argument("--enroll-best", action="store_true", help="Add best faces to faces.npz")
    parser.add_argument("--name",        help="Person name for --enroll-best")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--workers",     type=int, default=4)
    args = parser.parse_args()

    if not args.source.exists():
        log.error(f"Source directory not found: {args.source}")
        sys.exit(1)

    # ── enrollment mode ────────────────────────────────────────────────────────
    if args.enroll_best:
        if not args.name:
            log.error("--enroll-best requires --name")
            sys.exit(1)
        enroll_best_faces(args.source, args.name, args.faces_npz, args.dry_run)
        return

    # ── organize mode ──────────────────────────────────────────────────────────
    all_images = [
        p for p in args.source.rglob("*")
        if p.suffix.lower() in SUPPORTED_EXTS and p.is_file()
    ]
    log.info(f"Found {len(all_images)} images in {args.source}")
    log.info(f"Output → {args.output}  |  action={args.action}  |  threshold={args.threshold}")
    if args.dry_run:
        log.info("[DRY RUN — no files will be touched]")

    # Pre-load models before forking threads
    get_face_app()
    get_known_faces(args.faces_npz)

    work = [
        (img, args.output, args.faces_npz, args.threshold, args.action, args.dry_run)
        for img in all_images
    ]

    stats = defaultdict(int)
    errors = []

    # Use ThreadPoolExecutor (InsightFace is not fork-safe)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_one, w): w[0] for w in work}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            done += 1
            status, src, dest, tag, names = fut.result()
            if status == "err":
                errors.append((src, tag))
                stats["errors"] += 1
            else:
                stats[tag] += 1
            if done % 50 == 0 or done == len(all_images):
                log.info(f"  {done}/{len(all_images)} processed…")

    # ── summary ────────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print(f"  DONE — {len(all_images)} images processed")
    print("═" * 60)
    for tag, count in sorted(stats.items()):
        print(f"  {tag:<30}  {count:>5} photos")
    if errors:
        print(f"\n  ⚠  {len(errors)} errors:")
        for src, msg in errors[:20]:
            print(f"    {src.name}: {msg}")
    print("═" * 60)

    if not args.dry_run:
        print(f"\n  Sorted photos are in:  {args.output}/")
        print("  Subfolders created:")
        for folder in sorted(args.output.iterdir()):
            if folder.is_dir():
                count = sum(1 for _ in folder.iterdir())
                print(f"    {folder.name}/   ({count} files)")

if __name__ == "__main__":
    main()
