"""
Extension point for every "Future Expansion" / "Nice-to-Have" module
listed in the project brief (Instagram Reels export, TikTok export, auto
captions, AI subtitles, animated subscribe button, logo watermark,
thumbnail generation, batch thumbnails, AI titles/descriptions/hashtags,
YouTube upload, silence trimming, intro/outro, fade in/out, background
music, render queue persistence, and so on).

None of those features are implemented yet -- this package only defines
the *contract* (:class:`~shorts_generator.plugins.base.RenderPlugin`) a
future module implements, and the *registry* the pipeline uses to
discover and run enabled plugins, so that adding one of those modules
later never requires touching ``pipeline.py`` or the background
renderers.

See ``base.py`` for the hook points and ``examples.py`` for a fully
working (but disabled-by-default) reference implementation.
"""
