import os
import sys
import time
import traceback

import newrelic.agent  # See https://bit.ly/2xBVKBH

environment = os.environ.get("NOTIFY_ENVIRONMENT")
newrelic.agent.initialize(environment=environment)  # noqa: E402

# Detect OpenTelemetry auto-instrumentation
# When OTEL is present, use sync workers to avoid conflicts with gevent monkey patching
def is_otel_enabled():
    """Check if OpenTelemetry auto-instrumentation is enabled."""
    # Check for common OTEL environment variables
    otel_vars = [
        "OTEL_SERVICE_NAME",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_RESOURCE_ATTRIBUTES",
        "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS",
        "OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST",
        "OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE"
    ]
    
    # If any OTEL environment variable is set, assume OTEL is enabled
    for var in otel_vars:
        if os.environ.get(var):
            return True
    
    # Check if opentelemetry packages are available
    try:
        import opentelemetry
        return True
    except ImportError:
        pass
    
    return False

workers = 4
# Use sync workers when OpenTelemetry is detected to avoid gevent conflicts
worker_class = "sync" if is_otel_enabled() else "gevent"
worker_connections = 256
bind = "0.0.0.0:{}".format(os.getenv("PORT"))
accesslog = "-"

# See AWS doc
# > We also recommend that you configure the idle timeout of your application
# to be larger than the idle timeout configured for the load balancer.
# > By default, Elastic Load Balancing sets the idle timeout value for your load balancer to 60 seconds.
# https://docs.aws.amazon.com/elasticloadbalancing/latest/application/application-load-balancers.html#connection-idle-timeout
on_aws = environment in ["production", "staging", "scratch", "dev"]
if on_aws:
    # To avoid load balancers reporting errors on shutdown instances, see AWS doc
    # > We also recommend that you configure the idle timeout of your application
    # > to be larger than the idle timeout configured for the load balancer.
    # > By default, Elastic Load Balancing sets the idle timeout value for your load balancer to 60 seconds.
    # https://docs.aws.amazon.com/elasticloadbalancing/latest/application/application-load-balancers.html#connection-idle-timeout
    keepalive = 75

    # The default graceful timeout period for Kubernetes is 30 seconds, so
    # make sure that the timeouts defined here are less than the configured
    # Kubernetes timeout. This ensures that the gunicorn worker will exit
    # before the Kubernetes pod is terminated. This is important because
    # Kubernetes will send a SIGKILL to the pod if it does not terminate
    # within the grace period. If the worker is still processing requests
    # when it receives the SIGKILL, it will be terminated abruptly and
    # will not be able to finish processing the request. This can lead to
    # 502 errors being returned to the client.
    #
    # Also, some libraries such as NewRelic might need some time to finish
    # initialization before the worker can start processing requests. The
    # timeout values should consider these factors.
    #
    # Gunicorn config:
    # https://docs.gunicorn.org/en/stable/settings.html#graceful-timeout
    #
    # Kubernetes config:
    # https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/
    graceful_timeout = 85
    timeout = 90

# Start timer for total running time
start_time = time.time()


def on_starting(server):
    server.log.info("Starting Document Download API")
    server.log.info(f"Using worker class: {worker_class}")
    if worker_class == "sync":
        server.log.info("OpenTelemetry detected - using sync workers to avoid gevent conflicts")
    else:
        server.log.info("OpenTelemetry not detected - using gevent workers for better performance")


def worker_abort(worker):
    worker.log.info("worker received ABORT {}".format(worker.pid))
    for threadId, stack in sys._current_frames().items():
        worker.log.error("".join(traceback.format_stack(stack)))


def on_exit(server):
    elapsed_time = time.time() - start_time
    server.log.info("Stopping Document Download API")
    server.log.info("Total gunicorn API running time: {:.2f} seconds".format(elapsed_time))


def worker_int(worker):
    worker.log.info("worker: received SIGINT {}".format(worker.pid))
