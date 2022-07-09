# Zfs exporter

Prometheus [zfs exporter](https://github.com/pdf/zfs_exporter) for zfs metrics.

## Quickstart

Deploy the `prometheus-zfs-exporter` charm and relate it to the units you want
to export the metrics:

```bash
$ juju deploy prometheus-zfs-exporter
$ juju relate prometheus-zfs-exporter tiny-bash
```

The charm can register it's scrape target with Prometheus via relation to the
[Prometheus charm](https://charmhub.io/prometheus2):

```bash
$ juju deploy prometheus2
$ juju relate prometheus-zfs-exporter prometheus2
```

## Developing

We supply a `Makefile` with a target to build the charm:

```bash
$ make charm
```

## Testing
Run `tox -e ALL` to run unit + integration tests and verify linting.

## Contact

**We want to hear from you!**

Email us @ [info@dwellir.com](mailto:info@dwellir.com)

## Bugs

In the case things aren't working as expected, please
[file a bug](https://github.com/dwellir-public/charm-prometheus-zfs-exporter/issues).

## License

The charm is maintained under the MIT license. See `LICENSE` file in this
directory for full preamble.

Copyright &copy; Dwellir AB 2021

## Attributions 

Omnivector Solutions which this charm largely builds on.

Also to https://github.com/pdf/zfs_exporter


