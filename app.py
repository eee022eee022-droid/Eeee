"""NSFW-Uncensored-photo — text-to-image agent.

This is a self-hosted clone of the Hugging Face Space
https://huggingface.co/spaces/Heartsync/NSFW-Uncensored-photo

Model: Tongyi-MAI/Z-Image-Turbo (fast text-to-image diffusion pipeline).

- On a Hugging Face Space with ZeroGPU, the `spaces` package is available and
  the generate function is decorated with `@spaces.GPU` to borrow a GPU per
  request.
- Locally, if `spaces` is not installed, the decorator becomes a no-op so the
  same file runs on a local machine with a CUDA-capable GPU (or CPU, slowly).

No safety checker is applied; the pipeline outputs whatever the model
produces. The operator is responsible for complying with the model licence
and applicable laws.
"""

from __future__ import annotations

import os
import random

# IMPORTANT: `spaces` must be imported BEFORE any CUDA-related package
# (torch, diffusers, ...) on Hugging Face Spaces ZeroGPU. Otherwise the
# package raises:
#   RuntimeError: CUDA has been initialized before importing the `spaces` package.
try:
    import spaces  # type: ignore[import-not-found]

    HAS_SPACES = True
except ImportError:  # local / non-HF-Spaces environment
    HAS_SPACES = False

    class _SpacesStub:
        @staticmethod
        def GPU(*dargs, **dkwargs):  # noqa: N802 - mimic spaces.GPU API
            def decorator(func):
                return func

            # support both @spaces.GPU and @spaces.GPU(duration=...)
            if dargs and callable(dargs[0]):
                return dargs[0]
            return decorator

    spaces = _SpacesStub()  # type: ignore[assignment]


import gradio as gr  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from diffusers import DiffusionPipeline  # noqa: E402


MAX_SEED = np.iinfo(np.int32).max
MODEL_ID = os.environ.get("MODEL_ID", "Tongyi-MAI/Z-Image-Turbo")


def _resolve_min_age() -> int:
    """Configurable age threshold for the entry age-gate.

    Read from the ``MIN_AGE`` env var; defaults to 18. Clamped to >= 18 — the
    *generation* rules (no minors / no non-consensual / etc.) always apply
    regardless of this knob, because those are legal limits, not preferences.
    """
    raw = os.environ.get("MIN_AGE", "18").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 18
    return max(18, value)


MIN_AGE = _resolve_min_age()

prompt_examples = [
    "Moody mature anime scene of two lovers kissing under neon rain, sensual atmosphere",
    "A woman in a blue hanbok sits on a wooden floor, her legs folded beneath her, gazing out of a window, the sunlight highlighting the graceful lines of her clothing.",
    "A cinematic portrait of a confident woman in a sleek black evening gown, dramatic rim lighting, shallow depth of field.",
    "Close-up of a couple embracing on a rainy Tokyo street at night, neon reflections in puddles, film grain.",
    "Ultra-detailed studio portrait of a red-haired model in vintage lace lingerie, soft window light, 85mm lens.",
    "A steamy shower scene, water droplets on glass, warm golden light, intimate mood.",
    "A tasteful boudoir photo of a woman reclining on silk sheets, soft morning light, film look.",
    "A fantasy elf queen in translucent silk robes, moonlit forest clearing, fireflies, cinematic.",
    "Anime illustration of two lovers on a balcony at sunset, wind blowing through her dress, Makoto Shinkai style.",
    "Oil painting of Venus rising from the sea, classical composition, baroque lighting.",
]


def _build_pipeline() -> DiffusionPipeline:
    print(f"Loading {MODEL_ID} pipeline...")
    kwargs: dict = {"torch_dtype": torch.bfloat16, "low_cpu_mem_usage": False}

    # Optional flash-attn kernel (only available in HF Spaces ZeroGPU env).
    if os.environ.get("USE_FLASH_ATTN", "").lower() in {"1", "true", "yes"}:
        kwargs["attn_implementation"] = "kernels-community/vllm-flash-attn3"

    pipe = DiffusionPipeline.from_pretrained(MODEL_ID, **kwargs)
    if torch.cuda.is_available():
        pipe.to("cuda")
    return pipe


pipe = _build_pipeline()


def get_random_prompt() -> str:
    return random.choice(prompt_examples)


