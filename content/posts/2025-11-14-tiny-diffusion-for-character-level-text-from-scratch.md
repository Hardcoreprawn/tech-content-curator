---
action_run_id: '19379755769'
article_quality:
  dimensions:
    citations: 100.0
    code_examples: 0.0
    length: 100.0
    readability: 61.0
    source_citation: 100.0
    structure: 40.0
    tone: 100.0
  overall_score: 63.2
  passed_threshold: false
cover:
  alt: 'Tiny Diffusion for Character-Level Text: From Scratch'
  image: images/2025-11-14-tiny-diffusion-for-character-level-text-from-scratch.png
date: 2025-11-14T23:14:58+0000
generation_costs:
  content_generation: 0.00219465
  title_generation: 0.0014079
generator: General Article Generator
icon: images/2025-11-14-tiny-diffusion-for-character-level-text-from-scratch-icon.png
illustrations_count: 0
models_used:
  content: gpt-5-mini
  enrichment: gpt-5-nano
  title: gpt-5-nano
reading_time: 8 min read
sources:
- author: nathan-barry
  platform: hackernews
  quality_score: 0.65
  url: https://github.com/nathan-barry/tiny-diffusion
summary: 'Translating that success to text is not straightforward: language is discrete,
  long-range, and syntactically structured.'
tags:
- machine learning
- diffusion models
- natural language processing
- text generation
- transformers
title: 'Tiny Diffusion for Character-Level Text: From Scratch'
word_count: 1561
---

> **Attribution:** This article was based on content by **@nathan-barry** on **GitHub**.  
> Original: https://github.com/nathan-barry/tiny-diffusion

Introduction

Diffusion models have reshaped generative AI for images and audio by learning to reverse a gradual noising process, producing samples of striking quality. Translating that success to text is not straightforward: language is discrete, long-range, and syntactically structured. Tiny Diffusion — a compact, from-scratch character-level text diffusion model by Nathan Barry (source: Hacker News / GitHub) — is a hands-on experiment that explores this space with a 10.7M-parameter transformer trained on Tiny Shakespeare. It’s small enough to run locally, which makes it a useful testbed for researchers and practitioners who want to poke at the end-to-end pipeline for text diffusion without large compute budgets.

In this article you’ll learn:

- How diffusion ideas map to discrete text.
- What Tiny Diffusion does differently and why a character-level approach matters.
- Practical tips for implementing, training, and evaluating text diffusion models.
- Where diffusion fits in the current NLP landscape and potential use cases.

Key Takeaways

- Diffusion for text typically operates in a continuous space (embeddings or latents) or uses relaxed discrete methods; Tiny Diffusion experiments with characters to simplify the token layer.
- Non-autoregressive diffusion models offer benefits for controllability and robustness, but autoregressive models still lead in sample quality and efficiency on most text-generation tasks.
- Lightweight, from-scratch projects (like Tiny Diffusion) are valuable as reproducible learning platforms; use them to explore noise schedules, sampling strategies (DDIM), and hybrid architectures.

> Background: Diffusion models iteratively corrupt data with noise and learn a reverse process to denoise and generate new samples.

Credit: Tiny Diffusion is a project by Nathan Barry, discussed on Hacker News and available at https://github.com/nathan-barry/tiny-diffusion.

Main Concepts

