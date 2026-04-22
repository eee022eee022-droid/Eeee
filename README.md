---
title: NSFW Uncensored Photo
emoji: 🔞
colorFrom: gray
colorTo: red
sdk: gradio
sdk_version: 5.0.0
app_file: app.py
pinned: false
license: apache-2.0
short_description: Self-hosted text-to-image agent (Z-Image-Turbo), uncensored, 18+
hf_oauth: true
hf_oauth_scopes:
  - inference-api
---

# NSFW-Uncensored-photo

Self-hosted text-to-image "agent" that reproduces the behaviour of the
Hugging Face Space
[`Heartsync/NSFW-Uncensored-photo`](https://huggingface.co/spaces/Heartsync/NSFW-Uncensored-photo).

It loads **[`Tongyi-MAI/Z-Image-Turbo`](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)**
through `diffusers` and exposes it via a Gradio UI. No safety checker is wired
in — the model output is returned as-is.

> **18+.** Intended for adult, lawful, consensual content on your own
> infrastructure. You are responsible for complying with the model licence,
> Hugging Face ToS, and local law. Do **not** use it to generate CSAM,
> non-consensual deepfakes of real people, or any illegal material.

## How the original Space is built

Reading `app.py` of the reference Space, it's just:

1. **`diffusers.DiffusionPipeline.from_pretrained("Tongyi-MAI/Z-Image-Turbo", torch_dtype=torch.bfloat16)`** — loads the Z-Image-Turbo text-to-image model.
2. **`pipe.to("cuda")`** — moves it to the GPU assigned by HF Spaces.
3. **`@spaces.GPU`** — decorator that borrows a ZeroGPU slice per request.
4. **Gradio Blocks UI** — prompt textbox, width/height/steps/seed sliders, a gallery.
5. **Generate handler** calls `pipe(prompt, height, width, num_inference_steps, guidance_scale=0.0, generator=..., num_images_per_prompt=...)` and returns the PIL images to the gallery.

No NSFW-specific model is used; it's a plain fast diffusion model without a
safety checker. The "uncensored" part is simply that no filter is applied to
the output.

## Running locally (CUDA GPU recommended)

```bash
git clone https://github.com/eee022eee022-droid/Eeee.git
cd Eeee
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Optional: log in if the model ever becomes gated.
export HF_TOKEN=hf_xxx   # see .env.example

python app.py
# open http://127.0.0.1:7860
```

First launch downloads the Z-Image-Turbo weights (~several GB) into the
Hugging Face cache. A CUDA GPU with ≥12 GB VRAM is recommended for
1024×1024 output; CPU works but is very slow.

## Deploying as a Hugging Face Space (one-shot clone)

1. Create a new Space at https://huggingface.co/new-space
   - SDK: **Gradio**
   - Hardware: any GPU (or **ZeroGPU** — `@spaces.GPU` is already wired in).
2. Push this repository to the Space:
   ```bash
   git remote add space https://huggingface.co/spaces/<your-user>/<your-space>
   git push space main
   ```
3. If you want the flash-attn kernel used by the original Space, add a Space
   secret `USE_FLASH_ATTN=1` (only works on ZeroGPU hardware).

The `README.md` front-matter above is a valid HF Space config — the Space
will pick up `app_file: app.py` automatically.

## Configuration

| Env var              | Default                     | Purpose                              |
|----------------------|-----------------------------|--------------------------------------|
| `HF_TOKEN`           | _(unset)_                   | HF auth token for gated models.      |
| `MODEL_ID`           | `Tongyi-MAI/Z-Image-Turbo`  | Override the diffusion model.        |
| `USE_FLASH_ATTN`     | `0`                         | Use `kernels-community/vllm-flash-attn3`. |
| `GRADIO_SERVER_NAME` | `0.0.0.0`                   | Bind address for local run.          |
| `GRADIO_SERVER_PORT` | `7860`                      | Port for local run.                  |

See [`.env.example`](./.env.example).

## Files

- `app.py` — Gradio app + diffusion pipeline.
- `requirements.txt` — Python deps (Gradio, diffusers @ main, torch, spaces).
- `.env.example` — template for local config.
- `.gitignore` — ignores venvs, caches, checkpoints.
