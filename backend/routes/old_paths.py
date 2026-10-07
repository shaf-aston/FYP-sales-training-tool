"""Old API paths, kept as aliases: remove once the deployed web uses /api/buy and /api/sell.

The Vercel frontend and the Oracle VM backend deploy separately, so for a while the
live web may still call these. Every alias runs the very same view function as its
new path, so rate limits, input checks and session lookup are identical.
"""

from flask import Flask

from . import sell

# Old buy-mode path -> its new path. Methods are copied from the new route.
OLD_BUY_PATHS = {
    "/api/init": "/api/buy/init",
    "/api/chat": "/api/buy/chat",
    "/api/edit": "/api/buy/edit",
    "/api/reset": "/api/buy/reset",
    "/api/training/ask": "/api/buy/coach",
    "/api/test/question": "/api/buy/quiz/question",
    "/api/test/stage": "/api/buy/quiz/stage",
    "/api/test/next-move": "/api/buy/quiz/next-move",
    "/api/test/direction": "/api/buy/quiz/direction",
}

# Old sell-mode prefix: the whole sell blueprint is mounted here a second time.
OLD_SELL_PREFIX = "/api/prospect"


def register_old_paths(app: Flask) -> None:
    """Mount every old path on the view that now serves it. Call after the new routes exist."""
    app.register_blueprint(sell.bp, url_prefix=OLD_SELL_PREFIX, name="old_sell")

    new_rules = {rule.rule: rule for rule in app.url_map.iter_rules()}
    for old, new in OLD_BUY_PATHS.items():
        rule = new_rules[new]
        app.add_url_rule(
            old,
            endpoint="old_" + rule.endpoint.replace(".", "_"),
            view_func=app.view_functions[rule.endpoint],
            # HEAD and OPTIONS are added by Flask itself, as on the new path.
            methods=sorted(rule.methods - {"HEAD", "OPTIONS"}),
        )
