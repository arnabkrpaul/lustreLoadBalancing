# Open and Distributed Data Monitoring

## Dependencies

        - if python < 2.5, then we need `argparse` package
        - pika (RabbitMQ client library) 

## Build binary rpm package

    python setup.py bdist_rpm

## Metric Plugins

There are a few requirements for a valid plugin extension:

- A plugin needs to be named starting with `metric_`. 
- Plugins must define 4 functions:
  - `def metric_init(name, config_file, is_subscriber = False, loglevel=logging.DEBUG)`
  - `def metric_cleanup( is_subscriber = False)`
  - `def get_stats()`
  - `def save_stats( msg)`

### Plugin Function Behavior

- `metric_init()` returns True if it initialized properly.
- `get_stats()` returns the data that is to be published.  (Currently all plugins use JSON-encoded text, but that's probably not actually necessary.)
- The other functions return nothing.
- `get_stats()` is called by the publisher.
- `save_stats()` is called by the subscriber.
- `metric_init()` and `metric_cleanup()` are called by both.

The data that `get_stats()` returns (on the publisher side) is passed to `save_stats()` (on the subscriber side).  It's up to `save_stats()` to do something useful with that data.