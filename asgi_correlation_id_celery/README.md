## Celery

> Note: If you're using the celery integration, install the package with `pip install asgi-correlation-id[celery]`

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
