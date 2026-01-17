# Sponsor Slot Configuration

The sponsor slot is optional and hidden unless enabled in site configuration.

## Configure

Add to site/hugo.toml:

```toml
[params.sponsor]
  enabled = false
  label = "Sponsor"  # optional
  url = "https://example.com"
  text = "Your sponsor message"
  disclaimer = "Paid placement"
```

## Placement

- Homepage (below home info)
- Post footer (above tags)

## Behavior

- Hidden when `enabled = false`
- Hidden when `url` or `text` is missing
