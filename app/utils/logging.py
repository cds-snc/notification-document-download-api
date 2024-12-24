def log_config(app):
    "A function to log the configuration values of the app on startup"
    do_not_log = ["SECRET_KEY", "AUTH_TOKENS", "ANTIVIRUS_API_KEY"]
    for key in app.config:
        if key in do_not_log:
            continue
        app.logger.info(
            f"Config value: {key}={app.config[key]}"
        )