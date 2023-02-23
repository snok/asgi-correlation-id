## Sentry

If your project has [sentry-sdk](https://pypi.org/project/sentry-sdk/)
installed, correlation IDs will automatically be added to Sentry events as a `transaction_id`.

See
this [blogpost](https://blog.sentry.io/2019/04/04/trace-errors-through-stack-using-unique-identifiers-in-sentry#1-generate-a-unique-identifier-and-set-as-a-sentry-tag-on-issuing-service)
for a little bit of detail. The transaction ID is displayed in the event detail view in Sentry and is just an easy way
to connect logs to a Sentry event.