@spaces.GPU(duration=120)
def generate_image(
    prompt: str,
    height: int,
    width: int,
    num_inference_steps: int,
    seed: int,
    randomize_seed: bool,
    num_images: int,
):
    if not prompt:
        raise gr.Error("Please enter a prompt.")

    if randomize_seed:
        seed = random.randint(0, MAX_SEED)

    num_images = min(max(1, int(num_images)), 4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    generator = torch.Generator(device).manual_seed(int(seed))

    result = pipe(
        prompt=prompt,
        height=int(height),
        width=int(width),
        num_inference_steps=int(num_inference_steps),
        guidance_scale=0.0,
        generator=generator,
        max_sequence_length=1024,
        num_images_per_prompt=num_images,
        output_type="pil",
    )
    return result.images, int(seed)


css = """
.gradio-container { max-width: 1200px !important; margin: 0 auto !important; }
#title { text-align: center; margin-bottom: 0.5rem; }
.warning-box { background: #FEF3C7; border: 1px solid #F59E0B; border-radius: 8px;
    padding: 10px 16px; margin: 8px auto 16px auto; max-width: 900px; text-align: center;
    color: #92400E; font-weight: 600; }
.age-gate { max-width: 720px; margin: 40px auto; padding: 28px 32px;
    border: 2px solid #DC2626; border-radius: 12px; background: #FEF2F2; }
.age-gate h2 { color: #991B1B; margin-top: 0; }
.age-gate ul { color: #1F2937; line-height: 1.6; }
.age-gate-error { color: #991B1B; font-weight: 700; }
"""


def _build_age_gate_html(min_age: int) -> str:
    return f"""
<div class="age-gate">
  <h2>🔞 Adults Only — {min_age}+</h2>
  <p>This site generates AI imagery that may include nudity and sexually
  explicit content. By entering you confirm <b>all</b> of the following:</p>
  <ul>
    <li>You are <b>at least {min_age} years old</b> (or the age of majority in
    your jurisdiction, whichever is higher) and accessing this content is
    legal where you are.</li>
    <li>You will <b>not</b> attempt to generate, request, or share sexual,
    suggestive, or nude imagery of <b>minors</b> (anyone under 18, real or
    fictional). Such content is illegal in most jurisdictions and is strictly
    prohibited here.</li>
    <li>You will <b>not</b> generate non-consensual sexual imagery of real
    people (deepfakes, face-swaps, look-alikes), including celebrities.</li>
    <li>You will <b>not</b> generate content depicting non-consensual acts,
    bestiality, or any other illegal material.</li>
    <li>You take full responsibility for any prompts you submit and any
    images you save, share, or distribute.</li>
  </ul>
  <p>If you cannot agree to all of the above — close this tab now.</p>
</div>
"""


AGE_GATE_HTML = _build_age_gate_html(MIN_AGE)


def _enter_app(agreed: bool):
    if not agreed:
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(
                value=(
                    f"<p class='age-gate-error'>You must confirm you are "
                    f"{MIN_AGE}+ and agree to the rules above before "
                    f"entering.</p>"
                ),
                visible=True,
            ),
        )
    return (
        gr.update(visible=False),
        gr.update(visible=True),
        gr.update(value="", visible=False),
    )


with gr.Blocks(css=css, title="NSFW-Uncensored-photo") as demo:
    with gr.Group(visible=True) as gate_group:
        gr.HTML(AGE_GATE_HTML)
        gate_agree = gr.Checkbox(
            label=f"I am {MIN_AGE}+ and agree to all of the above.",
            value=False,
        )
        gate_error = gr.HTML(value="", visible=False)
        gate_enter = gr.Button("Enter", variant="primary", size="lg")

    with gr.Group(visible=False) as main_group:
        gr.Markdown("# NSFW-Uncensored-photo", elem_id="title")
        gr.Markdown(
            f"Powered by **Z-Image-Turbo** — text-to-image generation. "
            f"Adult content ({MIN_AGE}+) — operator is responsible for "
            f"lawful use. **No minors. No non-consensual deepfakes of real "
            f"people. No illegal content.**"
        )
        gr.HTML(
            "<div class='warning-box'>Free ZeroGPU has a per-user quota. "
            "Sign in with Hugging Face for a higher limit.</div>"
        )
        # HF Login button — ZeroGPU gives signed-in users a much larger
        # daily quota than anonymous IP-based access. Only meaningful inside
        # a Hugging Face Space; on local runs it's silently a no-op.
        try:
            gr.LoginButton(
                value="Sign in with Hugging Face (extra GPU quota)",
                size="sm",
            )
        except Exception:  # noqa: BLE001 — some Gradio versions / non-Space envs
            pass

        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=350):
                prompt_input = gr.Textbox(
                    label="Prompt",
                    placeholder="Describe the image you want to create...",
                    lines=4,
                )
                random_button = gr.Button(
                    "🎲 Random prompt", variant="secondary"
                )
                with gr.Row():
                    height_input = gr.Slider(
                        512, 2048, 1024, step=64, label="Height"
                    )
                    width_input = gr.Slider(
                        512, 2048, 1024, step=64, label="Width"
                    )
                num_images_input = gr.Slider(
                    1, 4, 2, step=1, label="Number of Images"
                )
                with gr.Accordion("Advanced Options", open=False):
                    steps_slider = gr.Slider(
                        minimum=1,
                        maximum=30,
                        step=1,
                        value=18,
                        label="Inference Steps",
                    )
                    seed_input = gr.Slider(
                        label="Seed",
                        minimum=0,
                        maximum=MAX_SEED,
                        step=1,
                        value=42,
                    )
                    randomize_seed_checkbox = gr.Checkbox(
                        label="Randomize Seed", value=True
                    )
                generate_button = gr.Button(
                    "✨ Generate", variant="primary", size="lg"
                )
                used_seed_output = gr.Number(label="Seed Used", interactive=False)

            with gr.Column(scale=1, min_width=350):
                output_gallery = gr.Gallery(
                    label="Generated Images",
                    height=600,
                    columns=2,
                    object_fit="contain",
                    show_label=True,
                )

    gate_enter.click(
        fn=_enter_app,
        inputs=[gate_agree],
        outputs=[gate_group, main_group, gate_error],
    )
    random_button.click(fn=get_random_prompt, outputs=[prompt_input])
    generate_button.click(
        fn=generate_image,
        inputs=[
            prompt_input,
            height_input,
            width_input,
            steps_slider,
            seed_input,
            randomize_seed_checkbox,
            num_images_input,
        ],
        outputs=[output_gallery, used_seed_output],
    )


if __name__ == "__main__":
    demo.queue().launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
    )
