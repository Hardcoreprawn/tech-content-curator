"""Self-hosted/home-lab specialized generator.

Generates deep-dive articles for self-hosting and home lab topics with
architectural guidance, component comparisons, and practical setup instructions.
"""

from rich.console import Console

from ...models import EnrichedItem
from ..base import BaseGenerator

console = Console()


class SelfHostedGenerator(BaseGenerator):
    """Deep-dive generator for self-hosted and home lab topics."""

    @property
    def name(self) -> str:
        return "Self-Hosted Deep-Dive Generator"

    @property
    def priority(self) -> int:
        return 60  # Higher priority - very specific content type

    def can_handle(self, item: EnrichedItem) -> bool:
        """Heuristically detect if an item is about self-hosting/home lab.

        Uses both extracted topics and raw content keywords.
        """
        topic_text = " ".join(item.topics).lower() if item.topics else ""
        content_text = item.original.content.lower()

        # More specific keywords to avoid false positives
        keywords = [
            "self-hosted",
            "self hosted",
            "selfhosted",
            "home lab",
            "homelab",
            "home-lab",
            "docker compose",
            "kubernetes",
            "k8s",
            "traefik",
            "caddy server",
            "authelia",
            "oauth proxy",
            "oauth2-proxy",
            "authentik",
            "jellyfin",
            "plex media",
            "home assistant",
            "proxmox",
            "portainer",
            "nginx proxy manager",
            "reverse proxy",
            "wireguard",
            "tailscale",
            "truenas",
            " nas ",
            "nas server",  # More specific NAS matches
        ]
        return any(k in topic_text or k in content_text for k in keywords)

    def generate_content(self, item: EnrichedItem) -> tuple[str, int, int]:
        """Generate a deep-dive self-hosted/home-lab article.

        Focus on: reference architecture, component choices, trade-offs, and a start plan.

        Args:
            item: The enriched item about self-hosting

        Returns:
                        Tuple of (article content as markdown string, input tokens, output tokens)
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")

        prompt = f"""
    Write a comprehensive, practical guide for running self-hosted services at home.

    CONTEXT FROM SOCIAL POST:
    "{item.original.content}"
    SOURCE URL: {item.original.url}
    TOPICS: {", ".join(item.topics)}

  GOALS:
    - Explain a reference architecture for a home network running containers
    - Compare 2-3 credible options per key category with detailed trade-offs and use-case fit
        if not self.client:
            raise ValueError("OpenAI client not initialized")

        prompt = f
    Write a comprehensive, practical guide for running self-hosted services at home.

    CONTEXT FROM SOCIAL POST:
    "{item.original.content}"
    SOURCE URL: {item.original.url}
    TOPICS: {", ".join(item.topics)}

  GOALS:
    - Explain a reference architecture for a home network running containers
    - Compare 2-3 credible options per key category with detailed trade-offs and use-case fit
    - Provide a minimal viable setup and a clear growth path
    - Include an ASCII network diagram showing component relationships
    - Recommend specific services for common use-cases with detailed rationale (2-3 sentences per tool)
    - Include direct links to official project sites/repos for all mentioned tools
    - Credit the original source at the end

    CATEGORIES TO COVER (with depth):
    - Reverse proxy / ingress (e.g., Traefik, Caddy, Nginx Proxy Manager)
      * Explain routing, SSL/TLS termination, and when each shines
    - Authentication and SSO (e.g., Authelia, Authentik, OAuth2-Proxy)
      * Cover security model, 2FA support, and integration patterns
    - Orchestration (Docker Compose vs Portainer vs K8s-in-homelab)
      * Compare complexity, scalability, and learning curve
    - Storage + backups (e.g., TrueNAS, ZFS snapshots, Restic/Borg)
      * Discuss data protection, snapshots, and disaster recovery
    - Monitoring + logs (e.g., Prometheus/Grafana, Loki, Uptime-Kuma)
      * Explain metrics collection, alerting, and log aggregation
    - Remote access (e.g., WireGuard, Tailscale)
      * Cover security, ease of setup, and NAT traversal
    - Example apps (Media: Jellyfin; Home automation: Home Assistant; Docs: Outline/Wiki.js)
      * Explain what each does and why it's popular

    REQUIREMENTS:
    - 1200-1500 words minimum - provide substantial detail
    - Structure with clear ## headings and ### subheadings
    - Include markdown links for all tool names pointing to their official sites
    - Include a "Reference Architecture" ASCII diagram showing: Internet -> Reverse Proxy -> Apps, plus Auth, Storage, Monitoring
    - Provide detailed "Getting Started" section with a realistic Docker Compose example (without sensitive credentials)
    - Compare options with detailed pros/cons and specific use-case recommendations
    - Include a "Growth Path" section explaining how to scale from simple to advanced
    - Include a short "Key Takeaways" bullet list (3–5 bullets) after the introduction
    - Explain non-mainstream terms and acronyms inline the first time; add a brief blockquote callout when optional using the format:
      > Background: one-sentence explanation
    - Close with proper attribution: Credit the original post/author and include source URL
    """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=2500,  # Allow for longer, more detailed content
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from OpenAI")

            # Extract actual token usage
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            return content.strip(), input_tokens, output_tokens
        except Exception as e:
            console.print(
                f"[yellow]⚠[/yellow] Self-hosted article generation failed: {e}"
            )
            fallback = """
## Self-Hosting at Home: A Practical Starting Point

This guide outlines a simple, resilient way to run containers at home.

### Minimal Reference
- Reverse proxy: Caddy or Traefik
- Auth: Authelia or Authentik
- Orchestration: Docker Compose
- Storage: TrueNAS with Restic backups
- Monitoring: Prometheus + Grafana

Start with Docker Compose and add components gradually.
"""
            return fallback, 0, 0
