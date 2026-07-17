from __future__ import annotations

import io
import os
import threading
from typing import Optional

import numpy as np

SAMPLE_RATE = 16000


class SpeakerService:
    """
    Extracts speaker embeddings from WAV audio using pyannote/embedding.

    The model is loaded lazily on first call and cached for the process
    lifetime.  Requires HF_TOKEN to be set in the environment.
    """

    _model = None
    _lock  = threading.Lock()

    @classmethod
    def _get_model(cls):
        with cls._lock:
            if cls._model is not None:
                return cls._model

            hf_token = os.environ.get("HF_TOKEN")
            if not hf_token:
                raise RuntimeError(
                    "HF_TOKEN is not set. Speaker profile extraction requires a "
                    "HuggingFace access token that has accepted the "
                    "pyannote/embedding model terms at huggingface.co."
                )

            try:
                from pyannote.audio import Inference
                from huggingface_hub import login
                import torch
            except ImportError as exc:
                raise RuntimeError(
                    f"pyannote.audio is required for speaker profiles: {exc}"
                ) from exc

            login(token=hf_token, add_to_git_credential=False)

            # Force CPU to avoid clashing with Whisper's GPU session
            saved = os.environ.get("CUDA_VISIBLE_DEVICES")
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            try:
                model = Inference("pyannote/embedding", window="whole")
                model.to(torch.device("cpu"))
            finally:
                if saved is None:
                    os.environ.pop("CUDA_VISIBLE_DEVICES", None)
                else:
                    os.environ["CUDA_VISIBLE_DEVICES"] = saved

            cls._model = model
            return cls._model

    def extract_embedding(self, wav_bytes: bytes) -> list[float]:
        """
        Given raw WAV bytes, return a speaker embedding as a list of floats.
        Resamples to 16 kHz mono if necessary.
        """
        import torch
        import soundfile as sf

        audio, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != SAMPLE_RATE:
            target_len = int(len(audio) * SAMPLE_RATE / sr)
            indices    = np.linspace(0, len(audio) - 1, target_len)
            audio      = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

        model    = self._get_model()
        waveform = torch.from_numpy(audio).unsqueeze(0).float()
        with torch.no_grad():
            emb = model({"waveform": waveform, "sample_rate": SAMPLE_RATE})

        arr = emb.squeeze()
        if hasattr(arr, "cpu"):
            arr = arr.cpu().numpy()
        return arr.astype(np.float32).tolist()

    @property
    def available(self) -> bool:
        return bool(os.environ.get("HF_TOKEN"))
