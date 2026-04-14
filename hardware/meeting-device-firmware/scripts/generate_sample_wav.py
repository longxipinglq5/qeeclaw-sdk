#!/usr/bin/env python3
"""
生成一个可用于会议设备联调的示例 WAV 文件。
"""

import argparse
import math
import wave
from pathlib import Path


def clamp_sample(value: float) -> int:
    return max(-32767, min(32767, int(value)))


def generate_sine_wave(output_file: Path, duration_seconds: float, frequency: float, sample_rate: int) -> None:
    total_samples = int(duration_seconds * sample_rate)
    amplitude = 0.25 * 32767

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_file), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for index in range(total_samples):
            sample = amplitude * math.sin(2 * math.pi * frequency * index / sample_rate)
            frames.extend(clamp_sample(sample).to_bytes(2, byteorder="little", signed=True))

        wav_file.writeframes(bytes(frames))


def main() -> None:
    parser = argparse.ArgumentParser(description="生成会议设备联调示例 WAV 文件")
    parser.add_argument(
        "--output",
        default="scripts/output/sample.wav",
        help="输出 WAV 文件路径",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=6.0,
        help="音频时长（秒）",
    )
    parser.add_argument(
        "--frequency",
        type=float,
        default=440.0,
        help="正弦波频率（Hz）",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="采样率（Hz）",
    )
    args = parser.parse_args()

    output_file = Path(args.output).expanduser()
    generate_sine_wave(
        output_file=output_file,
        duration_seconds=args.duration,
        frequency=args.frequency,
        sample_rate=args.sample_rate,
    )
    print(f"Generated sample WAV: {output_file.resolve()}")


if __name__ == "__main__":
    main()
