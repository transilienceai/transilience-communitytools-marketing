"""
Blend Handler — scan folders recursively, optionally follow a sequence file,
or let Claude Vision determine optimal order, then output a numbered folder
ready for `python cli.py create`.
"""

import difflib
import re
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.table import Table

from .screenshot_handler import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

console = Console()

MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS


def scan_recursive(input_path: Path) -> List[Path]:
    """Recursively find all image/video files under *input_path*."""
    if input_path.is_file():
        if input_path.suffix.lower() in MEDIA_EXTENSIONS:
            return [input_path]
        return []

    found = []
    for ext in MEDIA_EXTENSIONS:
        found.extend(input_path.rglob(f"*{ext}"))
        found.extend(input_path.rglob(f"*{ext.upper()}"))

    # Deduplicate (case-insensitive glob overlap) and sort by full path
    seen = set()
    unique = []
    for p in sorted(found, key=lambda p: p.as_posix()):
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(p)
    return unique


def parse_sequence_source(sequence_path: Path) -> List[str]:
    """
    Parse sequence references from a single markdown file **or** a directory
    of markdown files (sorted by filename).

    Each markdown file is scanned for lines containing media file references.

    Handles:
      - Numbered lists:  ``1. Scene 1 (Problem): 01-scene-problem.jpg``
      - Bullet lists:    ``- tmp/screenshots/home-hero-1920x1080.png``
      - Any line containing a recognized media extension
      - Skips headings, blank lines, commentary without file refs
    """
    if sequence_path.is_dir():
        md_files = sorted(sequence_path.glob("*.md"), key=lambda p: p.name.lower())
        if not md_files:
            console.print(f"[yellow]No .md files found in {sequence_path}[/yellow]")
            return []
        console.print(f"Found {len(md_files)} sequence file(s) in {sequence_path.name}/")
        references: List[str] = []
        for md_file in md_files:
            refs = _parse_single_md(md_file)
            if refs:
                console.print(f"  {md_file.name}: {len(refs)} reference(s)")
            references.extend(refs)
        return references
    else:
        return _parse_single_md(sequence_path)


def _parse_single_md(md_path: Path) -> List[str]:
    """Extract file references from a single markdown file."""
    text = md_path.read_text(encoding="utf-8")
    references: List[str] = []

    ext_pattern = "|".join(re.escape(ext) for ext in MEDIA_EXTENSIONS)
    file_ref_re = re.compile(rf"(\S*(?:{ext_pattern}))", re.IGNORECASE)

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = file_ref_re.search(stripped)
        if match:
            references.append(match.group(1))

    return references


