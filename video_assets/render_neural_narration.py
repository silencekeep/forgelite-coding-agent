"""Render the demo narration with the open-source Qwen3-TTS model.

This is a release-asset helper, not a runtime dependency of ForgeLite. Install
``qwen-tts`` and a CUDA-enabled PyTorch build in an isolated environment before
running it. Model weights and generated audio belong under ``artifacts/`` and
must not be committed.
"""

from __future__ import annotations

import argparse
import random
import re
from pathlib import Path

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("video_assets/narration.md"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--speaker", default="Serena")
    parser.add_argument("--language", default="Chinese")
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--max-chars", type=int, default=150)
    parser.add_argument("--pause-ms", type=int, default=300)
    return parser.parse_args()


def narration_chunks(path: Path, max_chars: int) -> list[str]:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"(?m)^#.*$", "", source)
    source = source.replace("`", "").replace("“", "").replace("”", "")
    paragraphs = [re.sub(r"\s+", "", item) for item in re.split(r"\n\s*\n", source)]
    paragraphs = [item for item in paragraphs if item]

    chunks: list[str] = []
    for paragraph in paragraphs:
        sentences = [item for item in re.split(r"(?<=[。！？；])", paragraph) if item]
        current = ""
        for sentence in sentences:
            if current and len(current) + len(sentence) > max_chars:
                chunks.append(current)
                current = sentence
            else:
                current += sentence
        if current:
            chunks.append(current)
    if not chunks:
        raise ValueError(f"No narration text found in {path}")
    return chunks


def main() -> None:
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    model_kwargs: dict[str, object] = {"device_map": device, "dtype": dtype}
    if args.cache_dir:
        args.cache_dir.mkdir(parents=True, exist_ok=True)
        model_kwargs["cache_dir"] = str(args.cache_dir)

    chunks = narration_chunks(args.input, args.max_chars)
    print(f"Loading {args.model} on {device} ({dtype}); {len(chunks)} chunks")
    model = Qwen3TTSModel.from_pretrained(args.model, **model_kwargs)

    rendered: list[np.ndarray] = []
    sample_rate: int | None = None
    for index, chunk in enumerate(chunks, start=1):
        print(f"[{index}/{len(chunks)}] {chunk}")
        waves, current_rate = model.generate_custom_voice(
            text=chunk,
            speaker=args.speaker,
            language=args.language,
        )
        if sample_rate is not None and current_rate != sample_rate:
            raise RuntimeError("Qwen3-TTS returned inconsistent sample rates")
        sample_rate = current_rate
        rendered.append(np.asarray(waves[0], dtype=np.float32).reshape(-1))

    assert sample_rate is not None
    pause = np.zeros(round(sample_rate * args.pause_ms / 1000), dtype=np.float32)
    joined: list[np.ndarray] = []
    for index, wave in enumerate(rendered):
        joined.append(wave)
        if index < len(rendered) - 1:
            joined.append(pause)
    audio = np.concatenate(joined)
    peak = float(np.max(np.abs(audio)))
    if peak > 0.98:
        audio *= 0.98 / peak

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.output, audio, sample_rate, subtype="PCM_16")
    duration = len(audio) / sample_rate
    print(f"Wrote {args.output} ({duration:.3f}s, {sample_rate} Hz, peak {peak:.3f})")


if __name__ == "__main__":
    main()
