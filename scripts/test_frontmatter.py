import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import frontmatter

three_days_ago = (datetime.now(UTC) - timedelta(days=3)).strftime('%Y-%m-%d')
content = f"""---
title: Recent Article
date: {three_days_ago}
sources:
  - url: https://github.com/user/repo
---
Content.
"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
    f.write(content)
    fname = f.name

post = frontmatter.load(fname)
print('Meta:', post.metadata)
print('Date:', post.metadata.get('date'))
print('Sources:', post.metadata.get('sources'))

Path(fname).unlink()
