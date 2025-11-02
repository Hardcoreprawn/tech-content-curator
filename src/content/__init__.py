"""Content management package.

This package handles article lifecycle management including creation, storage,
retrieval, and publishing of generated articles.

Responsibilities:
- Article CRUD operations
- Frontmatter generation and parsing
- File system organization
- Publishing workflow
- Content versioning

Components:
- article_manager: Core article management operations
- frontmatter: Hugo frontmatter handling
- publisher: Publishing pipeline

Usage:
    from src.content import ArticleManager, save_article, load_article

    manager = ArticleManager(content_dir)
    manager.save(article)
    existing = manager.load(slug)
    manager.delete(slug)

Design Principles:
- Immutable articles (edit = new version)
- Clear file naming and organization
- Atomic write operations
- Validation before saving
- Backup before destructive operations

File Organization:
- content/posts/YYYY-MM-DD-slug.md (published articles)
- content/archive/ (older articles)
- Each article has frontmatter + content

Frontmatter Schema:
- title: Article title
- date: Publication date
- slug: URL-friendly identifier
- topics: Array of topics/tags
- source: Original source URL
- score: Quality score
- images: Cover image and social previews
"""

# Content management will be implemented in Phase 3
# from .article_manager import ArticleManager, save_article, load_article
# from .frontmatter import generate_frontmatter, parse_frontmatter
# from .publisher import publish_article, archive_article

__all__ = []