What is a diffusion model?
Diffusion models learn to generate data by modeling the reverse of a noising process. A clean sample x0 (e.g., an image or sentence embedding) is corrupted through T timesteps into xt by gradually adding noise. A neural network then learns to predict either the original x0 or the noise at each timestep to reverse the process. The classic continuous formulation is the Denoising Diffusion Probabilistic Model (DDPM) (Ho et al., 2020), built on early ideas from Sohl-[Dickstein et al. (2015)](https://doi.org/10.3386/w21351). There's also DDIM (Denoising Diffusion Implicit Models) (Song et al., 2020) which yields faster and deterministic sampling in some settings.

Why is text harder?
Text is discrete — you can’t simply “add Gaussian noise” to a token in the same way you do to pixels. Methods to handle this include:

- Diffusing in continuous embeddings: add noise to token embeddings or to a learned latent space and decode afterward (Rombach et al., 2022).
- Discrete diffusion with relaxations: model discrete token transitions directly or use soft relaxations like Gumbel-softmax for differentiability.
- Hybrid approaches: combine autoregressive decoders with diffusion-based proposals (Li et al., 2022).

Character-level vs. token-level
Tiny Diffusion uses a character-level vocabulary. That reduces vocabulary size and avoids dealing with subword tokenization models (like byte-pair encoding). It makes an exploratory end-to-end implementation simpler but places the burden on the model to assemble characters into coherent, long-range structures (words, syntax). With a small dataset such as Tiny Shakespeare, this is an acceptable tradeoff to explore modeling choices without heavy engineering.

How Tiny Diffusion likely works (implementation snapshot)

- Backbone: a compact transformer inspired by NanoGPT (a minimal GPT-style implementation).
- Data: Tiny Shakespeare — short, Shakespearean text snippets useful for quick iterations.
- Forward process: corrupt a character embedding sequence across timesteps (probably with Gaussian noise injected into embeddings).
- Objective: learn to predict the clean embedding or the injected noise (standard DDPM objective).
- Sampling: run the learned reverse process through T steps (DDIM-style sampling may be used for speed).
- Size: about 10.7 million parameters, enabling local experimentation on consumer hardware.

Practical Applications and Use Cases

1. Rapid prototyping and education
   Tiny Diffusion is ideal for learning how diffusion training loops, schedules, and samplers behave on text data. Students and engineers can inspect intermediate outputs, tune schedules, or explore discrete relaxations without cloud-scale infrastructure.

1. Controlled text editing and denoising
   Diffusion models are naturally suited to denoising tasks. A text diffusion model could be adapted for error correction, style transfer, or fill-in-the-blank editing where non-autoregressive denoising preserves global coherence while allowing controlled transformations.

1. Robust generation under noise
   In settings with noisy or incomplete input (OCR output, partial transcripts), a diffusion-based denoiser in embedding or latent space can be more robust than autoregressive decoders, because it explicitly models corruption and reconstruction.

Best Practices and Practical Insights

Noise space: embeddings or discrete?

- Start in continuous embedding space. It avoids the combinatorial complexity of discrete diffusion and lets you reuse DDPM machinery. If you want truly discrete generation, consider Gumbel-softmax relaxations or categorical diffusion techniques, but expect training instability.
  Noise schedule and timesteps
- The choice of noise schedule (linear, cosine) and number of timesteps T matters. For toy experiments, T in the hundreds is common; for faster sampling, use DDIM (Song et al., 2020). Try cosine schedules initially since they often stabilize training (Ho et al., 2020).
  Model objective
- Use the standard reweighted DDPM loss (predicting noise) as a baseline. For discrete targets or token probabilities, experiments may use cross-entropy targets at the final decoder step.
  Sampling speed
- Use DDIM or fewer reverse steps to boost sampling speed. When exploring quality vs time, compare full DDPM sampling to DDIM and to a small autoregressive baseline like NanoGPT’s comparable-sized model.
  Evaluation
- Evaluate both quantitative metrics (perplexity, n-gram overlap, BLEU-like metrics) and human judgments for coherence. Diffusion outputs can look locally plausible yet fail on long-range structure; human checks are essential.
  Reproducibility and scaling
- Log random seeds, batch sizes, and optimizer settings. Small models are sensitive to learning rate and weight decay. Training longer on more data typically helps more than aggressive scaling of model size in this constrained setup.

Comparison to autoregressive models

Autoregressive models (AR, e.g., GPT-style models) predict the next token conditioned on previous tokens. They remain dominant for text generation because they are conceptually aligned with language generation and train efficiently on maximum likelihood objectives. Diffusion approaches are appealing for non-autoregressive sampling, better controllability, and natural denoising but currently lag behind AR models in sample quality for open-ended text (Li et al., 2022).

Tiny Diffusion fits into the landscape as a lightweight testbed. At 10.7M parameters and character-level input, it is not intended to beat GPT-style models at fluency; rather, it provides an accessible laboratory to test hypotheses about noise schedules, embeddings vs. latents, and sampling strategies.

Implications & Research Context

Diffusion-based text modeling is an active research niche. Work such as Diffusion-LM (Li et al., 2022) shows that diffusion can be competitive for controllable generation tasks when carefully engineered. Latent diffusion (Rombach et al., 2022) demonstrates gains by performing diffusion in compressed continuous spaces, which is a promising direction for text as well: learn an autoencoder that maps text to a dense latent, diffuse in that space, then decode back to tokens.

Fundamentally, the challenges for text are:

- Discreteness and decoding: how to go from noisy continuous representations back to discrete tokens cleanly.
- Long-range dependencies: characters spread linguistic information across many tokens.
- Evaluation: distributional metrics often miss subtle coherence and factuality errors.

Tiny Diffusion’s value is not in pushing SOTA but in making these tradeoffs visible to learners and researchers who want to iterate rapidly.

Actionable Recommendations

- If you’re experimenting locally, start character-level as Tiny Diffusion does: it reduces engineering for tokenization and speeds up iteration.
- Use embedding-space diffusion first. It’s simpler and leverages continuous DDPM objectives.
- Try DDIM sampling for faster outputs and experiment with a small number of reverse steps to find a quality/time tradeoff.
- Compare against a small autoregressive baseline (e.g., NanoGPT-sized) to calibrate expectations: measure perplexity, n-gram overlap, and human judgments.
- To scale, consider moving diffusion to a learned latent space (autoencoder + latent diffusion) rather than token embeddings; this often improves sample quality per compute.

Conclusion & Takeaways

Tiny Diffusion is a tidy, educational demonstration that brings diffusion ideas into text generation at a playable scale. It highlights the practical choices you must make: operate on characters or embeddings, design a noise schedule, choose sampling steps, and evaluate beyond simple metrics. While autoregressive transformers remain the default for high-quality text generation, diffusion models offer interesting advantages for controllability, editing, and robustness. For anyone curious about the intersection of diffusion and NLP, Tiny Diffusion is a useful starting point: inspect the code, try alternative objectives, and experiment with hybrid decoders.

Further reading

- Sohl-Dickstein et al. (2015) — early work on diffusion processes in machine learning.
- [Ho et al. (2020)](https://doi.org/10.18820/9781928314837/10) — Denoising Diffusion Probabilistic Models (DDPM).
- [Song et al. (2020)](https://doi.org/10.5194/acp-2020-318-rc2) — Denoising Diffusion Implicit Models (DDIM).
- [Rombach et al. (2022)](https://doi.org/10.37307/b.978-3-503-20929-3) — Latent Diffusion Models for high-resolution synthesis.
- [Li et al. (2022)](https://doi.org/10.1515/9783110799750) — Diffusion-LM: diffusion for controllable text generation.

Acknowledgements and credits
This article discusses and builds on the Tiny Diffusion project by Nathan Barry (Hacker News post and GitHub: https://github.com/nathan-barry/tiny-diffusion). The discussion weaves foundational research on diffusion models (Ho et al., 2020; Song et al., 2020) and text-diffusion work (Li et al., 2022; Rombach et al., 2022).

If you want, I can walk through the repository, explain key files (training loop, transformer definition, noise schedule), or produce a small notebook showing how to sample and visualize intermediate denoising steps.


## References

- [Show HN: Tiny Diffusion – A character-level text diffusion model from scratch](https://github.com/nathan-barry/tiny-diffusion) — @nathan-barry on GitHub

- [Dickstein et al. (2015)](https://doi.org/10.3386/w21351)
- [Ho et al. (2020)](https://doi.org/10.18820/9781928314837/10)
- [Song et al. (2020)](https://doi.org/10.5194/acp-2020-318-rc2)
- [Rombach et al. (2022)](https://doi.org/10.37307/b.978-3-503-20929-3)
- [Li et al. (2022)](https://doi.org/10.1515/9783110799750)