def fuzzy_match(reference: str, all_files: List[Path]) -> Optional[Path]:
    """
    Match a sequence *reference* string to one of the discovered files.

    Strategy (in order):
      1. Exact basename match
      2. Stem-contains match (either direction)
      3. difflib.SequenceMatcher with threshold >= 0.6
    """
    ref_basename = Path(reference).name
    ref_stem = Path(reference).stem.lower()

    # 1. Exact basename
    for p in all_files:
        if p.name == ref_basename:
            return p

    # 2. Stem-contains (either direction)
    for p in all_files:
        p_stem = p.stem.lower()
        if ref_stem in p_stem or p_stem in ref_stem:
            return p

    # 3. Fuzzy ratio
    best_score = 0.0
    best_match = None
    for p in all_files:
        score = difflib.SequenceMatcher(None, ref_stem, p.stem.lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = p
    if best_score >= 0.6 and best_match is not None:
        return best_match

    return None


def blend_content(
    input_path: Path,
    output_dir: Path,
    sequence_path: Optional[Path] = None,
    bookend_path: Optional[Path] = None,
    include_unsequenced: bool = True,
    ai_order: bool = True,
    context: str = "",
    tone: str = "professional and engaging",
    storyline: str = "",
    dry_run: bool = False,
) -> List[Path]:
    """
    Main blend orchestrator.

    1. Scan input recursively
    2. If sequence file: parse it, fuzzy-match to found files,
       separate sequenced vs unsequenced
    3. If no sequence file: all files are "unsequenced"
    4. AI-order unsequenced files via reorder_items_with_vision()
       (or filename sort if ai_order=False)
    5. Build final list: bookend (opening) -> sequenced -> unsequenced -> bookend (closing)
    6. Copy files to output dir with ``{i:02d}-{original_stem}{ext}`` naming
    7. Print summary table

    Returns list of copied file paths in final order.
    """
    # ── 1. Scan ──
    all_files = scan_recursive(input_path)

    # Exclude the bookend itself from scanned files (it's added separately)
    if bookend_path:
        bookend_resolved = bookend_path.resolve()
        all_files = [f for f in all_files if f.resolve() != bookend_resolved]

    if not all_files:
        console.print(f"[red]No media files found under {input_path}[/red]")
        return []

    console.print(f"[bold]Found {len(all_files)} media file(s) under {input_path}[/bold]")

    # ── 1b. Deduplicate near-identical images (same page at different sizes) ──
    # e.g. home.png, home-hero.png, home-hero-1920x1080.png → keep largest
    def _stem_group(p: Path) -> str:
        """Normalize stem to group size variants: home-hero-1920x1080 → home-hero."""
        stem = p.stem.lower()
        # Strip common resolution suffixes
        stem = re.sub(r'[-_]?\d{3,4}x\d{3,4}$', '', stem)
        return stem

    stem_groups: dict = {}
    for f in all_files:
        key = _stem_group(f)
        if key not in stem_groups:
            stem_groups[key] = []
        stem_groups[key].append(f)

    deduped_files: List[Path] = []
    removed_dupes = 0
    for key, group in stem_groups.items():
        if len(group) > 1:
            # Keep the largest file (highest resolution)
            best = max(group, key=lambda p: p.stat().st_size)
            deduped_files.append(best)
            removed_dupes += len(group) - 1
        else:
            deduped_files.append(group[0])

    # Sort to maintain stable order
    deduped_files.sort(key=lambda p: p.as_posix())

    if removed_dupes:
        console.print(f"[dim]Deduplicated: removed {removed_dupes} size variants, kept {len(deduped_files)} unique images[/dim]")
    all_files = deduped_files

    # ── 2. Sequence matching ──
    sequenced: List[Path] = []
    unsequenced: List[Path] = list(all_files)

    if sequence_path:
        refs = parse_sequence_source(sequence_path)
        console.print(f"Parsed {len(refs)} total reference(s) from {sequence_path}")

        matched_set = set()
        for ref in refs:
            match = fuzzy_match(ref, all_files)
            if match:
                resolved = match.resolve()
                # Skip if already matched (avoid duplicates from multiple sequence refs)
                if resolved in matched_set:
                    console.print(f"  [dim]Skipped duplicate[/dim] {ref} -> {match.name}")
                    continue
                sequenced.append(match)
                matched_set.add(resolved)
                console.print(f"  [green]Matched[/green] {ref} -> {match.name}")
            else:
                console.print(f"  [yellow]No match[/yellow] for: {ref}")

        # Unsequenced = everything not matched
        if include_unsequenced:
            unsequenced = [f for f in all_files if f.resolve() not in matched_set]
        else:
            unsequenced = []

    # ── 3/4. Order unsequenced ──
    if unsequenced and ai_order:
        from .veo_pipeline import reorder_items_with_vision

        # Build items as List[Tuple[Path, str]] expected by reorder_items_with_vision
        items: List[Tuple[Path, str]] = []
        for f in unsequenced:
            ftype = "video" if f.suffix.lower() in VIDEO_EXTENSIONS else "image"
            items.append((f, ftype))

        ordered = reorder_items_with_vision(items, context, tone, storyline)
        unsequenced = [path for path, _ in ordered]
    elif unsequenced:
        # Filename sort
        unsequenced.sort(key=lambda p: p.name.lower())

    # ── 5. Build final list (interleave by source folder) ──
    combined = sequenced + unsequenced
    # Group files by their parent folder so screenshots/ and generated/ get mixed
    from collections import OrderedDict
    folder_buckets: OrderedDict[str, List[Path]] = OrderedDict()
    for f in combined:
        folder_key = str(f.parent)
        if folder_key not in folder_buckets:
            folder_buckets[folder_key] = []
        folder_buckets[folder_key].append(f)

    final: List[Path] = []
    if bookend_path:
        final.append(bookend_path)

    if len(folder_buckets) > 1:
        # Round-robin interleave across folders
        bucket_iters = {k: iter(v) for k, v in folder_buckets.items()}
        bucket_remaining = {k: len(v) for k, v in folder_buckets.items()}
        total = len(combined)
        bucket_counts = {k: 0 for k in folder_buckets}

        for _ in range(total):
            # Pick the folder that is most "behind" its fair share
            best_key = None
            best_deficit = -1
            for k in folder_buckets:
                if bucket_remaining[k] <= 0:
                    continue
                target_ratio = bucket_counts[k] / max(len(folder_buckets[k]), 1)
                deficit = 1.0 - target_ratio  # higher = more behind
                if deficit > best_deficit:
                    best_deficit = deficit
                    best_key = k
            if best_key is None:
                break
            final.append(next(bucket_iters[best_key]))
            bucket_counts[best_key] += 1
            bucket_remaining[best_key] -= 1
    else:
        final.extend(combined)

    if bookend_path:
        final.append(bookend_path)

    if not final:
        console.print("[red]No files to blend.[/red]")
        return []

    # ── Summary table ──
    table = Table(title="Blend Order", show_header=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Output Name", style="blue")
    table.add_column("Source", style="white")
    table.add_column("Type", style="magenta", width=8)

    # Determine zero-pad width
    pad = len(str(len(final) - 1))

    copied: List[Path] = []
    for i, src in enumerate(final):
        ext = src.suffix
        # For bookend copies, tag them
        if bookend_path and i == 0:
            stem = f"{src.stem}-intro"
        elif bookend_path and i == len(final) - 1:
            stem = f"{src.stem}-closing"
        else:
            stem = src.stem

        out_name = f"{i:0{pad}d}-{stem}{ext}"
        ftype = "video" if src.suffix.lower() in VIDEO_EXTENSIONS else "image"
        table.add_row(str(i), out_name, str(src), ftype)

        if not dry_run:
            dest = output_dir / out_name
            copied.append(dest)

    console.print(table)

    # ── 6. Copy files ──
    if dry_run:
        console.print(f"\n[yellow]DRY RUN — would copy {len(final)} files to {output_dir}/[/yellow]")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)

    for i, src in enumerate(final):
        ext = src.suffix
        if bookend_path and i == 0:
            stem = f"{src.stem}-intro"
        elif bookend_path and i == len(final) - 1:
            stem = f"{src.stem}-closing"
        else:
            stem = src.stem

        out_name = f"{i:0{pad}d}-{stem}{ext}"
        dest = output_dir / out_name
        shutil.copy2(str(src), str(dest))

    console.print(f"\n[green]Copied {len(final)} files to {output_dir}/[/green]")
    console.print(f"[dim]Ready for: python cli.py create {output_dir}/ -o video.mp4[/dim]")

    return copied
