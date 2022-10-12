[![pypi](https://img.shields.io/pypi/v/asgi-correlation-id)](https://pypi.org/project/asgi-correlation-id/)
[![test](https://github.com/snok/asgi-correlation-id/actions/workflows/test.yml/badge.svg)](https://github.com/snok/asgi-correlation-id/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/snok/asgi-correlation-id/branch/main/graph/badge.svg?token=1aXlWPm2gb)](https://codecov.io/gh/snok/asgi-correlation-id)

# ASGI Correlation ID middleware

Middleware for reading or generating correlation IDs for each incoming request. Correlation IDs can then be added to your
logs, making it simple to retrieve all logs generated from a single HTTP request.

When the middleware detects a correlation ID HTTP header in an incoming request, the ID is stored. If no header is
found, a correlation ID is generated for the request instead.

The middleware checks for the `X-Request-ID` header by default, but can be set to any key.
`X-Correlation-ID` is also pretty commonly used.

## Example

Once logging is configured, your output will go from this:

```
INFO    ... project.views  This is an info log
WARNING ... project.models This is a warning log
INFO    ... project.views  This is an info log
INFO    ... project.views  This is an info log
WARNING ... project.models This is a warning log
WARNING ... project.models This is a warning log
```

to this:

```docker
INFO    ... [773fa6885] project.views  This is an info log
WARNING ... [773fa6885] project.models This is a warning log
INFO    ... [0d1c3919e] project.views  This is an info log
INFO    ... [99d44111e] project.views  This is an info log
WARNING ... [0d1c3919e] project.models This is a warning log
WARNING ... [99d44111e] project.models This is a warning log
```

Now we're actually able to see which logs are related.

# Installation

```
pip install asgi-correlation-id
```

# Setup

To set up the package, you need to add the middleware and configure logging.

## Adding the middleware

The middleware can be added like this:

```python
from fastapi import FastAPI

from asgi_correlation_id import CorrelationIdMiddleware

app = FastAPI()
app.add_middleware(CorrelationIdMiddleware)
```

or any other way your framework allows.

For [Starlette](https://github.com/encode/starlette) apps, just substitute `FastAPI` with `Starlette` in all examples.

## Configure logging

This section assumes you have already started configuring logging in your project. If this is not the case, check out
the section on [setting up logging from scratch](#setting-up-logging-from-scratch) instead.

To set up logging of the correlation ID, you simply have to add the log-filter the package provides.

If your current log-config looked like this:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'web': {
            'class': 'logging.Formatter',
            'datefmt': '%H:%M:%S',
            'format': '%(levelname)s ... %(name)s %(message)s',
        },
    },
    'handlers': {
        'web': {
            'class': 'logging.StreamHandler',
            'formatter': 'web',
        },
    },
    'loggers': {
        'my_project': {
            'handlers': ['web'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

You simply have to add the filter, like this:

```diff
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
+   'filters': {
+       'correlation_id': {
+           '()': 'asgi_correlation_id.CorrelationIdFilter',
+           'uuid_length': 32,
+       },
+   },
    'formatters': {
        'web': {
            'class': 'logging.Formatter',
            'datefmt': '%H:%M:%S',
+           'format': '%(levelname)s ... [%(correlation_id)s] %(name)s %(message)s',
        },
    },
    'handlers': {
        'web': {
            'class': 'logging.StreamHandler',
+           'filters': ['correlation_id'],
            'formatter': 'web',
        },
    },
    'loggers': {
        'my_project': {
            'handlers': ['web'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

If you're using a json log-formatter, just add `correlation-id: %(correlation_id)s` to your list of properties.

## Middleware configuration

The middleware can be configured in a few ways, but there are no required arguments.

```python
app.add_middleware(
    CorrelationIdMiddleware,
    header_name='X-Request-ID',
    generator=lambda: uuid4().hex,
    validator=is_valid_uuid4,
    transformer=lambda a: a,
)
```

Configurable middleware arguments include:

**header_name**

- Type: `str`
- Default: `X-Request-ID`
- Description: The header name decides which HTTP header value to read correlation IDs from. `X-Request-ID` and
  `X-Correlation-ID` are common choices.

**generator**

- Type: `Callable[[], str]`
- Default: `lambda: uuid4().hex`
- Description: The generator function is responsible for generating new correlation IDs when no ID is received from an
  incoming request's headers. We use UUIDs by default, but if you prefer, you could use libraries
  like [nanoid](https://github.com/puyuan/py-nanoid) or your own custom function.

**validator**

- Type: `Callable[[str], bool]`
- Default: `is_valid_uuid4` (
  found [here](https://github.com/snok/asgi-correlation-id/blob/main/asgi_correlation_id/middleware.py#L17))
- Description: The validator function is used when reading incoming HTTP header values. By default, we discard non-UUID
  formatted header values, to enforce correlation ID uniqueness. If you prefer to allow any header value, you can set
  this setting to `None`, or pass your own validator.

**transformer**

- Type: `Callable[[str], str]`
- Default: `lambda a: a`
- Description: Most users won't need a transformer, and by default we do nothing.
  The argument was added for cases where users might want to alter incoming or generated ID values in some way. It
  provides a mechanism for transforming an incoming ID in a way you see fit. See the middleware code for more context.

## Exception handling

By default, the `X-Request-ID` and `Access-Control-Expose-Headers` response headers will be included in all
responses from the server, *except* in the case of unhandled server errors. If you wish to include request IDs in the
case of a `500` error you can add a custom exception handler.

Here are some simple examples to help you get started. See each framework's documentation for more info.

### Starlette

Docs: https://www.starlette.io/exceptions/

```python
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.applications import Starlette

from asgi_correlation_id import correlation_id


async def custom_exception_handler(request: Request, exc: Exception) -> PlainTextResponse:
    return PlainTextResponse(
        "Internal Server Error",
        status_code=500,
        headers={
            'X-Request-ID': correlation_id.get() or "",
            'Access-Control-Expose-Headers': 'X-Request-ID'
        }
    )


app = Starlette(
    ...,
    exception_handlers={500: custom_exception_handler}
)
```

### FastAPI

Docs: https://fastapi.tiangolo.com/tutorial/handling-errors/

```python
from app.main import app
from fastapi import HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse

from asgi_correlation_id import correlation_id


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return await http_exception_handler(
        request,
        HTTPException(
            500,
            'Internal server error',
            headers={
                'X-Request-ID': correlation_id.get() or "",
                'Access-Control-Expose-Headers': 'X-Request-ID'
            }
        ))
```

# Setting up logging from scratch

If your project does not have logging configured, this section will explain how to get started. If you want even more
details, take a look
at [this blogpost](https://medium.com/@sondrelg_12432/setting-up-request-id-logging-for-your-fastapi-application-4dc190aac0ea)
.

The Python [docs](https://docs.python.org/3/library/logging.config.html) explain there are a few configuration functions
you may use for simpler setup. For this example we will use `dictConfig`, because that's what, e.g., Django users should
find most familiar, but the different configuration methods are interchangable, so if you want to use another method,
just browse the python docs and change the configuration method as you please.

The benefit of `dictConfig` is that it lets you specify your entire logging configuration in a single data structure,
and it lets you add conditional logic to it. The following example shows how to set up both console and JSON logging:

```python
from logging.config import dictConfig

from app.core.config import settings


def configure_logging() -> None:
    dictConfig(
        {
            'version': 1,
            'disable_existing_loggers': False,
            'filters': {  # correlation ID filter must be added here to make the %(correlation_id)s formatter work
                'correlation_id': {
                    '()': 'asgi_correlation_id.CorrelationIdFilter',
                    'uuid_length': 8 if not settings.ENVIRONMENT == 'local' else 32,
                },
            },
            'formatters': {
                'console': {
                    'class': 'logging.Formatter',
                    'datefmt': '%H:%M:%S',
                    # formatter decides how our console logs look, and what info is included.
                    # adding %(correlation_id)s to this format is what make correlation IDs appear in our logs
                    'format': '%(levelname)s:\t\b%(asctime)s %(name)s:%(lineno)d [%(correlation_id)s] %(message)s',
                },
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    # Filter must be declared in the handler, otherwise it won't be included
                    'filters': ['correlation_id'],
                    'formatter': 'console',
                },
            },
            # Loggers can be specified to set the log-level to log, and which handlers to use
            'loggers': {
                # project logger
                'app': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': True},
                # third-party package loggers
                'databases': {'handlers': ['console'], 'level': 'WARNING'},
                'httpx': {'handlers': ['console'], 'level': 'INFO'},
                'asgi_correlation_id': {'handlers': ['console'], 'level': 'WARNING'},
            },
        }
    )
```

With the logging configuration defined within a function like this, all you have to do is make sure to run the function
on startup somehow, and logging should work for you. You can do this any way you'd like, but passing it to
the `FastAPI.on_startup` list of callables is a good starting point.

# Integration with structlog

[structlog](https://www.structlog.org/) is a Python library that enables structured logging.

It is trivial to configure with `asgi_correlation_id`:

```python
import logging
from typing import Any

import structlog
from asgi_correlation_id import correlation_id


def add_correlation(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add request id to log message."""
    if request_id := correlation_id.get():
        event_dict["request_id"] = request_id
    return event_dict


structlog.configure(
    processors=[
        add_correlation,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M.%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

# Integration with [SAQ](https://github.com/tobymao/saq)

If you're using [saq](https://github.com/tobymao/saq/), you
can easily transfer request IDs from the web server to your
workers by using the event hooks provided by the library:

```python
from uuid import uuid4

from asgi_correlation_id import correlation_id
from saq import Job, Queue


CID_TRANSFER_KEY = 'correlation_id'


async def before_enqueue(job: Job) -> None:
    """
    Transfer the correlation ID from the current context to the worker.

    This might be called from a web server or a worker process.
    """
    job.meta[CID_TRANSFER_KEY] = correlation_id.get() or uuid4()


async def before_process(ctx: dict) -> None:
    """
    Load correlation ID from the enqueueing process to this one.
    """
    correlation_id.set(ctx['job'].meta.get(CID_TRANSFER_KEY, uuid4()))


async def after_process(ctx: dict) -> None:
    """
    Reset correlation ID for this process.
    """
    correlation_id.set(None)

queue = Queue(...)
queue.register_before_enqueue(before_enqueue)

priority_settings = {
    ...,
    'queue': queue,
    'before_process': before_process,
    'after_process': after_process,
}
```

# Extensions

In addition to the middleware, we've added a couple of extensions for third-party packages.

## Sentry

If your project has [sentry-sdk](https://pypi.org/project/sentry-sdk/)
installed, correlation IDs will automatically be added to Sentry events as a `transaction_id`.

See
this [blogpost](https://blog.sentry.io/2019/04/04/trace-errors-through-stack-using-unique-identifiers-in-sentry#1-generate-a-unique-identifier-and-set-as-a-sentry-tag-on-issuing-service)
for a little bit of detail. The transaction ID is displayed in the event detail view in Sentry and is just an easy way
to connect logs to a Sentry event.

## Celery

For Celery user's there's one primary issue: workers run as completely separate processes, so correlation IDs are lost
when spawning background tasks from requests.

However, with some Celery signal magic, we can actually transfer correlation IDs to worker processes, like this:

```python
@before_task_publish.connect()
def transfer_correlation_id(headers) -> None:
    # This is called before task.delay() finishes
    # Here we're able to transfer the correlation ID via the headers kept in our backend
    headers[header_key] = correlation_id.get()


@task_prerun.connect()
def load_correlation_id(task) -> None:
    # This is called when the worker picks up the task
    # Here we're able to load the correlation ID from the headers
    id_value = task.request.get(header_key)
    correlation_id.set(id_value)
```

To configure correlation ID transfer, simply import and run the setup function the package provides:

```python
from asgi_correlation_id.extensions.celery import load_correlation_ids

load_correlation_ids()
```

### Taking it one step further - Adding Celery tracing IDs

In addition to transferring request IDs to Celery workers, we've added one more log filter for improving tracing in
celery processes. This is completely separate from correlation ID functionality, but is something we use ourselves, so
keep in the package with the rest of the signals.

The log filter adds an ID, `celery_current_id` for each worker process, and an ID, `celery_parent_id` for the process
that spawned it.

Here's a quick summary of outputs from different scenarios:

| Scenario                                           | Correlation ID     | Celery Current ID | Celery Parent ID |
|------------------------------------------          |--------------------|-------------------|------------------|
| Request                                            | ✅                |                   |                  |
| Request -> Worker                                  | ✅                | ✅               |                  |
| Request -> Worker -> Another worker                | ✅                | ✅               | ✅              |
| Beat -> Worker     | ✅*               | ✅                |                   |                  |
| Beat -> Worker -> Worker     | ✅*     | ✅                | ✅               | ✅              |

*When we're in a process spawned separately from an HTTP request, a correlation ID is still spawned for the first
process in the chain, and passed down. You can think of the correlation ID as an origin ID, while the combination of
current and parent-ids as a way of linking the chain.

To add the current and parent IDs, just alter your `celery.py` to this:

```diff
+ from asgi_correlation_id.extensions.celery import load_correlation_ids, load_celery_current_and_parent_ids

load_correlation_ids()
+ load_celery_current_and_parent_ids()
```

If you wish to correlate celery task IDs through the IDs found in your broker (i.e., the celery `task_id`), use the `use_internal_celery_task_id` argument on `load_celery_current_and_parent_ids`
```diff
from asgi_correlation_id.extensions.celery import load_correlation_ids, load_celery_current_and_parent_ids

load_correlation_ids()
+ load_celery_current_and_parent_ids(use_internal_celery_task_id=True)
```
Note: `load_celery_current_and_parent_ids` will ignore the `generator` argument when `use_internal_celery_task_id` is set to `True`

To set up the additional log filters, update your log config like this:

```diff
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'correlation_id': {
+           '()': 'asgi_correlation_id.CorrelationIdFilter',
+           'uuid_length': 32,
+       },
+       'celery_tracing': {
+            '()': 'asgi_correlation_id.CeleryTracingIdsFilter',
+            'uuid_length': 32,
+       },
    },
    'formatters': {
        'web': {
            'class': 'logging.Formatter',
            'datefmt': '%H:%M:%S',
            'format': '%(levelname)s ... [%(correlation_id)s] %(name)s %(message)s',
        },
+       'celery': {
+           'class': 'logging.Formatter',
+           'datefmt': '%H:%M:%S',
+           'format': '%(levelname)s ... [%(correlation_id)s] [%(celery_parent_id)s-%(celery_current_id)s] %(name)s %(message)s',
+       },
    },
    'handlers': {
        'web': {
            'class': 'logging.StreamHandler',
            'filters': ['correlation_id'],
            'formatter': 'web',
        },
+       'celery': {
+           'class': 'logging.StreamHandler',
+           'filters': ['correlation_id', 'celery_tracing'],
+           'formatter': 'celery',
+       },
    },
    'loggers': {
        'my_project': {
+           'handlers': ['celery' if any('celery' in i for i in sys.argv) else 'web'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

With these IDs configured you should be able to:

1. correlate all logs from a single origin, and
2. piece together the order each log was run, and which process spawned which

#### Example

With everything configured, assuming you have a set of tasks like this:

```python
@celery.task()
def debug_task() -> None:
    logger.info('Debug task 1')
    second_debug_task.delay()
    second_debug_task.delay()


@celery.task()
def second_debug_task() -> None:
    logger.info('Debug task 2')
    third_debug_task.delay()
    fourth_debug_task.delay()


@celery.task()
def third_debug_task() -> None:
    logger.info('Debug task 3')
    fourth_debug_task.delay()
    fourth_debug_task.delay()


@celery.task()
def fourth_debug_task() -> None:
    logger.info('Debug task 4')
```

your logs could look something like this:

```
   correlation-id               current-id
          |        parent-id        |
          |            |            |
INFO [3b162382e1] [   None   ] [93ddf3639c] project.tasks - Debug task 1
INFO [3b162382e1] [93ddf3639c] [24046ab022] project.tasks - Debug task 2
INFO [3b162382e1] [93ddf3639c] [cb5595a417] project.tasks - Debug task 2
INFO [3b162382e1] [24046ab022] [08f5428a66] project.tasks - Debug task 3
INFO [3b162382e1] [24046ab022] [32f40041c6] project.tasks - Debug task 4
INFO [3b162382e1] [cb5595a417] [1c75a4ed2c] project.tasks - Debug task 3
INFO [3b162382e1] [08f5428a66] [578ad2d141] project.tasks - Debug task 4
INFO [3b162382e1] [cb5595a417] [21b2ef77ae] project.tasks - Debug task 4
INFO [3b162382e1] [08f5428a66] [8cad7fc4d7] project.tasks - Debug task 4
INFO [3b162382e1] [1c75a4ed2c] [72a43319f0] project.tasks - Debug task 4
INFO [3b162382e1] [1c75a4ed2c] [ec3cf4113e] project.tasks - Debug task 4
```
